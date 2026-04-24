-- Migration 009: extincao do papel operador_alei.
--
-- Contexto: decisao 2026-04-24 — alei deixa de ter acesso ao app. AREI
-- centralizado ja absorve o fluxo. Usuarios com papel alei sao removidos
-- e a CHECK constraint de role passa a aceitar apenas gestor/operador_arei.
--
-- Idempotente (DROP ... IF EXISTS + DELETE tolera ausencia).

-- 1. Remove usuarios com papel alei (decisao: delete, nao desativar).
DELETE FROM smo.usuarios WHERE role = 'operador_alei';

-- 2. Substitui CHECK de role — a antiga foi criada inline em 002,
--    Postgres auto-nomeia como `usuarios_role_check`.
ALTER TABLE smo.usuarios DROP CONSTRAINT IF EXISTS usuarios_role_check;
ALTER TABLE smo.usuarios ADD CONSTRAINT usuarios_role_check
    CHECK (role IN ('gestor','operador_arei'));

-- 3. Dropa CHECK "alei_precisa_unidade" — sem alei, obrigatoriedade
--    de unidade fica por conta do codigo da aplicacao (operador_arei
--    tambem tem unidade, mas nao e required a nivel de DB).
ALTER TABLE smo.usuarios DROP CONSTRAINT IF EXISTS alei_precisa_unidade;
