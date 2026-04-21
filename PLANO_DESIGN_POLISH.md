# PLANO — Design Polish (pré-Oracle deploy)

Data: 2026-04-21
Continuação de: Fase 6.2.5 (triagem de missões — `AUDITORIA_6_2_5.md`)

> **Nota de escopo**: NÃO é a Fase 6.3 do roadmap original (que é form ALEI +
> deploy Oracle). Este é um polimento visual e de navegação feito **antes** do
> deploy Oracle, para consolidar identidade visual e acesso às páginas admin
> que hoje só são alcançáveis via URL digitada. A Fase 6.3 continua reservada.

---

## 1. Contexto / estado atual

- Parser (`/operador`) tem identidade visual completa: dark theme
  (`#0d0d0d`), acentos gold (`#F7B900`), tipografia minimalista.
  Ver [app/static/css/upload.css](app/static/css/upload.css).
- Login, 2FA, e as 5 páginas admin (`/admin/catalogos/missoes`,
  `/admin/catalogos/municipios`, `/admin/catalogos/crpms`,
  `/admin/catalogos/triagem-missoes`, `/admin/usuarios`) usam visual
  **light theme** (`#F2F2F2` + navy/white) herdado de
  [app/static/css/auth.css](app/static/css/auth.css) — **dissonante** com
  o parser.
- [app/templates/base.html](app/templates/base.html) é um shell vazio. Não
  há header/nav compartilhado. Cada página duplica `<h1>`.
- Páginas admin só são acessíveis via URL digitada no browser (não há
  link/botão no app).
- Link "Painel do Analista" no parser aparece pra todo usuário — deveria
  ser restrito.
