-- Migration 001: schema `smo` + movimentacao das tabelas existentes
-- Aplicavel multiplas vezes com seguranca (idempotente).

CREATE SCHEMA IF NOT EXISTS smo;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = 'fracoes'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.tables
         WHERE table_schema = 'smo' AND table_name = 'fracoes'
    ) THEN
        EXECUTE 'ALTER TABLE public.fracoes SET SCHEMA smo';
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = 'cabecalho'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.tables
         WHERE table_schema = 'smo' AND table_name = 'cabecalho'
    ) THEN
        EXECUTE 'ALTER TABLE public.cabecalho SET SCHEMA smo';
    END IF;
END
$$;

-- Redes de seguranca: cria tabelas vazias em smo se nao existirem (novo ambiente).

CREATE TABLE IF NOT EXISTS smo.fracoes (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    unidade        VARCHAR(50)  NOT NULL,
    data           VARCHAR(30)  NOT NULL,
    turno          VARCHAR(100),
    fracao         VARCHAR(100),
    comandante     VARCHAR(120),
    telefone       VARCHAR(30),
    equipes        INTEGER DEFAULT 0,
    pms            INTEGER DEFAULT 0,
    horario_inicio VARCHAR(200),
    horario_fim    VARCHAR(200),
    missao         TEXT,
    created_at     TIMESTAMPTZ  DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS smo.cabecalho (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    unidade            VARCHAR(50)  NOT NULL,
    data               VARCHAR(30)  NOT NULL,
    turno              VARCHAR(100),
    oficial_superior   VARCHAR(120),
    tel_oficial        VARCHAR(80),
    tel_copom          VARCHAR(80),
    operador_diurno    VARCHAR(120),
    tel_op_diurno      VARCHAR(80),
    horario_op_diurno  VARCHAR(50),
    operador_noturno   VARCHAR(120),
    tel_op_noturno     VARCHAR(80),
    horario_op_noturno VARCHAR(50),
    efetivo_total      INTEGER DEFAULT 0,
    oficiais           INTEGER DEFAULT 0,
    sargentos          INTEGER DEFAULT 0,
    soldados           INTEGER DEFAULT 0,
    vtrs               INTEGER DEFAULT 0,
    motos              INTEGER DEFAULT 0,
    ef_motorizado      INTEGER DEFAULT 0,
    armas_ace          INTEGER DEFAULT 0,
    armas_portateis    INTEGER DEFAULT 0,
    armas_longas       INTEGER DEFAULT 0,
    animais            INTEGER DEFAULT 0,
    animais_tipo       VARCHAR(50),
    locais_atuacao     TEXT,
    missoes_osv        TEXT,
    created_at         TIMESTAMPTZ  DEFAULT NOW()
);
