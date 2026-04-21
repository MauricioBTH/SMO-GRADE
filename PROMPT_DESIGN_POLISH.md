# PROMPT — Design Polish (pré-Oracle deploy)

Data: 2026-04-21
Continuação de: Fase 6.2.5 (triagem de missões — `AUDITORIA_6_2_5.md`)

> **Nota de escopo**: NÃO é a Fase 6.3 do roadmap. É um polimento visual +
> navegação executado antes do deploy Oracle. A Fase 6.3 (form ALEI + deploy)
> continua reservada. Ver `PLANO_DESIGN_POLISH.md` §1 para contexto completo.

---

## 0. Ordem de leitura antes de codar

Leia nesta ordem (não pule):

1. **`PLANO_DESIGN_POLISH.md`** — este arquivo é o guia, mas o plano tem
   os detalhes finos (tokens, contratos, testes, pontos sutis).
2. `AUDITORIA_6_2_5.md` — o que já está pronto.
3. `memory/user_mauricio.md` — princípios inegociáveis do usuário.
4. `memory/feedback_frontend_burro.md` — regra de ouro.
5. `memory/domain_fracoes_vs_missoes.md` — CANIL/PATRES/PRONTIDAO são
   frações, não missões.
6. `memory/decisao_fase6_3_alei_normalizacao.md` — não muda nada aqui, só
   contexto.
7. `app/static/css/upload.css` — aesthetic de referência (dark + gold).
8. `app/static/css/base.css` — onde os tokens vão viver.
9. `app/templates/base.html` — shell atual, a ser estendido.
10. `app/templates/operador/index.html` — exemplo de consumidor do visual.
11. `app/models/user.py` — roles existentes (`gestor`, `operador_arei`,
    `operador_alei` — **sem `analista`**).

---

## 1. Decisões já tomadas (não revisitar sem motivo forte)

- **"Analista" = `gestor`**. Nenhuma role nova. Páginas admin continuam
  com `@role_required(["gestor"])`.
- **Tokens de cor centralizados em `base.css` `:root`**, não em arquivo
  novo. `upload.css` vai trocar hex literais por variáveis.
- **Header/nav via blocos opcionais em `base.html`** + partials
  (`_components/header.html`, `_components/nav.html`). **Sem**
  `base_app.html` novo.
- **Ícones-only com tooltip nativo** (`title=""`) em toda nav e ações CRUD.
- **Dropdown do user-chip via `<details>` CSS puro**. Zero JS.
- **Trocar senha adiantada** (Etapa 3) pra o header da Etapa 4 nascer
  100% funcional.

---

## 2. Etapas — executar nesta ordem com revisão entre elas

| # | Etapa | LOC est. | Revisão com usuário? |
|---|---|---|---|
| 1 | Tokens em `base.css` + `upload.css` trocando hex por variáveis | +10 / ~40 | automática (sem mudança visual) |
| 2 | Login + 2FA dark theme + subtítulo CCMO | ~120 | **sim** — user abre `/login` e aprova |
| 3 | Rota + template "Trocar senha" | ~100 | **sim** — user testa fluxo |
| 4 | `base.html` + blocos + partials `header.html` / `nav.html` + CSS | ~140 | **sim** — user abre `/login` (sem header) e `/` (com header), confere |
| 5 | Parser + painel analista plugam header/nav | ~15 | **sim** — user abre `/` e `/analista` |
| 6a | `crpms.html` dark theme | ~60 | **sim** |
| 6b | `missoes.html` dark theme | ~100 | **sim** |
| 6c | `municipios.html` dark theme | ~100 | **sim** |
| 6d | `triagem_missoes.html` dark theme (cuidado: modal + banner undo) | ~150 | **sim** |
| 7 | `/admin/usuarios` dark theme | ~150 | **sim** |
| 8 | `/me` perfil readonly | ~80 | **sim** |

**Regra**: NÃO avançar para a próxima etapa sem aprovação explícita do
usuário da etapa anterior.

Ver `PLANO_DESIGN_POLISH.md` §3 para contratos de cada etapa (tokens,
template do header, rota trocar_senha, etc).

---

## 3. Princípios inegociáveis — CHECAR A CADA ETAPA

1. **Tipagem forte**: zero `Any`, zero `cast` fora da fronteira de DB,
   zero `Record`. `Literal`/`TypedDict`/`dataclass(frozen=True)`.
2. **500 LOC max por arquivo**. Se um CSS estourar, dividir por feature
   (ex.: `base.css` + `forms.css` + `tables.css`).
3. **Segurança contra ataques**:
   - Prepared statements (`cur.execute(sql, params)`).
   - CSRF em todos os POSTs.
   - `@role_required` / `@login_required` em toda rota autenticada.
   - Input sanitizado (limites de tamanho, validação antes do banco).
   - Autoescape Jinja2 (nunca `|safe` em conteúdo de usuário).
   - Trocar senha valida senha atual via bcrypt antes de aceitar nova.
4. **Frontend burro**: toda lógica no backend. JS só abre/fecha modal
   ou faz fetch+reload. Dropdown do user-chip via `<details>` puro CSS.
   Navegação é anchor `<a>` — nada de SPA.
