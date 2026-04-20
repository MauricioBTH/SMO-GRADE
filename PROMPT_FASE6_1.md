# Prompt — Fase 6.1 (Migrations, Schema `smo`, Auth + Roles)

Cole este prompt em uma nova conversa com Claude Code para iniciar a Entrega 6.1.

---

Você vai implementar a **Entrega 6.1** do sistema SMO-GRADE (Sistema C2 do CPChq — Brigada Militar RS). Antes de qualquer código, leia a fonte de verdade arquitetural: `ARQUITETURA.md` na raiz do repositório. Todas as decisões de produto, modelo de dados, infra, roles e fluxos estão consolidadas lá.

## Princípios inegociáveis (obrigatórios em todo código)

1. **Tipagem forte** — sem `Any`, sem casts cegos, sem `unknown`/`Record` genérico. Use `TypedDict`, `dataclass`, `Protocol`, tipos específicos. Em Python, `from __future__ import annotations` + tipos de retorno explícitos em toda função.
2. **Modularidade máxima** — nenhum arquivo ultrapassa **500 LOC**. Se um módulo crescer, divida por responsabilidade antes de continuar.
3. **Segurança ativa** — sanitização de toda entrada, prepared statements (parâmetros `%(...)s` no psycopg2, nunca f-string em SQL), escape em templates Jinja2 (autoescape ligado), hash de senha com bcrypt (não sha/md5), TOTP via `pyotp`, rate limit em endpoints sensíveis. Nada passa sem validar.
4. **Front burro, lógica no backend** — cálculos, agregações, derivações e decisões SEMPRE em Python. Frontend (Jinja2 + JS vanilla) só renderiza dados prontos vindos do JSON. Nenhum cálculo de regra de negócio em JS.
5. **Design elegante, minimalista, intuitivo** — sem poluição visual, tipografia clara, affordances óbvias. Siga o estilo existente dos templates em `app/templates/`.
6. **Auditoria de conformidade ao final** — antes de declarar a entrega pronta, emita um relatório explícito: arquivo por arquivo, LOC, pontos de tipagem, pontos de segurança, e autoavaliação contra estes 6 princípios.

## Contexto rápido

- **Stack atual**: Flask 3.1 + psycopg2 + Supabase (Postgres remoto). Ver `requirements.txt`.
- **Modelo atual**: Flask roda local no PC do operador regional, DB no Supabase. Sem auth nenhuma hoje.
- **Tabelas atuais** (em schema `public`): `fracoes`, `cabecalho`. Ver `app/models/database.py`.
- **Env var atual**: `SUPABASE_DB_URL` em `app/config.py` — será renomeada nesta entrega.

## Escopo da Entrega 6.1 (o que está dentro)

### 1. Estrutura de migrations

- Criar diretório `migrations/` com scripts SQL numerados: `001_init_schema_smo.sql`, `002_usuarios.sql`.
- Criar runner Python `scripts/migrate.py` que:
  - Lê tabela `smo.schema_migrations` (id, nome, aplicada_em) — cria se não existe
  - Aplica migrations pendentes em ordem
  - Idempotente (rodar 2x não duplica)
- Substituir a chamada de `init_tables()` hardcoded em `app/__init__.py` (se existir) por invocação ao runner.

### 2. Migration 001 — Schema `smo` + movimentação

- `CREATE SCHEMA IF NOT EXISTS smo;`
- `ALTER TABLE public.fracoes SET SCHEMA smo;`
- `ALTER TABLE public.cabecalho SET SCHEMA smo;`
- Ajustar todo SQL em `app/services/supabase_service.py` (renomear para `db_service.py`) para usar `smo.fracoes` e `smo.cabecalho`.

### 3. Migration 002 — `smo.usuarios`

```sql
CREATE TABLE smo.usuarios (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nome          VARCHAR(120) NOT NULL,
  email         VARCHAR(200) UNIQUE NOT NULL,
  senha_hash    TEXT NOT NULL,
  totp_secret   TEXT,
  totp_ativo    BOOLEAN NOT NULL DEFAULT FALSE,
  role          VARCHAR(20) NOT NULL CHECK (role IN ('gestor','operador_arei','operador_alei')),
  unidade       VARCHAR(50),        -- NULL para gestor e arei; obrigatório para alei
  ativo         BOOLEAN NOT NULL DEFAULT TRUE,
  ultimo_login  TIMESTAMPTZ,
  criado_em     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT alei_precisa_unidade
    CHECK (role <> 'operador_alei' OR unidade IS NOT NULL)
);
CREATE INDEX idx_usuarios_email ON smo.usuarios(email);
```

### 4. Renomear env var

- `SUPABASE_DB_URL` → `DATABASE_URL` em `app/config.py`, `.env.example`, e qualquer referência.
- Sem fallback para nome antigo — migração limpa.

