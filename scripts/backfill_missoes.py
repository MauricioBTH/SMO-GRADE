"""Backfill de smo.fracoes.missao_id / municipio_id a partir dos catalogos.

Estrategia:
  1. match exato (normalizacao: uppercase sem acentos) -> UPDATE direto
  2. match fuzzy via rapidfuzz (score >= 85) -> UPDATE + log com score
  3. score < 85 ou multiplos candidatos empatados -> reporta (nenhum UPDATE)

Uso:
    python -m scripts.backfill_missoes [--dry-run]

O script e idempotente: so processa linhas onde missao_id IS NULL
(respectivamente municipio_id IS NULL) e o texto bruto nao vazio.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402
from app.models.database import get_connection  # noqa: E402
from app.services.catalogo_types import normalizar  # noqa: E402

try:
    from rapidfuzz import fuzz, process  # noqa: E402
except ImportError:
    print("rapidfuzz nao instalado. rode: pip install rapidfuzz==3.10.1",
          file=sys.stderr)
    sys.exit(1)


SCORE_MIN: int = 85


@dataclass(frozen=True)
class MatchResult:
    total_lidos: int
    exatos: int
    fuzzy: int
    ambiguos: int
    sem_match: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _carregar_catalogo_missoes() -> dict[str, str]:
    """{nome_normalizado: id} das missoes ativas."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, nome FROM smo.missoes WHERE ativo = TRUE"
            )
            return {normalizar(r["nome"]): str(r["id"]) for r in cur.fetchall()}
    finally:
        conn.close()


