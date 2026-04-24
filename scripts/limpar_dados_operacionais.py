"""Limpa dados operacionais SMO (Fase 6.5.c — reset pre-Fase 7).

Motivacao: as escalas historicas nao tem municipio/missao solidos (apenas 9 de
3483 fracoes usam o modelo N:N). Backfill nao e viavel, entao zeramos os
operacionais pra comecar com dados bons pelo modelo canonico.

Preservado: catalogos (unidades, municipios, missoes, bpms, crpms) + usuarios.
Apagado: uploads + cabecalho + fracoes + fracao_missoes + fracao_missao_bpms.

Uso: python -m scripts.limpar_dados_operacionais
Pre-requisito: ter rodado scripts.backup_dados_operacionais antes.
Idempotente: pode rodar multiplas vezes sem efeito colateral (tabelas ja vazias).
"""
from __future__ import annotations

import sys
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402
from app.models.database import get_connection  # noqa: E402

TABELAS_OPERACIONAIS: list[str] = [
    "smo.fracao_missao_bpms",
    "smo.fracao_missoes",
    "smo.fracoes",
    "smo.cabecalho",
    "smo.uploads",
]

CATALOGOS_PRESERVADOS: list[str] = [
    "smo.unidades",
    "smo.municipios",
    "smo.missoes",
    "smo.bpms",
    "smo.crpms",
]


def _contar(cur, tabela: str) -> int:
    cur.execute(f"SELECT COUNT(*) AS n FROM {tabela}")
    row = cur.fetchone()
    return int(row["n"]) if row else 0


def limpar() -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            print("Antes da limpeza:")
            antes_op: dict[str, int] = {}
            for t in TABELAS_OPERACIONAIS:
                n = _contar(cur, t)
                antes_op[t] = n
                print(f"  {t:32s} {n:>6} rows")

            print()
            print("Catalogos preservados (nao serao tocados):")
            cat_antes: dict[str, int] = {}
            for t in CATALOGOS_PRESERVADOS:
                n = _contar(cur, t)
                cat_antes[t] = n
                print(f"  {t:32s} {n:>6} rows")

            print()
            print("Executando TRUNCATE CASCADE...")
            alvo: str = ", ".join(TABELAS_OPERACIONAIS)
            cur.execute(f"TRUNCATE {alvo} RESTART IDENTITY CASCADE")
            conn.commit()

            print()
            print("Depois da limpeza:")
            for t in TABELAS_OPERACIONAIS:
                n = _contar(cur, t)
                status: str = "OK" if n == 0 else "FALHOU"
                print(f"  {t:32s} {n:>6} rows  [{status}]")

            print()
            print("Validando catalogos (devem estar inalterados):")
            todos_ok: bool = True
            for t in CATALOGOS_PRESERVADOS:
                n = _contar(cur, t)
                ok: bool = n == cat_antes[t]
                todos_ok = todos_ok and ok
                status = "OK" if ok else f"ALTERADO! antes={cat_antes[t]}"
                print(f"  {t:32s} {n:>6} rows  [{status}]")

            if not todos_ok:
                print()
                print("ATENCAO: algum catalogo foi alterado — verifique!")
                return 1

        return 0
    except Exception as e:
        conn.rollback()
        print(f"ERRO: {e}")
        print("Transacao revertida.")
        return 1
    finally:
        conn.close()


def main() -> int:
    app = create_app()
    with app.app_context():
        print(f"Limpeza SMO (dados operacionais) - {datetime.now().isoformat()}")
        print()
        return limpar()


if __name__ == "__main__":
    sys.exit(main())
