-- Migration 003: catalogos normativos (CRPMs, municipios, missoes)
-- Idempotente: usa IF NOT EXISTS onde possivel. Ordem I..XXI do Art. 3o.

CREATE TABLE IF NOT EXISTS smo.crpms (
    id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sigla  VARCHAR(20) UNIQUE NOT NULL,
    nome   VARCHAR(160) NOT NULL,
    sede   VARCHAR(80),
    ordem  SMALLINT NOT NULL UNIQUE,
    ativo  BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS smo.municipios (
    id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome      VARCHAR(120) NOT NULL,
    crpm_id   UUID NOT NULL REFERENCES smo.crpms(id) ON DELETE RESTRICT,
    ativo     BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (nome, crpm_id)
);

CREATE INDEX IF NOT EXISTS idx_municipios_crpm ON smo.municipios(crpm_id);
CREATE INDEX IF NOT EXISTS idx_municipios_nome ON smo.municipios(LOWER(nome));

CREATE TABLE IF NOT EXISTS smo.missoes (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome       VARCHAR(120) UNIQUE NOT NULL,
    descricao  TEXT,
    ativo      BOOLEAN NOT NULL DEFAULT TRUE,
    criada_em  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_missoes_nome ON smo.missoes(LOWER(nome));
