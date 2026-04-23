-- Migration 008 (Fase 6.5.b): uploads + soft-delete em fracoes/cabecalho.
--
-- Motivacao: ate 6.4.1 o save_fracoes era DELETE/INSERT destrutivo por
-- (unidade, data). Operador AREI pode errar a data do texto do escalante
-- e sobrescrever dados validos sem rastreabilidade. A partir daqui toda
-- gravacao passa a ser *versionada*: cria-se 1 upload por (unidade, data),
-- as linhas anteriores ficam soft-deletadas (nao apagadas) e vinculadas
-- ao upload anterior — permitindo restaurar a versao anterior.
--
-- Idempotente: padrao 003-007 (CREATE ... IF NOT EXISTS / ADD COLUMN IF
-- NOT EXISTS). Backfill inline na mesma transacao; so roda se houver
-- linhas orfas (upload_id IS NULL), portanto re-aplicacoes sao no-op.
--
-- Views *_atuais escondem as linhas soft-deletadas para as queries de
-- leitura — regra de design para reduzir risco de regressao ao adicionar
-- nova query em analytics sem lembrar do filtro deletado_em IS NULL.

-- ============================================================
-- 1. Usuario "sistema" — necessario para o backfill e para
--    referenciar uploads sinteticos (origem='backfill').
-- ============================================================
INSERT INTO smo.usuarios (nome, email, senha_hash, role, ativo)
VALUES (
    'Sistema',
    'sistema@smo.local',
    '!INATIVO-SENHA-NAO-USAVEL!',
    'gestor',
    FALSE  -- ativo=FALSE para impedir login pelo login/senha
)
ON CONFLICT (email) DO NOTHING;

-- ============================================================
-- 2. Tabela principal de uploads.
-- ============================================================
CREATE TABLE IF NOT EXISTS smo.uploads (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id     UUID NOT NULL REFERENCES smo.usuarios(id) ON DELETE RESTRICT,
    unidade        TEXT NOT NULL,
    data           TEXT NOT NULL,            -- manter o formato DD/MM/YYYY das demais tabelas
    criado_em      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    origem         TEXT NOT NULL DEFAULT 'whatsapp',
                   -- 'whatsapp' | 'xlsx' | 'edicao' | 'backfill'
    texto_original TEXT,                     -- cru do WhatsApp (NULL para xlsx/backfill)
    substitui_id   UUID NULL REFERENCES smo.uploads(id) ON DELETE SET NULL,
    cancelado_em   TIMESTAMPTZ NULL,
    cancelado_por  UUID NULL REFERENCES smo.usuarios(id) ON DELETE RESTRICT,
    observacao     TEXT
);

CREATE INDEX IF NOT EXISTS idx_uploads_unidade_data
    ON smo.uploads(unidade, data, criado_em DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_uploads_ativo_por_dia
    ON smo.uploads(unidade, data) WHERE cancelado_em IS NULL;

-- ============================================================
-- 3. Colunas de soft-delete + upload_id em tabelas existentes.
--    (ADD COLUMN IF NOT EXISTS = idempotente.)
-- ============================================================
ALTER TABLE smo.fracoes
    ADD COLUMN IF NOT EXISTS upload_id    UUID NULL REFERENCES smo.uploads(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS deletado_em  TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS deletado_por UUID NULL REFERENCES smo.usuarios(id) ON DELETE SET NULL;

ALTER TABLE smo.cabecalho
    ADD COLUMN IF NOT EXISTS upload_id    UUID NULL REFERENCES smo.uploads(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS deletado_em  TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS deletado_por UUID NULL REFERENCES smo.usuarios(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_fracoes_ativas
    ON smo.fracoes(unidade, data) WHERE deletado_em IS NULL;
CREATE INDEX IF NOT EXISTS idx_cabecalho_ativo
    ON smo.cabecalho(unidade, data) WHERE deletado_em IS NULL;
CREATE INDEX IF NOT EXISTS idx_fracoes_upload   ON smo.fracoes(upload_id);
CREATE INDEX IF NOT EXISTS idx_cabecalho_upload ON smo.cabecalho(upload_id);

-- ============================================================
-- 4. Backfill — cria 1 upload sintetico por (unidade, data) existente
--    e vincula as linhas. Idempotente: so pega orfaos (upload_id IS NULL).
-- ============================================================
WITH agrupados_fracoes AS (
    SELECT DISTINCT unidade, data
      FROM smo.fracoes
     WHERE upload_id IS NULL
),
agrupados_cabecalho AS (
    SELECT DISTINCT unidade, data
      FROM smo.cabecalho
     WHERE upload_id IS NULL
),
agrupados AS (
    SELECT unidade, data FROM agrupados_fracoes
    UNION
    SELECT unidade, data FROM agrupados_cabecalho
),
sistema AS (
    SELECT id FROM smo.usuarios WHERE email = 'sistema@smo.local' LIMIT 1
),
inseridos AS (
    INSERT INTO smo.uploads (usuario_id, unidade, data, origem, observacao)
    SELECT
        (SELECT id FROM sistema),
        a.unidade,
        a.data,
        'backfill',
        'Fase 6.5 — upload sintetico agrupando linhas pre-existentes'
    FROM agrupados a
    RETURNING id, unidade, data
)
UPDATE smo.fracoes f
   SET upload_id = i.id
  FROM inseridos i
 WHERE f.unidade = i.unidade
   AND f.data    = i.data
   AND f.upload_id IS NULL;

-- Reaproveita os uploads recem-criados para o cabecalho.
UPDATE smo.cabecalho c
   SET upload_id = u.id
  FROM smo.uploads u
 WHERE u.origem  = 'backfill'
   AND u.unidade = c.unidade
   AND u.data    = c.data
   AND c.upload_id IS NULL;

-- ============================================================
-- 5. Views de conveniencia para queries de leitura.
--    Padrao: toda query nova usa _atuais em vez de FROM smo.fracoes
--    — reduz risco de esquecer o filtro deletado_em IS NULL.
-- ============================================================
CREATE OR REPLACE VIEW smo.fracoes_atuais AS
    SELECT * FROM smo.fracoes WHERE deletado_em IS NULL;

CREATE OR REPLACE VIEW smo.cabecalho_atuais AS
    SELECT * FROM smo.cabecalho WHERE deletado_em IS NULL;
