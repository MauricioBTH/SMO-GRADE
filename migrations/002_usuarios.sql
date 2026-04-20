-- Migration 002: tabela smo.usuarios (auth + roles)

CREATE TABLE IF NOT EXISTS smo.usuarios (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome         VARCHAR(120) NOT NULL,
    email        VARCHAR(200) UNIQUE NOT NULL,
    senha_hash   TEXT NOT NULL,
    totp_secret  TEXT,
    totp_ativo   BOOLEAN NOT NULL DEFAULT FALSE,
    role         VARCHAR(20) NOT NULL
                 CHECK (role IN ('gestor','operador_arei','operador_alei')),
    unidade      VARCHAR(50),
    ativo        BOOLEAN NOT NULL DEFAULT TRUE,
    ultimo_login TIMESTAMPTZ,
    criado_em    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT alei_precisa_unidade
        CHECK (role <> 'operador_alei' OR unidade IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_usuarios_email ON smo.usuarios(email);
