-- Migration 007 (Fase 6.4.1): catalogo de unidades operacionais + municipio
-- sede. Resolve o problema de analise por municipio para missoes em quartel
-- (Prontidao, Pernoite, Retorno) que nao trazem municipio na linha de texto:
-- o resolver do catalogo vai derivar o municipio a partir da unidade da fracao.
--
-- Catalogo fechado e pequeno (~7 batalhoes do CPChq + RPMon). Lookup por
-- nome_normalizado tolera variantes '1°BPChq' / '1 BPChq' / '1ºBPChq'.
--
-- Idempotente — padrao de 003/004/005/006: CREATE ... IF NOT EXISTS +
-- INSERT ... ON CONFLICT no seed posterior.

CREATE TABLE IF NOT EXISTS smo.unidades (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome              TEXT NOT NULL,
    nome_normalizado  TEXT NOT NULL UNIQUE,
    municipio_sede_id UUID NOT NULL REFERENCES smo.municipios(id) ON DELETE RESTRICT,
    ativo             BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_unidades_municipio_sede
    ON smo.unidades(municipio_sede_id);
