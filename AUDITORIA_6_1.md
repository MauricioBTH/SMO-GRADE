# AUDITORIA — Entrega 6.1

Data: 2026-04-19
Escopo: Migrations + schema `smo` + autenticacao (email/senha + TOTP) + roles + decoradores + `/admin/usuarios`.

Resultado dos testes: **118 passed / 0 failed** (`python -m pytest`).

---

## 1. Arquivos novos e modificados (LOC)

### Novos

| Arquivo | LOC |
|---|---:|
| migrations/001_init_schema_smo.sql | 77 |
| migrations/002_usuarios.sql | 20 |
| scripts/migrate.py | 119 |
| scripts/seed_gestor.py | 77 |
| app/extensions.py | 9 |
| app/auth/__init__.py | 1 |
| app/auth/decorators.py | 82 |
| app/models/user.py | 45 |
| app/services/user_service.py | 307 |
| app/services/totp_service.py | 44 |
| app/routes/auth.py | 150 |
| app/routes/admin.py | 117 |
| app/templates/auth/login.html | 30 |
| app/templates/auth/login_2fa.html | 40 |
| app/templates/auth/setup_2fa.html | 46 |
| app/templates/admin/usuarios.html | 157 |
| app/static/css/auth.css | 134 |
| tests/test_auth.py | 304 |

### Renomeados

| De | Para | LOC pós |
|---|---|---:|
| app/services/supabase_service.py | app/services/db_service.py | 309 |

### Modificados

| Arquivo | LOC | Natureza |
|---|---:|---|
| app/__init__.py | 50 | registra LoginManager, Limiter, blueprints auth/admin |
| app/config.py | 28 | renomeia SUPABASE_DB_URL→DATABASE_URL, session lifetime 8h, flask-limiter |
| app/models/database.py | 15 | usa DATABASE_URL; removido init_tables() (migrations assumiram) |
| app/routes/operador.py | 21 | @login_required + role_required |
| app/routes/analista.py | 12 | @login_required |
| app/routes/api.py | 327 | troca imports, DATABASE_URL, @login_required + role nas rotas de escrita |
| requirements.txt | 12 | flask-login, bcrypt, pyotp, qrcode, flask-limiter |
| .env.example | 4 | renomeia SUPABASE_DB_URL→DATABASE_URL |
| tests/conftest.py | 200 | DATABASE_URL, SESSION_PROTECTION=None, login de Gestor para fixtures |
| scripts/importar_lote.py | 141 | import de db_service (antes supabase_service) |

### Teto de 500 LOC

**Nenhum arquivo ultrapassa 500 LOC.** O maior é `app/routes/api.py` (327) seguido de `app/services/db_service.py` (309) e `tests/test_auth.py` (304). Todos dentro do limite.

---

## 2. Tipagem

### Geral
- `from __future__ import annotations` em todos os modulos Python novos e modificados.
- Tipos de retorno explicitos em todas as funcoes novas.
- TypedDicts para payloads (`UsuarioCreate`, `UsuarioUpdate`, `UsuarioFiltro`).
- `Literal`/`frozenset` para roles (`Role = Literal["gestor","operador_arei","operador_alei"]`).
- `dataclass(frozen=True)` para `User`.

### Ocorrencias de `Any`
Unica ocorrencia: `app/auth/decorators.py` — dentro das assinaturas de wrappers/`Callable`. `Any` e idiomatico e
necessario para decoradores genericos que envolvem qualquer view Flask sem perder `*args`/`**kwargs`.
**Nao ha `Any` em codigo de dominio** (services, models, rotas, templates).

### Ocorrencias de `dict` sem parametros
Mantidas apenas em assinaturas que retornam linhas de banco ja ha tempos no projeto (analytics_* e db_service)
por compatibilidade com callers existentes. O codigo novo usa `TypedDict`/`dataclass`/`Literal`.

### Casts
`typing.cast` aplicado explicitamente quando o tipo de uma coluna vinda do `RealDictCursor` precisa ser
afirmado (ex.: `_row_to_user` em `user_service.py`).

---

## 3. Seguranca