- Não existe página de perfil (`/me`) nem rota de trocar senha —
  [user_service.alterar_senha()](app/services/user_service.py#L212) existe
  mas não tem UI nem rota.

### Roles existentes
[app/models/user.py:8](app/models/user.py#L8): `gestor`, `operador_arei`,
`operador_alei`. **Decidido**: "analista" do roadmap = `gestor`. Nenhuma
nova role. Páginas admin continuam `role_required(["gestor"])`.

### Decisões do usuário (2026-04-21)

1. Analista = gestor. Nenhuma nova role.
2. Tokens de cor centralizados em `base.css` (sem criar `shell.css` novo).
3. Header/nav: blocos opcionais em `base.html` existente + partials. **Sem**
   `base_app.html` novo.
4. Ícones-only com tooltip nativo (`title=""`) em toda nav e ações CRUD.
5. Ordem revisada: trocar senha adiantado para Etapa 3 (antes do header).

---

## 2. Etapas (ordem de execução)

| # | Etapa | Arquivos | LOC est. | Risco |
|---|---|---|---|---|
| 1 | Tokens de cor em `base.css` + troca de hex em `upload.css` | `base.css`, `upload.css` | +10 / ~40 substituições | trivial |
| 2 | Login + 2FA dark theme + subtítulo CCMO | 3 templates auth + reescrita de `auth.css` | ~120 | baixo |
| 3 | Rota + template "Trocar senha" | `routes/auth.py`, `templates/auth/trocar_senha.html`, `tests/test_auth.py` | ~100 | baixo |
| 4 | `base.html` ganha blocos `header`/`nav` + partials | `base.html`, `_components/header.html`, `_components/nav.html`, `base.css` | ~140 | baixo |
| 5 | Parser e painel analista plugam header/nav | `operador/index.html`, `analista/index.html` | ~15 | baixo |
| 6 | 4 páginas admin dark theme (missoes, municipios, crpms, triagem_missoes) | 4 templates + CSS | ~400 alt / ~120 novos | médio |
| 7 | `/admin/usuarios` mesma tratativa | 1 template + CSS | ~150 | baixo |
| 8 | `/me` (página de perfil readonly) | nova rota + template | ~80 | trivial |

**Total**: ~1130 LOC alteradas + ~560 LOC novas, espalhadas em ~18 arquivos.
Nenhum arquivo isolado > 300 LOC.

### Ponto de revisão com o usuário após: 2, 3, 4, 5, cada sub-passo do 6, 7, 8.

---

## 3. Contratos

### Etapa 1 — Tokens de cor

Adicionar em [app/static/css/base.css](app/static/css/base.css) `:root`:

```css
--dark-bg: #0d0d0d;
--dark-panel: #1a1a1a;
--dark-panel-alt: #141414;
--border-subtle: rgba(87, 87, 90, 0.3);
--border-muted: rgba(87, 87, 90, 0.4);
--gold-soft: rgba(247, 185, 0, 0.1);
--gold-border: rgba(247, 185, 0, 0.3);
--gold-hover: #e5ab00;
--status-success: #22c55e;
--status-error: #ef4444;
--status-warning: #f87171;
```

Em [app/static/css/upload.css](app/static/css/upload.css), substituir
todos os hex literais pelas variáveis acima. Zero mudança visual.

### Etapa 2 — Login redesign

Template [app/templates/auth/login.html](app/templates/auth/login.html)
(e 2fa/setup_2fa análogos):

```jinja
<div class="auth-wrap">
  <form class="auth-card">
    <h1>Brigada Militar · CPChq</h1>
    <p class="auth-subtitle">Comando e Controle de Meios Operacionais — CCMO</p>
    <h2>Acesso ao SMO</h2>
    ...
  </form>
</div>
```

`auth.css` reescrita: fundo `var(--dark-bg)`, card `var(--dark-panel)`,
bordas `var(--border-subtle)`, botão primário gold (mesmo do parser),
inputs escuros com border gold no focus.

### Etapa 3 — Trocar senha

**Serviço já existe**: [user_service.alterar_senha()](app/services/user_service.py#L212-L219).
Validação de tamanho + bcrypt + UPDATE — pronto.

**Falta criar**:

```python
# app/routes/auth.py
@auth_bp.route("/trocar-senha", methods=["GET", "POST"])
@login_required
def trocar_senha() -> Response | str:
    if request.method == "GET":
        return render_template("auth/trocar_senha.html")
    senha_atual: str = request.form.get("senha_atual") or ""
    senha_nova: str = request.form.get("senha_nova") or ""
    senha_conf: str = request.form.get("senha_conf") or ""
    # valida current via user_service.verificar_senha(current_user.email, senha_atual)
    # valida senha_nova == senha_conf
    # chama user_service.alterar_senha(current_user.id, senha_nova)
    # flash + redirect
```

Template estende `base.html`, reusa `.auth-card` da Etapa 2.

**Segurança**:
- Valida senha atual antes de aceitar nova (bcrypt.checkpw).
- Senha nova ≥ 8 chars (reusa `_validar_senha`).
- Confirmação bate com nova antes do hash.
- CSRF token.

**Testes** (mínimo 4):
1. GET sem login → 401.
2. POST senha atual errada → flash error, sem UPDATE.
3. POST nova ≠ confirmação → flash error.
4. POST ok → UPDATE feito, flash info, redirect.

### Etapa 4 — `base.html` + partials

```jinja
{# base.html #}
<!DOCTYPE html>
<html lang="pt-BR">
<head>...</head>
<body>
  {% block header %}{% endblock %}
  {% block nav %}{% endblock %}
  {% block content %}{% endblock %}
  {% block scripts %}{% endblock %}
</body>
</html>
```

```jinja
{# _components/header.html #}
<header class="app-header">
  <div class="app-header__brand">
    <h1>Brigada Militar · CPChq</h1>
    <p class="app-header__ccmo">Comando e Controle de Meios Operacionais — CCMO</p>
  </div>
  <div class="app-header__user">
    <details class="user-chip">
      <summary>
        <span class="user-chip__avatar">{{ current_user.nome[:2]|upper }}</span>
        <span class="user-chip__nome">{{ current_user.nome }}</span>
        <span class="user-chip__role">{{ current_user.role|replace('_',' ')|upper }}</span>
      </summary>
      <div class="user-chip__menu">
        <a href="{{ url_for('user.perfil') }}">Minha conta</a>
        <a href="{{ url_for('auth.trocar_senha') }}">Trocar senha</a>
        <form method="POST" action="{{ url_for('auth.logout') }}">
          <button type="submit">Sair</button>
        </form>
      </div>
    </details>
  </div>
</header>
```

```jinja
{# _components/nav.html — só renderiza itens conforme role #}
<nav class="app-nav">
  <a href="{{ url_for('operador.index') }}" title="Parser"
     class="{% if request.endpoint == 'operador.index' %}ativo{% endif %}">
    <svg>...</svg>
  </a>
  {% if current_user.eh_gestor() %}
    <a href="{{ url_for('analista.index') }}" title="Painel do Analista">...</a>
    <a href="{{ url_for('admin_catalogos.listar_missoes_view') }}" title="Missões">...</a>
    <a href="{{ url_for('admin_catalogos.listar_municipios_view') }}" title="Municípios">...</a>
    <a href="{{ url_for('admin_catalogos.listar_triagem_view') }}" title="Triagem">...</a>
    <a href="{{ url_for('admin.listar_usuarios') }}" title="Usuários">...</a>
  {% endif %}
</nav>
```

Dropdown do user-chip: **CSS puro** via `<details>` + `<summary>`. Zero JS.

### Etapa 5 — Parser e painel plugam header/nav

```jinja
{# operador/index.html #}
{% extends "base.html" %}

{% block header %}{% include "_components/header.html" %}{% endblock %}
{% block nav %}{% include "_components/nav.html" %}{% endblock %}

{% block content %}
  {# conteúdo atual — remove o link hardcoded "Painel do Analista" da linha 29 #}
{% endblock %}
```

### Etapa 6 — 4 páginas admin dark theme

Ordem de execução (menor → maior risco):
1. `crpms.html` (readonly, mais simples)
2. `missoes.html`
3. `municipios.html`
4. `triagem_missoes.html` (modal + banner undo já existem — cuidado)

Cada uma:
- Estende `base.html`, inclui header/nav.
- Remove `<style>` inline duplicado → classes utilitárias em `base.css`.
- Troca `auth.css` por classes dark-admin em `base.css`:
  - `.admin-wrap` → fundo `var(--dark-bg)`, texto claro
  - `.admin-table` → header gold muted, zebra sutil com `var(--dark-panel-alt)`
  - `.admin-actions` → botões ícone-only com tooltip
- Modal "Nova missão" (triagem) ganha visual do `.modal-box` do parser.

### Etapa 7 — `/admin/usuarios`

Mesmo padrão da Etapa 6. `role_required(["gestor"])` mantido.

### Etapa 8 — `/me` perfil

```python
# app/routes/user.py (blueprint novo, ou agrega em auth)
@user_bp.route("/me", methods=["GET"])
@login_required
def perfil() -> str:
    return render_template("user/perfil.html")
```

Template readonly: nome, email, role, unidade. Link pra `auth.trocar_senha`.

---

## 4. Segurança

- **Sem novas rotas sem role_required ou login_required**.
- **Trocar senha**: valida senha atual via bcrypt antes de aceitar nova.
- **CSRF**: todos os POSTs novos com token (mesmo padrão do app).
- **Links em nav**: render condicional — `current_user.eh_gestor()`
  impede que não-gestor veja link que levaria a 403.
- **Input**: confirmação de senha bate com nova antes do hash.
- **XSS**: `current_user.nome` no header vem do DB próprio — ainda assim
  Jinja2 autoescape é default. Nunca usar `|safe` em conteúdo de usuário.
- **Dropdown `<details>`**: sem JS, imune a XSS em handlers inline.

---

## 5. Testes

Novos testes mínimos:

1. **Trocar senha**:
   - GET sem login → 401.
   - POST senha atual errada → 200 com flash error, sem UPDATE.
   - POST nova ≠ conf → 200 com flash error, sem UPDATE.
   - POST ok → 302 redirect, UPDATE aplicado.
2. **Nav role-gate** (teste de template render):
   - Usuário `operador_arei` logado → HTML do nav NÃO contém link pra
     `/admin/catalogos/missoes`.
   - Usuário `gestor` → HTML do nav contém todos os links admin.
3. **`/me` perfil**:
   - GET sem login → 401.
   - GET com login → 200, HTML contém email/role/unidade do user atual.

Suite atual: **164 testes** (após 6.2.5). Meta pós-polish: **~172**.

---

## 6. Princípios inegociáveis (reforço)

1. **Tipagem forte**: zero `Any`, zero `cast` fora da fronteira de DB, zero
   `Record`. Use `Literal`, `TypedDict`, `dataclass(frozen=True)`.
2. **500 LOC max por arquivo**. Maior previsto: `base.css` (~400 depois
   do polish). Se estourar, dividir por feature (`base.css` + `forms.css`
   + `tables.css`).
3. **Segurança contra ataques**: prepared statements, CSRF, role gates,
   sanitize de inputs, autoescape Jinja2, validação antes do banco.
4. **Frontend burro**: **zero lógica de negócio no JS**. Dropdown via
   `<details>` puro CSS. Navegação é anchor `<a>` — nada de SPA.
5. **Design elegante/minimalista/intuitivo**: ícones-only com tooltip
   nativo, espaçamento generoso, hierarquia tipográfica clara, dark theme
   consistente.
6. **Auditoria**: ao concluir, escrever `AUDITORIA_DESIGN_POLISH.md` com
   tabela LOC + decisões + cobertura de testes, seguindo
   `AUDITORIA_6_2_5.md`.
7. **Domínio**: **CANIL/PATRES/PRONTIDAO/PMOB são frações, não missões**.
   Nada a ver com polish visual, mas se qualquer texto de UI mencionar
   esses termos, respeitar semântica.

---

## 7. Arquivos a criar/modificar — resumo

### Novos
- `app/templates/_components/header.html`
- `app/templates/_components/nav.html`
- `app/templates/auth/trocar_senha.html`
- `app/templates/user/perfil.html`
- `app/routes/user.py` (se escolher blueprint separado — alternativa:
  agregar `/me` em `auth.py`)
- `tests/test_trocar_senha.py`
- `tests/test_perfil.py`
- `AUDITORIA_DESIGN_POLISH.md`

### Modificados
- `app/templates/base.html` (+2 blocos vazios)
- `app/templates/auth/login.html`
- `app/templates/auth/login_2fa.html`
- `app/templates/auth/setup_2fa.html`
- `app/templates/operador/index.html` (plug header/nav, remove link hardcoded linha 29)
- `app/templates/analista/index.html` (plug header/nav)
- `app/templates/admin/missoes.html`
- `app/templates/admin/municipios.html`
- `app/templates/admin/crpms.html`
- `app/templates/admin/triagem_missoes.html`
- `app/templates/admin/usuarios.html`
- `app/static/css/base.css` (+ tokens + classes admin + header/nav)
- `app/static/css/auth.css` (reescrita)
- `app/static/css/upload.css` (hex → variáveis)
- `app/routes/auth.py` (+ rota trocar_senha)

---

## 8. Pontos sutis já debatidos

- **Por que não `base_app.html` novo**: seria layer extra para um app
  pequeno. Blocos opcionais em `base.html` resolvem com menos
  estrutura.
- **Por que ícones-only + tooltip nativo**: mais clean, evita problemas
  de i18n/text-overflow, `title=""` é acessível e zero JS.
- **Por que dropdown via `<details>`**: HTML nativo, acessível, sem JS,
  funciona sem CSS também.
- **Por que "analista" = gestor**: o sistema já tem só 3 roles
  (`gestor`, `operador_arei`, `operador_alei`). Criar uma 4ª só pra
  desambiguar seria churn. Gestor já é quem administra catálogos.
- **Por que adiantar trocar-senha pra Etapa 3**: evita botão `disabled`
  no header da Etapa 4. Faz o header nascer 100% funcional.
- **Por que não tocar `/operador` antes da Etapa 5**: parser é a tela
  mais crítica. Só migra depois que header/nav já existem e foram
  validados visualmente no login.

---

## 9. Próximos passos após o polish

- **Fase 6.3** (roadmap original): form web ALEI + deploy Oracle Cloud Free
  + hardening. Ver `ARQUITETURA.md` §roadmap e `PROMPT_FASE6_2.md` §157.
  ALEI usará o parser com `role_required` expandido — ver
  `memory/decisao_fase6_3_alei_normalizacao.md`.
- **Fase 7**: editor in-place no preview de parse (sugerido em
  `AUDITORIA_6_2`).

---

## 10. Pendências arquiteturais da 6.3 (não afetam o polish)

Decididas em 2026-04-21 mas executadas na 6.3, não aqui:

- **Fluxo de recepção AREI (modelo C)** — ALEI publica direto, AREI tem
  tela `/arei/consolidacao?data=...` com status por unidade (✓ recebida /
  ⏳ pendente / ⚠ avisos) e edição inline. Ver
  [`DECISAO_FLUXO_AREI.md`](DECISAO_FLUXO_AREI.md) para contratos,
  pré-requisitos e testes.
- **Migration 005 (rastreabilidade)** — pré-requisito da 6.3. Adiciona
  `criado_por UUID` em `smo.fracoes` e `smo.cabecalho`, `created_at` em
  `smo.cabecalho`, índices `(unidade, data)`. Detalhes em
  [`DECISAO_FLUXO_AREI.md`](DECISAO_FLUXO_AREI.md#3-pré-requisitos--migration-005-antes-da-63).

**Impacto no polish**: zero. Header/nav a serem criados nas Etapas 3-4
serão reaproveitados pela tela de consolidação quando ela for construída.