def _carregar_catalogo_municipios() -> dict[str, str]:
    """{nome_normalizado: id} dos municipios ativos."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, nome FROM smo.municipios WHERE ativo = TRUE"
            )
            return {normalizar(r["nome"]): str(r["id"]) for r in cur.fetchall()}
    finally:
        conn.close()


def _match_fuzzy(
    termo_norm: str, catalogo: dict[str, str]
) -> tuple[str | None, int, bool]:
    """Retorna (id_match, score, ambiguo)."""
    if not catalogo:
        return None, 0, False
    nomes: list[str] = list(catalogo.keys())
    resultado = process.extract(
        termo_norm, nomes, scorer=fuzz.token_sort_ratio, limit=3
    )
    if not resultado:
        return None, 0, False
    top_nome, top_score, _ = resultado[0]
    if top_score < SCORE_MIN:
        return None, int(top_score), False
    # Ambiguo se segundo tambem passa do minimo e esta a <=2 pontos do topo
    if len(resultado) > 1:
        _, segundo_score, _ = resultado[1]
        if segundo_score >= SCORE_MIN and (top_score - segundo_score) <= 2:
            return None, int(top_score), True
    return catalogo[top_nome], int(top_score), False


# ---------------------------------------------------------------------------
# Backfill
# ---------------------------------------------------------------------------


def backfill_missoes(dry_run: bool = False) -> MatchResult:
    catalogo: dict[str, str] = _carregar_catalogo_missoes()
    if not catalogo:
        print("  (catalogo de missoes vazio — rode seed_catalogos primeiro)")
        return MatchResult(0, 0, 0, 0, 0)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, missao FROM smo.fracoes "
                "WHERE missao_id IS NULL AND missao IS NOT NULL AND missao <> ''"
            )
            pendentes: list[dict] = [dict(r) for r in cur.fetchall()]

            exatos: int = 0
            fuzzy: int = 0
            ambiguos: int = 0
            sem_match: int = 0

            for row in pendentes:
                texto: str = row["missao"] or ""
                termo: str = normalizar(texto)
                if not termo:
                    sem_match += 1
                    continue

                # 1. exato
                if termo in catalogo:
                    if not dry_run:
                        cur.execute(
                            "UPDATE smo.fracoes SET missao_id = %s WHERE id = %s",
                            (catalogo[termo], row["id"]),
                        )
                    exatos += 1
                    continue

                # 2. fuzzy
                match_id, score, ambiguo = _match_fuzzy(termo, catalogo)
                if ambiguo:
                    ambiguos += 1
                    print(
                        f"  ? AMBIGUO missao='{texto}' score={score} "
                        f"(nao atualizado)"
                    )
                    continue
                if match_id:
                    if not dry_run:
                        cur.execute(
                            "UPDATE smo.fracoes SET missao_id = %s WHERE id = %s",
                            (match_id, row["id"]),
                        )
                    fuzzy += 1
                    print(f"  ~ FUZZY  missao='{texto}' score={score}")
                    continue

                sem_match += 1
                print(f"  - SEM_MATCH missao='{texto}'")

        if not dry_run:
            conn.commit()
        else:
            conn.rollback()

        return MatchResult(
            total_lidos=len(pendentes),
            exatos=exatos, fuzzy=fuzzy,
            ambiguos=ambiguos, sem_match=sem_match,
        )
    finally:
        conn.close()


def backfill_municipios(dry_run: bool = False) -> MatchResult:
    catalogo: dict[str, str] = _carregar_catalogo_municipios()
    if not catalogo:
        print("  (catalogo de municipios vazio — rode seed_catalogos primeiro)")
        return MatchResult(0, 0, 0, 0, 0)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, municipio_nome_raw FROM smo.fracoes "
                "WHERE municipio_id IS NULL "
                "  AND municipio_nome_raw IS NOT NULL "
                "  AND municipio_nome_raw <> ''"
            )
            pendentes: list[dict] = [dict(r) for r in cur.fetchall()]

            exatos: int = 0
            fuzzy: int = 0
            ambiguos: int = 0
            sem_match: int = 0

            for row in pendentes:
                texto: str = row["municipio_nome_raw"] or ""
                termo: str = normalizar(texto)
                if not termo:
                    sem_match += 1
                    continue

                if termo in catalogo:
                    if not dry_run:
                        cur.execute(
                            "UPDATE smo.fracoes SET municipio_id = %s "
                            "WHERE id = %s",
                            (catalogo[termo], row["id"]),
                        )
                    exatos += 1
                    continue

                match_id, score, ambiguo = _match_fuzzy(termo, catalogo)
                if ambiguo:
                    ambiguos += 1
                    print(
                        f"  ? AMBIGUO municipio='{texto}' score={score} "
                        f"(nao atualizado)"
                    )
                    continue
                if match_id:
                    if not dry_run:
                        cur.execute(
                            "UPDATE smo.fracoes SET municipio_id = %s "
                            "WHERE id = %s",
                            (match_id, row["id"]),
                        )
                    fuzzy += 1
                    print(f"  ~ FUZZY  municipio='{texto}' score={score}")
                    continue

                sem_match += 1
                print(f"  - SEM_MATCH municipio='{texto}'")

        if not dry_run:
            conn.commit()
        else:
            conn.rollback()

        return MatchResult(
            total_lidos=len(pendentes),
            exatos=exatos, fuzzy=fuzzy,
            ambiguos=ambiguos, sem_match=sem_match,
        )
    finally:
        conn.close()


def _imprimir_resumo(titulo: str, r: MatchResult) -> None:
    print(f"\n{titulo}:")
    print(f"  total lidos : {r.total_lidos}")
    print(f"  exatos      : {r.exatos}")
    print(f"  fuzzy>=85   : {r.fuzzy}")
    print(f"  ambiguos    : {r.ambiguos}")
    print(f"  sem match   : {r.sem_match}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill de catalogos em smo.fracoes")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="simula sem gravar (rollback no fim)",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        print(
            f"Backfill {'(DRY-RUN)' if args.dry_run else ''} — "
            f"missoes e municipios"
        )
        r_mis = backfill_missoes(dry_run=args.dry_run)
        r_mun = backfill_municipios(dry_run=args.dry_run)
    _imprimir_resumo("MISSOES", r_mis)
    _imprimir_resumo("MUNICIPIOS", r_mun)
    return 0


if __name__ == "__main__":
    sys.exit(main())
