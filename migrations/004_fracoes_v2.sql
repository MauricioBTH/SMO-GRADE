-- Migration 004: evolucao de smo.fracoes com FKs para catalogos + osv + atualizado_em.
-- A coluna textual `missao` (legado) permanece ate a 6.3, para backfill.
-- Idempotente via verificacoes em information_schema.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'smo' AND table_name = 'fracoes'
           AND column_name = 'missao_id'
    ) THEN
        ALTER TABLE smo.fracoes
            ADD COLUMN missao_id UUID REFERENCES smo.missoes(id) ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'smo' AND table_name = 'fracoes'
           AND column_name = 'osv'
    ) THEN
        ALTER TABLE smo.fracoes ADD COLUMN osv VARCHAR(40);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'smo' AND table_name = 'fracoes'
           AND column_name = 'municipio_id'
    ) THEN
        ALTER TABLE smo.fracoes
            ADD COLUMN municipio_id UUID REFERENCES smo.municipios(id) ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'smo' AND table_name = 'fracoes'
           AND column_name = 'municipio_nome_raw'
    ) THEN
        ALTER TABLE smo.fracoes ADD COLUMN municipio_nome_raw VARCHAR(120);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'smo' AND table_name = 'fracoes'
           AND column_name = 'atualizado_em'
    ) THEN
        ALTER TABLE smo.fracoes
            ADD COLUMN atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW();
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_fracoes_missao    ON smo.fracoes(missao_id);
CREATE INDEX IF NOT EXISTS idx_fracoes_municipio ON smo.fracoes(municipio_id);

COMMENT ON COLUMN smo.fracoes.missao IS
    'DEPRECATED 6.2: manter apenas para backfill; preferir missao_id. Remocao planejada para 6.3.';
