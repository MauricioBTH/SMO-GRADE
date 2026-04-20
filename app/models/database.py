from __future__ import annotations

import psycopg2
import psycopg2.extensions
import psycopg2.extras
from flask import current_app


def get_connection() -> psycopg2.extensions.connection:
    db_url: str = current_app.config["DATABASE_URL"]
    if not db_url:
        raise RuntimeError("DATABASE_URL nao configurada")
    return psycopg2.connect(
        db_url, cursor_factory=psycopg2.extras.RealDictCursor
    )
