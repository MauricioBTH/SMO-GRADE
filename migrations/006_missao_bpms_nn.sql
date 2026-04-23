-- Migration 006 (Fase 6.4): N:N entre vertices (fracao_missoes) e BPMs.
--
-- Motivacao: uma mesma missao em Porto Alegre pode cobrir multiplos BPMs no
-- mesmo vertice, ex.: "Policiamento Ostensivo Municipio: Porto Alegre
-- (20 BPM, 1 BPM)". O modelo 1:1 via smo.fracao_missoes.bpm_id nao expressa
-- isso — a coluna captura apenas o primeiro BPM.
--
-- Estrategia:
--   1) Tabela intermediaria smo.fracao_missao_bpms(fracao_missao_id, bpm_id)
--      com PK composto. CASCADE no vertice pai (apagar vertice limpa seus
--      BPMs); RESTRICT no bpm_id (nao deletamos BPM em uso). Fonte de verdade.
--   2) Backfill idempotente de toda fracao_missoes.bpm_id IS NOT NULL.
--   3) smo.fracao_missoes.bpm_id permanece como cache do 1o BPM (para analytics
--      legadas que ainda leem o singular) — DEPRECATED; remocao planejada 6.5.
--
-- Idempotente — padrao de 003/004/005: CREATE ... IF NOT EXISTS + INSERT ON CONFLICT.

CREATE TABLE IF NOT EXISTS smo.fracao_missao_bpms (
    fracao_missao_id UUID NOT NULL REFERENCES smo.fracao_missoes(id) ON DELETE CASCADE,
    bpm_id           UUID NOT NULL REFERENCES smo.bpms(id)           ON DELETE RESTRICT,
    criado_em        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (fracao_missao_id, bpm_id)
);

-- PK ja cobre (fracao_missao_id, bpm_id); este indice acelera o caminho reverso
-- ("todos os vertices que cobrem o BPM X") usado por analytics futuras.
CREATE INDEX IF NOT EXISTS idx_fmb_bpm ON smo.fracao_missao_bpms(bpm_id);

-- Backfill: cada vertice com bpm_id populado vira uma linha na tabela
-- intermediaria. ON CONFLICT garante reentrancia caso a migration rode 2x.
INSERT INTO smo.fracao_missao_bpms (fracao_missao_id, bpm_id)
SELECT id, bpm_id
  FROM smo.fracao_missoes
 WHERE bpm_id IS NOT NULL
ON CONFLICT DO NOTHING;

-- Fonte de verdade passa a ser smo.fracao_missao_bpms. A coluna bpm_id em
-- fracao_missoes fica como cache do 1o BPM (para nao quebrar analytics que
-- ainda leem o singular). Drop planejado em 6.5.
COMMENT ON COLUMN smo.fracao_missoes.bpm_id IS
    'DEPRECATED 6.4 -> smo.fracao_missao_bpms (fonte de verdade). Cache do 1o BPM para analytics legadas; remocao planejada em 6.5.';