5. **Design elegante/minimalista/intuitivo**:
   - Ícones-only com tooltip nativo (`title=""`).
   - Espaçamento generoso, hierarquia tipográfica clara.
   - Dark theme consistente (`--dark-bg`, `--dark-panel`, `--gold`).
   - Estados hover/focus explícitos.
6. **Auditoria**: ao terminar TODAS as etapas, escrever
   `AUDITORIA_DESIGN_POLISH.md` (formato: ver `AUDITORIA_6_2_5.md`).
7. **Domínio**: CANIL/PATRES/PRONTIDAO/PMOB = frações, não missões. Se
   algum copy de UI mencionar, respeitar a semântica.

---

## 4. Contratos resumidos (detalhes em `PLANO_DESIGN_POLISH.md` §3)

### Tokens novos em `base.css` `:root`
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

### Rota trocar-senha (Etapa 3)
```python
@auth_bp.route("/trocar-senha", methods=["GET", "POST"])
@login_required
def trocar_senha() -> Response | str:
    # GET → render form
    # POST →
    #   1. valida senha atual via user_service.verificar_senha
    #   2. valida senha_nova == senha_conf
    #   3. chama user_service.alterar_senha(current_user.id, senha_nova)
    #   4. flash info + redirect
```

Serviço `alterar_senha` **já existe** em
[app/services/user_service.py:212](app/services/user_service.py#L212) —
não duplicar. Só consumir.

### `base.html` estendido (Etapa 4)
```jinja
<body>
  {% block header %}{% endblock %}
  {% block nav %}{% endblock %}
  {% block content %}{% endblock %}
  {% block scripts %}{% endblock %}
</body>
```

### Nav com role-gate (Etapa 4)
```jinja
<nav class="app-nav">
  <a href="{{ url_for('operador.index') }}" title="Parser">...</a>
  {% if current_user.eh_gestor() %}
    <a href="{{ url_for('analista.index') }}" title="Painel do Analista">...</a>
    <a href="{{ url_for('admin_catalogos.listar_missoes_view') }}" title="Missões">...</a>
    <a href="{{ url_for('admin_catalogos.listar_municipios_view') }}" title="Municípios">...</a>
    <a href="{{ url_for('admin_catalogos.listar_triagem_view') }}" title="Triagem">...</a>
    <a href="{{ url_for('admin.listar_usuarios') }}" title="Usuários">...</a>
  {% endif %}
</nav>
```

---

## 5. Testes — mínimo por etapa

| Etapa | Teste novo |
|---|---|
| 3 | 4 testes em `tests/test_trocar_senha.py` (ver `PLANO_DESIGN_POLISH.md` §5) |
| 4 | 2 testes de template render (nav com gestor mostra todos os links; nav com AREI esconde admin) |
| 8 | 2 testes em `tests/test_perfil.py` (GET sem login → 401; GET com login → 200 com dados) |

Meta: suite atual 164 → pós-polish ~172. Rodar `pytest -q` após cada etapa.

---

## 6. Pontos de atenção

- **Parser é a tela mais crítica**. Nunca mexer nele antes da Etapa 5, e
  só com header/nav já aprovados em isolamento.
- **`triagem_missoes.html`** (Etapa 6d) tem modal `<dialog>` + banner undo
  `#banner-undo` — NÃO quebrar a UX existente ao migrar o visual.
- **`base.css` pode estourar 500 LOC** ao absorver classes de header/nav/
  tabela admin. Se passar de ~400, dividir: `base.css` (tokens + reset),
  `components.css` (header, nav, user-chip), `admin.css` (tables, forms,
  modal). Coordenar com o usuário antes de dividir.
- **Autoescape Jinja2 é default** — `current_user.nome` é seguro. Nunca
  `|safe` em conteúdo de usuário.
- **Tokens primeiro**: nunca hardcodar cor nova em CSS. Sempre via
  variável em `base.css` `:root`.

---

## 7. Quando terminar

1. Rodar `pytest -q` — 172+ passando.
2. Rodar o app e testar manualmente cada tela em cada role:
   - `gestor` → vê tudo.
   - `operador_arei` → vê parser + painel analista, não vê admin.
   - `operador_alei` → vê apenas parser.
3. Escrever `AUDITORIA_DESIGN_POLISH.md` com:
   - Tabela LOC (todos arquivos novos/modificados).
   - Decisões tomadas com justificativa.
   - Cobertura de testes (quantos novos, quais cenários).
   - Pontos abertos/pendentes pra Fase 6.3.
4. Atualizar `MEMORY.md` com ponteiro pra auditoria se for memória
   durável (ex.: nova convenção de design tokens).

---

## 8. O que NÃO fazer

- **Não criar `base_app.html`**. Decisão já tomada.
- **Não criar role `analista`**. Decisão já tomada.
- **Não duplicar `user_service.alterar_senha`**. Serviço já existe.
- **Não adicionar JS pra dropdown**. `<details>` + CSS resolve.
- **Não tocar lógica de negócio do parser/triagem**. É polimento visual
  + navegação + trocar senha + `/me`. Nada mais.
- **Não avançar etapa sem aprovação do usuário**.
- **Não usar `Any`/`cast`/`Record`**. Princípio inegociável.
- **Não colocar lógica no JS**. Frontend burro é inegociável.
- **Não hardcodar cor** — sempre via token em `base.css` `:root`.
