-- Migration 005 (Fase 6.3): modelo N:N entre fracoes e missoes, + catalogo smo.bpms.
--
-- Motivacao: 70% das fracoes executam 2-3 missoes sequenciais no mesmo turno
-- (mesmo efetivo/comando). O modelo 1:1 em smo.fracoes invisibilizava isso.
-- Agora uma fracao tem N vertices em smo.fracao_missoes, cada um com seu
-- municipio e (se POA fora de quartel) BPM.
--
-- Idempotente — padrao de 003/004: CREATE ... IF NOT EXISTS + DO $$ ... $$.

CREATE TABLE IF NOT EXISTS smo.bpms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo VARCHAR(10) NOT NULL UNIQUE,
    numero SMALLINT NOT NULL UNIQUE,
    municipio_id UUID NOT NULL REFERENCES smo.municipios(id) ON DELETE RESTRICT,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bpms_municipio ON smo.bpms(municipio_id);

CREATE TABLE IF NOT EXISTS smo.fracao_missoes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fracao_id UUID NOT NULL REFERENCES smo.fracoes(id) ON DELETE CASCADE,
    ordem SMALLINT NOT NULL,
    missao_id UUID REFERENCES smo.missoes(id) ON DELETE RESTRICT,
    missao_nome_raw VARCHAR(300) NOT NULL,
    municipio_id UUID NOT NULL REFERENCES smo.municipios(id) ON DELETE RESTRICT,
    bpm_id UUID REFERENCES smo.bpms(id) ON DELETE RESTRICT,
    em_quartel BOOLEAN NOT NULL DEFAULT FALSE,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (fracao_id, ordem)
);

-- Invariante dura: bpm_id populado <=> municipio POA AND nao em quartel.
-- CHECK so valida que em_quartel=TRUE implica bpm_id NULL. A ligacao
-- municipio=POA e validada na camada Python (catalogo).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
         WHERE table_schema = 'smo'
           AND table_name = 'fracao_missoes'
           AND constraint_name = 'fm_em_quartel_sem_bpm'
    ) THEN
        ALTER TABLE smo.fracao_missoes
            ADD CONSTRAINT fm_em_quartel_sem_bpm
            CHECK (NOT (em_quartel = TRUE AND bpm_id IS NOT NULL));
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_fm_fracao    ON smo.fracao_missoes(fracao_id);
CREATE INDEX IF NOT EXISTS idx_fm_missao    ON smo.fracao_missoes(missao_id);
CREATE INDEX IF NOT EXISTS idx_fm_municipio ON smo.fracao_missoes(municipio_id);
CREATE INDEX IF NOT EXISTS idx_fm_bpm       ON smo.fracao_missoes(bpm_id);

-- Colunas legadas de smo.fracoes ficam DEPRECATED — drop planejado em 6.5.
-- Comentarios idempotentes (COMMENT ON ... pode ser reaplicado sem efeito
-- colateral; o catch de "coluna inexistente" ficaria no exception handler
-- abaixo caso a 004 nao tenha rodado ainda, mas a ordem das migrations garante).
COMMENT ON COLUMN smo.fracoes.missao             IS 'DEPRECATED 6.3 -> fracao_missoes.missao_nome_raw';
COMMENT ON COLUMN smo.fracoes.missao_id          IS 'DEPRECATED 6.3 -> fracao_missoes.missao_id';
COMMENT ON COLUMN smo.fracoes.municipio_id       IS 'DEPRECATED 6.3 -> fracao_missoes.municipio_id';
COMMENT ON COLUMN smo.fracoes.municipio_nome_raw IS 'DEPRECATED 6.3 -> fracao_missoes.municipio_nome_raw';