### 5. Dependências novas em `requirements.txt`

- `flask-login==0.6.3`
- `bcrypt==4.2.1`
- `pyotp==2.9.0`
- `qrcode[pil]==8.0` (para gerar QR do TOTP no setup)
- `flask-limiter==3.8.0`

### 6. Modelo `User`

- `app/models/user.py` — classe `User(UserMixin)` com `id`, `nome`, `email`, `role`, `unidade`, `totp_ativo`, `ativo`.
- `app/services/user_service.py` — CRUD: `get_by_id`, `get_by_email`, `create`, `update`, `desativar`, `set_totp_secret`, `verificar_senha`, `registrar_login`. Tipagem estrita.
- Integração com Flask-Login: `user_loader`.

### 7. Rotas de autenticação

- `app/routes/auth.py`:
  - `GET/POST /login` — formulário email + senha; se `totp_ativo`, redireciona para `/login/2fa`
  - `GET/POST /login/2fa` — campo TOTP 6 dígitos
  - `GET/POST /setup-2fa` — mostra QR code (primeiro acesso de Gestor/AREI)
  - `POST /logout`
- Sessão expira em 8 horas (`PERMANENT_SESSION_LIFETIME`).
- Rate limit: 5 tentativas/min/IP em `/login` e `/login/2fa`.
- 2FA **obrigatório** para Gestor e Operador AREI. **Opcional** para ALEI.

### 8. Decoradores de autorização

- `app/auth/decorators.py`:
  - `@login_required` (do flask-login, já)
  - `@role_required(['gestor'])` — lista de roles permitidos, 403 caso contrário
  - `@unidade_match_required` — para rotas que recebem `unidade` na URL/form e operador é ALEI, valida que `current_user.unidade == unidade`. Gestor e AREI passam livres.

### 9. Templates (elegantes, minimalistas)

- `app/templates/auth/login.html`
- `app/templates/auth/login_2fa.html`
- `app/templates/auth/setup_2fa.html` — exibe QR code inline + código manual
- Reusar `base.html` existente. Autoescape Jinja ligado.

### 10. Tela `/admin/usuarios` (Gestor apenas)

- Listar usuários com filtros por role/unidade/ativo
- Botões: criar, editar, desativar, resetar 2FA
- `app/routes/admin.py` + `app/templates/admin/usuarios.html`
- Toda lógica de permissão no backend (decoradores). Frontend só renderiza.

### 11. Seed inicial de Gestor

- `scripts/seed_gestor.py` — recebe email + senha via prompt interativo, cria o primeiro Gestor. Senha com bcrypt, `totp_ativo=FALSE` (ele configura no primeiro login). Roda uma vez.

### 12. Proteção de rotas existentes

- Todas as rotas em `app/routes/operador.py`, `app/routes/analista.py`, `app/routes/api.py` ganham `@login_required` e role apropriado:
  - Upload/inserção: `operador_arei` ou `gestor` (alei entra depois na 6.3)
  - Painel do analista: qualquer role autenticado
  - Admin: `gestor`

### 13. Testes

- `tests/test_auth.py`:
  - Login OK com credenciais corretas
  - Login falha com senha errada
  - Rate limit bloqueia após 5 tentativas
  - 2FA válido passa, inválido nega
  - Decorador de role retorna 403 para role errado
  - ALEI não consegue acessar rota de outra unidade

### 14. Auditoria final

Ao terminar, produza um relatório em `AUDITORIA_6_1.md` na raiz:

- Lista de arquivos novos/modificados com LOC de cada
- Arquivos que passam dos 500 LOC (idealmente zero)
- Pontos de tipagem: qualquer uso de `Any`, `dict` sem parâmetros, etc., ou "nenhum"
- Pontos de segurança: queries parametrizadas, hash bcrypt, TOTP validado server-side, rate limit ativo, autoescape Jinja — ou as exceções
- Autoavaliação contra os 6 princípios inegociáveis — passou/falhou por princípio, com justificativa

## O que NÃO está em escopo da 6.1 (não faça)

- Matriz nova `Missão:`/`OSv:`/`Município:` — é Entrega 6.2
- Catálogo curado de missões + match fuzzy — 6.2
- Charts novos por missão/município — 6.2
- Form web ALEI + gestão de catálogo — 6.3
- Deploy no Oracle Cloud — 6.3
- Audit_log via triggers — 6.5 (hardening militar)

## Como operar

- Use o TodoWrite para rastrear cada item do escopo; marque em andamento e concluído ao longo da execução.
- Antes de editar um arquivo existente, leia-o.
- Prefira `Edit` a `Write` em arquivos existentes. Só crie arquivos quando indispensável.
- Rode os testes ao final e confirme verde antes da auditoria.
- Não toque em nada fora do escopo listado.
- Ao final, pare e aguarde revisão humana antes de seguir para 6.2.
