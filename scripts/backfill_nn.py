"""Backfill: cria 1 vertice em smo.fracao_missoes para cada smo.fracoes existente.

Uso:
    python -m scripts.backfill_nn [--dry-run]

Estrategia:
  Para cada fracao com `municipio_id IS NOT NULL` e sem vertice em
  `fracao_missoes`, cria 1 vertice com ordem=1 copiando:
    - missao_nome_raw <- fracoes.missao
    - missao_id       <- fracoes.missao_id (pode ser NULL)
    - municipio_id    <- fracoes.municipio_id (obrigatorio — regra 6.3)
    - bpm_id          <- NULL (nao temos como inferir retroativamente)
    - em_quartel      <- FALSE (idem — operador corrige caso a caso se
                                necessario no futuro)

Fracoes legadas com `municipio_id IS NULL` ficam fora do backfill — elas
precisam ser resolvidas via backfill_missoes / triagem manual antes de entrar
no modelo N:N. O script reporta essas pendencias.

Idempotente: `WHERE NOT EXISTS (... fracao_missoes WHERE fracao_id = ...)`
garante que rodar 2x nao duplica vertices.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402
from app.models.database import get_connection  # noqa: E402


@dataclass(frozen=True)
class BackfillResult:
    total_fracoes: int
    criados: int
    ja_existiam: int
    sem_municipio: int


def backfill_fracao_missoes(dry_run: bool = False) -> BackfillResult:
    """Cria 1 vertice por fracao existente que tenha municipio_id."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*)::int AS n FROM smo.fracoes")
            row = cur.fetchone()
            total: int = int(row["n"]) if row else 0

            cur.execute(
                "SELECT COUNT(*)::int AS n FROM smo.fracoes f "
                " WHERE f.municipio_id IS NULL"
            )
            row = cur.fetchone()
            sem_municipio: int = int(row["n"]) if row else 0

            cur.execute(
                "SELECT COUNT(*)::int AS n FROM smo.fracoes f "
                " WHERE EXISTS ("
                "   SELECT 1 FROM smo.fracao_missoes fm "
                "    WHERE fm.fracao_id = f.id AND fm.ordem = 1"
                " )"
            )
            row = cur.fetchone()
            ja_existiam: int = int(row["n"]) if row else 0

            cur.execute(
                "INSERT INTO smo.fracao_missoes ("
                "    fracao_id, ordem, missao_id, missao_nome_raw, "
                "    municipio_id, bpm_id, em_quartel"
                ") "
                "SELECT f.id, 1::SMALLINT, f.missao_id, "
                "       COALESCE(NULLIF(f.missao, ''), '(sem missao)'), "
                "       f.municipio_id, NULL::UUID, FALSE "
                "  FROM smo.fracoes f "
                " WHERE f.municipio_id IS NOT NULL "
                "   AND NOT EXISTS ("
                "       SELECT 1 FROM smo.fracao_missoes fm "
                "        WHERE fm.fracao_id = f.id AND fm.ordem = 1"
                "   ) "
                "RETURNING id"
            )
            criados: int = len(cur.fetchall())

        if dry_run:
            conn.rollback()
        else:
            conn.commit()

        return BackfillResult(
            total_fracoes=total,
            criados=criados,
            ja_existiam=ja_existiam,
            sem_municipio=sem_municipio,
        )
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill smo.fracoes -> smo.fracao_missoes (1 vertice)."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="simula sem gravar (rollback no fim)",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        print(f"Backfill N:N{' (DRY-RUN)' if args.dry_run else ''}")
        r = backfill_fracao_missoes(dry_run=args.dry_run)

    print("\nRESUMO:")
    print(f"  total de fracoes          : {r.total_fracoes}")
    print(f"  vertices criados          : {r.criados}")
    print(f"  ja existiam (idempotente) : {r.ja_existiam}")
    print(f"  sem municipio (puladas)   : {r.sem_municipio}")
    if r.sem_municipio:
        print(
            "\n  AVISO: fracoes sem municipio_id nao entram no modelo N:N. "
            "Resolva via triagem ou backfill_missoes antes de prosseguir."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
