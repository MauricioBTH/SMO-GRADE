"""Executor ad-hoc de SQL para diagnostico manual.

Uso:
    python -m scripts.sql "SELECT origem, COUNT(*) FROM smo.uploads GROUP BY origem"
    python -m scripts.sql < arquivo.sql

Nao usar em producao pra qualquer coisa alem de SELECT — nao ha
confirmacao antes de rodar. Pensado pra validacao manual da Fase 6.5
sem precisar de psql instalado.
"""
from __future__ import annotations

import sys
from typing import Any

from app import create_app
from app.models.database import get_connection


def _executar(sql: str) -> None:
    app = create_app()
    with app.app_context():
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                if cur.description is None:
                    print(f"OK — {cur.rowcount} linha(s) afetada(s).")
                    conn.commit()
                    return
                cols: list[str] = [d[0] for d in cur.description]
                rows: list[dict[str, Any]] = [dict(r) for r in cur.fetchall()]
            if not rows:
                print("(sem linhas)")
                return
            larguras: dict[str, int] = {
                c: max(len(c), max(len(str(r.get(c, ""))) for r in rows))
                for c in cols
            }
            sep: str = " | ".join("-" * larguras[c] for c in cols)
            print(" | ".join(c.ljust(larguras[c]) for c in cols))
            print(sep)
            for r in rows:
                print(" | ".join(str(r.get(c, "")).ljust(larguras[c]) for c in cols))
            print(f"\n({len(rows)} linha(s))")
        finally:
            conn.close()


def main() -> int:
    if len(sys.argv) > 1:
        sql: str = " ".join(sys.argv[1:])
    else:
        sql = sys.stdin.read()
    sql = sql.strip()
    if not sql:
        print("ERRO: nenhum SQL fornecido.", file=sys.stderr)
        return 1
    _executar(sql)
    return 0


if __name__ == "__main__":
    sys.exit(main())
