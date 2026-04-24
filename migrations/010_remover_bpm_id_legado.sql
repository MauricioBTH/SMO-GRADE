-- Migration 010: remover coluna legada smo.fracao_missoes.bpm_id.
--
-- A coluna bpm_id era cache do 1o BPM criado na Fase 6.4 para nao quebrar
-- analytics legadas durante a migracao pra N:N. Desde 6.4 a fonte de
-- verdade e smo.fracao_missao_bpms; analytics_catalogos.py ja le apenas
-- da tabela N:N (grep confirma zero consumidores).
--
-- Esta migration dropa: CHECK fm_em_quartel_sem_bpm, INDEX idx_fm_bpm,
-- COLUMN bpm_id. A invariante "em_quartel=TRUE => sem BPMs" migra para
-- a camada Python (db_service_save.py ja garantia isso — zera bpm_ids).
--
-- Idempotente via IF EXISTS.

ALTER TABLE smo.fracao_missoes
    DROP CONSTRAINT IF EXISTS fm_em_quartel_sem_bpm;

DROP INDEX IF EXISTS smo.idx_fm_bpm;

ALTER TABLE smo.fracao_missoes
    DROP COLUMN IF EXISTS bpm_id;