| Item | Status | Evidencia |
|---|---|---|
| Queries SQL parametrizadas | OK | 100% `%(...)s` / `%s` em `db_service.py`, `user_service.py`. Zero f-string em SQL. |
| Hash de senha bcrypt (cost=12) | OK | `user_service._hash_senha` e `verificar_senha` usam `bcrypt.hashpw`/`checkpw`. |
| TOTP validado server-side | OK | `totp_service.verificar_codigo` usa `pyotp.TOTP.verify(window=1)`. |
| 2FA obrigatorio para Gestor e AREI | OK | `User.requer_2fa()` + fluxo `auth.login` redireciona para `/setup-2fa` no primeiro acesso. |
| Rate limit 5/min em /login e /login/2fa | OK | `@limiter.limit("5 per minute", methods=["POST"])` nas duas rotas (desligado em TESTING). |
| Autoescape Jinja2 | OK | Flask liga autoescape por padrao para templates `.html`; nenhum `|safe` foi usado. |
| Session cookie httpOnly + SameSite=Lax | OK | `Config.SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE="Lax"`. |
| Sessao expira em 8h | OK | `Config.PERMANENT_SESSION_LIFETIME=timedelta(hours=8)` + `session.permanent = True` em `_post_login`. |
| Login invalido retorna 401 sem distinguir causa | OK | Mesma flash "Credenciais invalidas" para usuario inexistente / senha errada. |
| CHECK no banco para ALEI ter unidade | OK | Migration 002 impoe `CHECK (role <> 'operador_alei' OR unidade IS NOT NULL)`. |
| Validacao server-side de role/unidade | OK | `user_service.create`/`update` validam `ROLES_VALIDOS` e exigem unidade para ALEI. |
| Session protection (Flask-Login "strong") | OK | `login_manager.session_protection = "strong"` em producao; `None` apenas sob TESTING. |
| Proteger rotas existentes | OK | `@login_required` em todas as rotas `operador`, `analista`, `api`. Rotas de escrita exigem role Gestor/AREI. |
| Unidade cross-submit bloqueada (ALEI) | OK | Decorador `unidade_match_required` pronto para rotas Fase 6.3. |

### Exposicao de informacao
- Seed do Gestor nao escreve senha em log; usa `getpass.getpass`.
- Mensagens de erro de banco nao vazam para o cliente; sao logadas com `current_app.logger`.
- QR code 2FA entregue inline como `data:image/png;base64,...` (nao fica em disco nem no servico externo).

---

## 4. Testes

`tests/test_auth.py` cobre o mandato do escopo 6.1 e roda 12 casos:

- Login OK / senha errada / campos vazios (400/401)
- Rate limit dispara 429 na 6a tentativa
- 2FA valido (302 -> area logada) e invalido (401)
- Decorador `role_required`: Gestor entra em `/admin/usuarios`, ALEI recebe 403, anonimo redireciona para /login
- Decorador `unidade_match_required`: ALEI em unidade errada = 403, na propria unidade = 200, Gestor passa livre

Suite completa preservada: **118 passed** (86 existentes + 12 novos + 20 whatsapp parser).

---

## 5. Migrations

- `scripts/migrate.py` le `./migrations/NNN_*.sql`, cria `smo.schema_migrations`, aplica pendentes em ordem.
- Idempotente: segunda execucao nao duplica (checa `id` antes de aplicar).
- `ALTER TABLE ... SET SCHEMA smo` e condicional (so move se ainda existe em `public` e ainda nao existe em `smo`).
- Tabelas `smo.fracoes`/`smo.cabecalho` tambem sao criadas via `CREATE TABLE IF NOT EXISTS` como rede de seguranca para ambientes novos.
- `smo.usuarios` tem CHECK constraint para ALEI exigir unidade.

Smoke test local:
```
python -c "from scripts.migrate import _listar_migrations; print([m.nome for m in _listar_migrations()])"
# ['001_init_schema_smo.sql', '002_usuarios.sql']
```

---

## 6. Autoavaliacao dos 6 principios inegociaveis

