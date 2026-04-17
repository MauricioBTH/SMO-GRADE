import psycopg2
import psycopg2.extras
from flask import current_app


def get_connection() -> psycopg2.extensions.connection:
    db_url = current_app.config["SUPABASE_DB_URL"]
    if not db_url:
        raise RuntimeError("SUPABASE_DB_URL nao configurada")
    return psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)


def init_tables() -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_SQL_CREATE_FRACOES)
            cur.execute(_SQL_CREATE_CABECALHO)
        conn.commit()
    finally:
        conn.close()


_SQL_CREATE_FRACOES = """
CREATE TABLE IF NOT EXISTS fracoes (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    unidade       VARCHAR(50)  NOT NULL,
    data          VARCHAR(30)  NOT NULL,
    turno         VARCHAR(100),
    fracao        VARCHAR(100),
    comandante    VARCHAR(120),
    telefone      VARCHAR(30),
    equipes       INTEGER DEFAULT 0,
    pms           INTEGER DEFAULT 0,
    horario_inicio VARCHAR(50),
    horario_fim   VARCHAR(50),
    missao        TEXT,
    created_at    TIMESTAMPTZ  DEFAULT NOW()
);
"""

_SQL_CREATE_CABECALHO = """
CREATE TABLE IF NOT EXISTS cabecalho (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    unidade           VARCHAR(50)  NOT NULL,
    data              VARCHAR(30)  NOT NULL,
    turno             VARCHAR(100),
    oficial_superior  VARCHAR(120),
    tel_oficial       VARCHAR(80),
    tel_copom         VARCHAR(80),
    operador_diurno   VARCHAR(120),
    tel_op_diurno     VARCHAR(80),
    horario_op_diurno VARCHAR(50),
    operador_noturno  VARCHAR(120),
    tel_op_noturno    VARCHAR(80),
    horario_op_noturno VARCHAR(50),
    efetivo_total     INTEGER DEFAULT 0,
    oficiais          INTEGER DEFAULT 0,
    sargentos         INTEGER DEFAULT 0,
    soldados          INTEGER DEFAULT 0,
    vtrs              INTEGER DEFAULT 0,
    motos             INTEGER DEFAULT 0,
    ef_motorizado     INTEGER DEFAULT 0,
    armas_ace         INTEGER DEFAULT 0,
    armas_portateis   INTEGER DEFAULT 0,
    armas_longas      INTEGER DEFAULT 0,
    animais           INTEGER DEFAULT 0,
    animais_tipo      VARCHAR(50),
    locais_atuacao    TEXT,
    missoes_osv       TEXT,
    created_at        TIMESTAMPTZ  DEFAULT NOW()
);
"""
