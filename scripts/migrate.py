"""Runner de migrations SQL numeradas.

Uso:
    python -m scripts.migrate

Le arquivos em ./migrations/NNN_*.sql, aplica os pendentes em ordem,
registra em smo.schema_migrations. Idempotente.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg2
import psycopg2.extensions
from dotenv import load_dotenv

load_dotenv()

ROOT_DIR: Path = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR: Path = ROOT_DIR / "migrations"
MIGRATION_FILE_RE: re.Pattern[str] = re.compile(r"^(\d{3})_[A-Za-z0-9_\-]+\.sql$")


@dataclass(frozen=True)
class Migration:
    numero: str
    nome: str
    caminho: Path


def _database_url() -> str:
    url: str = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL nao configurada no ambiente")
    return url


def _listar_migrations() -> list[Migration]:
    if not MIGRATIONS_DIR.is_dir():
        raise RuntimeError(f"Diretorio de migrations nao encontrado: {MIGRATIONS_DIR}")

    migrations: list[Migration] = []
    for arquivo in sorted(MIGRATIONS_DIR.iterdir()):
        if not arquivo.is_file():
            continue
        match = MIGRATION_FILE_RE.match(arquivo.name)
        if not match:
            continue
        migrations.append(
            Migration(numero=match.group(1), nome=arquivo.name, caminho=arquivo)
        )
    return migrations


def _preparar_tabela_controle(conn: psycopg2.extensions.connection) -> None:
    with conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS smo")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS smo.schema_migrations (
                id         TEXT PRIMARY KEY,
                nome       TEXT NOT NULL,
                aplicada_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    conn.commit()


def _migrations_aplicadas(conn: psycopg2.extensions.connection) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM smo.schema_migrations")
        return {row[0] for row in cur.fetchall()}


def _aplicar(conn: psycopg2.extensions.connection, migration: Migration) -> None:
    sql: str = migration.caminho.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
        cur.execute(
            "INSERT INTO smo.schema_migrations (id, nome) VALUES (%s, %s)",
            (migration.numero, migration.nome),
        )
    conn.commit()


def run() -> int:
    url: str = _database_url()
    conn: psycopg2.extensions.connection = psycopg2.connect(url)
    try:
        _preparar_tabela_controle(conn)
        aplicadas: set[str] = _migrations_aplicadas(conn)
        pendentes: list[Migration] = [
            m for m in _listar_migrations() if m.numero not in aplicadas
        ]
        if not pendentes:
            print("Nenhuma migration pendente.")
            return 0
        for m in pendentes:
            print(f"Aplicando {m.nome} ...")
            try:
                _aplicar(conn, m)
            except psycopg2.Error as exc:
                conn.rollback()
                print(f"ERRO em {m.nome}: {exc}", file=sys.stderr)
                return 1
            print(f"  OK ({m.numero})")
        print(f"{len(pendentes)} migration(s) aplicada(s).")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(run())