| # | Principio | Resultado | Justificativa |
|---|---|---|---|
| 1 | Tipagem forte | **Passou** | Zero `Any` em dominio. TypedDict/Literal/dataclass. `Any` apenas em decoradores genericos (idiomatico). |
| 2 | Modularidade max 500 LOC | **Passou** | Maior arquivo: 327 LOC (api.py). |
| 3 | Seguranca ativa | **Passou** | Parametros SQL, bcrypt, TOTP, rate limit, autoescape, CHECK constraint, cookie seguro, session protection. |
| 4 | Front burro, logica no backend | **Passou** | Templates apenas renderizam variaveis ja tratadas. Decoradores backend controlam autorizacao. Zero logica de negocio em JS novo. |
| 5 | Design elegante e minimalista | **Passou** | `auth.css` reusa variaveis do tema (navy/gold/bg), cards centralizados, tipografia consistente com base.css. Sem poluicao visual. |
| 6 | Auditoria final | **Passou** | Este documento. |

---

## 7. Checklist do escopo 6.1 (prompt)

- [x] `migrations/` + runner `scripts/migrate.py`
- [x] Migration 001: schema `smo` + move `fracoes`/`cabecalho`
- [x] Migration 002: `smo.usuarios` + CHECK + index email
- [x] `SUPABASE_DB_URL` -> `DATABASE_URL` em config, env.example, codigo
- [x] `app/services/supabase_service.py` -> `app/services/db_service.py` (git mv)
- [x] Todo SQL ajustado para `smo.fracoes` / `smo.cabecalho`
- [x] `requirements.txt` com flask-login, bcrypt, pyotp, qrcode[pil], flask-limiter
- [x] `app/models/user.py` (`User(UserMixin)` + Role literal)
- [x] `app/services/user_service.py` (CRUD tipado)
- [x] Flask-Login `user_loader` em `app/__init__.py`
- [x] Rotas `/login`, `/login/2fa`, `/setup-2fa`, `/logout`
- [x] Sessao 8h (`PERMANENT_SESSION_LIFETIME`)
- [x] Rate limit 5/min em `/login` e `/login/2fa`
- [x] 2FA obrigatorio para Gestor/AREI, opcional para ALEI
- [x] Decoradores `role_required([...])` e `unidade_match_required`
- [x] Templates auth (login, login_2fa, setup_2fa) com autoescape Jinja
- [x] Tela `/admin/usuarios` (Gestor apenas) com filtros/criar/desativar/reset-2FA
- [x] `scripts/seed_gestor.py` via prompt interativo
- [x] Protecao das rotas existentes (operador/analista/api) com role apropriado
- [x] `tests/test_auth.py` cobrindo login, 2FA, rate limit, decoradores (12 casos)
- [x] Este documento de auditoria

---

## 8. Observacoes para a revisao humana

1. **Supabase IPv6**: sem mudanca no modelo de conexao. `DATABASE_URL` aceita a URL de connection pooling
   (transacional na porta 6543) do Supabase, que continua 100% compativel com psycopg2.
2. **Primeiro uso**: (i) `pip install -r requirements.txt`; (ii) `python -m scripts.migrate`;
   (iii) `python -m scripts.seed_gestor`; (iv) `python run.py`; (v) logar com o Gestor recem-criado — ele
   vai ser redirecionado para `/setup-2fa` no primeiro login.
3. **Form do admin/usuarios**: nao implementa "editar inline" por enquanto (escopo 6.1 pedia botoes
   criar/editar/desativar/resetar 2FA — editar esta como rota backend `POST /admin/usuarios/<id>/editar`
   mas a UI simplificou para criar/desativar/reset-2FA; edicao completa pode ser tratada via reset + recriar
   ou numa iteracao 6.1.1 de UI se o chefe pedir).
4. **Legado `missao` em `fracoes`**: nao alterado nesta entrega. Colunas novas (`missao_id`, `osv`,
   `municipio_id`, `atualizado_em`) e catalogo `smo.missoes`/`smo.municipios` sao escopo da 6.2.
5. **Session protection** `strong` em producao invalida sessao se fingerprint (IP+UA) mudar. Se causar UX
   ruim na rede da intel (saida via proxy com IP variavel), trocar para `basic` no `app/__init__.py`.

Entrega 6.1 pronta para revisao. Nao avancar para 6.2 sem OK do chefe.
