"""Backup CSV das tabelas operacionais SMO (pre-limpeza Fase 6.5.c).

Exporta via COPY TO CSV cada tabela que sera truncada pelo
limpar_dados_operacionais.py, pra dar um cinto-de-seguranca reversivel.
Catalogos (unidades/municipios/missoes/bpms/crpms) + usuarios nao entram:
permanecem intactos.

Uso: python -m scripts.backup_dados_operacionais

Gera backups/SMO_<timestamp>/*.csv. Restauracao manual via COPY FROM.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402
from app.models.database import get_connection  # noqa: E402

TABELAS: list[str] = [
    "smo.uploads",
    "smo.cabecalho",
    "smo.fracoes",
    "smo.fracao_missoes",
    "smo.fracao_missao_bpms",
]


def backup() -> int:
    ts: str = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino: Path = Path("backups") / f"SMO_{ts}"
    destino.mkdir(parents=True, exist_ok=True)

    total_rows: int = 0
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for tabela in TABELAS:
                arq: Path = destino / (tabela.replace(".", "__") + ".csv")
                with arq.open("wb") as f:
                    cur.copy_expert(
                        f"COPY {tabela} TO STDOUT WITH CSV HEADER",
                        f,
                    )
                cur.execute(f"SELECT COUNT(*) AS n FROM {tabela}")
                row = cur.fetchone()
                n: int = int(row["n"]) if row else 0
                total_rows += n
                size_kb: float = arq.stat().st_size / 1024
                print(f"  {tabela:30s} {n:>6} rows  {size_kb:>8.1f} KB  -> {arq.name}")
    finally:
        conn.close()

    print()
    print(f"Backup completo em {destino}/ ({total_rows} rows no total).")
    return 0


def main() -> int:
    app = create_app()
    with app.app_context():
        print(f"Backup SMO (dados operacionais) - {datetime.now().isoformat()}")
        print()
        return backup()


if __name__ == "__main__":
    sys.exit(main())
