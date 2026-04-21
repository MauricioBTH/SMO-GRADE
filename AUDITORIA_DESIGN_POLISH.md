# AUDITORIA — Design Polish (pre-Oracle deploy) — parcial

Data: 2026-04-21
Escopo: polimento visual + navegacao pre-deploy Oracle. NAO e a Fase 6.3 do
roadmap. Executado em 8 etapas sequenciais — **5 concluidas, 3 pendentes**.
Ver `PROMPT_DESIGN_POLISH.md` e `PLANO_DESIGN_POLISH.md` para contrato.

---

## 1. Resumo executivo

- Suite: 164 testes (pos-6.2.5) -> **174 testes** (0 falhas, 3.3s).
- 16 arquivos: 6 novos (header, nav, trocar_senha template, 2 suites de teste,
  esta auditoria) + 10 modificados.
- Tokens de cor centralizados em `base.css :root` (11 novos).
- Login/2FA/setup_2FA + trocar-senha em dark theme consistente com parser.
- Header com user-chip (dropdown via `<details>` puro CSS) + nav icone-only
  com role-gate.
- Parser e painel analista plugam header/nav. Nenhum arquivo acima de 500 LOC.

## 2. Etapas concluidas (1-5)

| # | Etapa | Arquivos principais | LOC |
|---|---|---|---|
| 1 | Tokens em `base.css` + hex→var em `upload.css` | `base.css` (+11), `upload.css` (24 subs) | +11 / ~24 subs |
| 2 | Login + 2FA dark theme + subtitulo CCMO | `auth.css` (reescrita), 3 templates auth | ~120 |
| 3 | Rota + template "Trocar senha" + politica de senha | `auth.py` (+42), `user_service.py` (politica), template novo, 8 testes novos | ~240 |
| 4 | `base.html` blocks + partials `header.html`/`nav.html` + CSS | `base.html` (+2), 2 partials, `base.css` (+145), 2 testes novos | ~330 |
| 5 | Parser + painel analista plugam header/nav | `operador/index.html` (+3 / -1), `analista/index.html` (+3) | ~5 |

**Total etapas 1-5:** ~700 LOC alteradas/novas em 16 arquivos. Maior arquivo
tocado: `base.css` com 210 LOC (bem abaixo do limite 500).

## 3. Arquivos entregues (tabela LOC)

| Arquivo | LOC | Estado | Proposito |
|---|---|---|---|
| `app/static/css/base.css` | 210 | estendido (+182) | 11 tokens + header/nav/user-chip |
| `app/static/css/auth.css` | 132 | reescrita | dark theme auth pages |
| `app/static/css/upload.css` | 484 | hex→tokens (24) | zero mudanca visual |
| `app/templates/base.html` | 16 | +2 blocos | `{% block header %}` `{% block nav %}` |
| `app/templates/_components/header.html` | 21 | novo | brand + CCMO + user-chip |
| `app/templates/_components/nav.html` | 50 | novo | icon-only nav role-gate |
| `app/templates/auth/login.html` | 29 | +subtitulo, -h2 | subtitulo CCMO, h2 "Acesso ao SMO" removido |
| `app/templates/auth/login_2fa.html` | 41 | h1 institucional + subtitulo | |
| `app/templates/auth/setup_2fa.html` | 46 | h1 institucional + subtitulo | |
| `app/templates/auth/trocar_senha.html` | 38 | novo | form de troca de senha |
| `app/templates/operador/index.html` | 96 | +2 blocks, -link hardcoded | |
| `app/templates/analista/index.html` | +3 | +2 blocks | (resto pertence a 6.2, nao commitado aqui) |
| `app/routes/auth.py` | 193 | +42 (rota `/trocar-senha`) | GET/POST com validacoes em camadas |
| `app/services/user_service.py` | 247 | politica de senha | SENHA_MIN_LEN=8 + maiuscula + especial |
| `tests/test_trocar_senha.py` | 159 | novo | 4 testes rota + 4 testes politica |
| `tests/test_nav.py` | 91 | novo | 2 testes role-gate (gestor, AREI) |

## 4. Decisoes tomadas (com justificativa)

1. **"Analista" = `gestor`.** Nenhuma role nova. Nav usa
   `current_user.eh_gestor()` para role-gate. Documentado no PROMPT.

2. **Tokens em `base.css :root`, nao arquivo novo.** Evita `shell.css`
   intermediario. Substituicao em `upload.css` foi mecanica — 24 hex
   literais -> variaveis. Hex sem token canonico (0.08, 0.04, 0.15, 0.2,
   0.25, 0.4, 0.6 em gold; verdes/vermelhos legacy do `.upload-status`)
   ficaram como literais. Zero mudanca visual verificada.

3. **Subtitulo CCMO em ASCII** (hifen regular, sem acentos). Convencao do
   projeto — `grep` confirmou zero caracteres acentuados nos templates.

4. **h2 "Acesso ao SMO" removido do login** a pedido do usuario. Login
   agora tem apenas h1 + subtitulo CCMO + form. As paginas 2FA mantem h2
   com o contexto especifico da etapa ("Verificacao em dois fatores",
   "Cadastrar 2FA").

5. **Politica de senha: 8+ chars, 1 maiuscula, 1 especial.** Sobrescreveu
   o SENHA_MIN_LEN=10 anterior. Caractere especial = qualquer char nao
   alfanumerico ASCII (`[^A-Za-z0-9]`). Validacao no service layer
   (`_validar_senha`) — reusado por `create` e `alterar_senha`. Hashes
   existentes no banco nao sao afetados (bcrypt.checkpw ignora politica;
   so bate em novas senhas).

6. **Sem CSRF** em `/trocar-senha` — o app inteiro nao usa CSRF hoje
   (login, setup_2fa, logout tambem nao). Adicionar so aqui seria
   inconsistente. Flaguei como pendente transversal.

7. **Trocar-senha redireciona pra `/` mantendo sessao viva.** Alternativa
   seria logout forcado; pior UX, sem pedido explicito.

8. **Dropdown user-chip via `<details>`/`<summary>` puro CSS.** Zero JS.
   Remove `::-webkit-details-marker` e `::marker`. Borda muda via
   `.user-chip[open] > summary`.

9. **"Minha conta" omitido do dropdown.** `user.perfil` so existe na
   Etapa 8 — referenciar agora geraria `BuildError` em toda render.
   Sera adicionado junto com `/me`.

10. **Endpoint correto e `analista.analista`, nao `analista.index`.** O
    plano listava errado. Corrigido no nav.

11. **Sem `position: sticky`** no header/nav — evita colisao com
    `padding-top: 80px` e gradiente do `#upload-screen`. Pode ser
    revisitado apos Etapa 6.

12. **`app/templates/analista/index.html` commitado parcialmente** via
    `git add -p`. Apenas as 3 linhas dos blocks `header`/`nav` entraram;
    as 36 linhas pre-existentes da Fase 6.2 (top missoes/municipios)
    seguem uncommitted — nao sao escopo desta sessao.

## 5. Testes

Meta do plano: 164 -> ~172. **Entregue: 174.**

### `tests/test_trocar_senha.py` (8 testes)

Rota `/trocar-senha`:
1. `test_get_sem_login_redireciona` — 302 pra `/login`.
2. `test_post_senha_atual_errada` — 401, nao chama `alterar_senha`.
3. `test_post_nova_diferente_da_confirmacao` — 400, nao chama
   `alterar_senha`.
4. `test_post_ok_atualiza_e_redireciona` — 302 nao-login + 1 chamada a
   `alterar_senha(user_id, senha_nova)`.

Politica de senha (unit tests em `_validar_senha`):
5. `test_rejeita_curta` — <8 chars.
6. `test_rejeita_sem_maiuscula`.
7. `test_rejeita_sem_especial`.
8. `test_aceita_senha_valida`.

### `tests/test_nav.py` (2 testes)

Renderiza `_components/nav.html` via blueprint de teste:
1. `test_gestor_ve_todos_os_links` — 5 hrefs admin presentes.
2. `test_arei_nao_ve_links_admin` — so `href="/"` presente; todos os
   admin ausentes.

## 6. Etapas pendentes (6a-d, 7, 8)

| # | Etapa | Arquivos | LOC est. | Risco |
|---|---|---|---|---|
| 6a | `crpms.html` dark theme | 1 template + CSS admin em `base.css` | ~60 | baixo |
| 6b | `missoes.html` dark theme | 1 template + CSS | ~100 | baixo |
| 6c | `municipios.html` dark theme | 1 template + CSS | ~100 | baixo |
| 6d | `triagem_missoes.html` dark theme (modal + banner undo) | 1 template + CSS cuidadoso | ~150 | **medio** (preservar UX modal/undo) |
| 7 | `admin/usuarios.html` dark theme | 1 template + CSS | ~150 | baixo |
| 8 | `/me` perfil readonly + link "Minha conta" no dropdown | `app/routes/user.py` (novo) + template + header.html (+1 linha) + 2 testes | ~80 | trivial |

**LOC estimada restante:** ~640, em ~8 arquivos.
**Testes adicionais previstos:** 2 em `tests/test_perfil.py` (GET sem login ->
401/302; GET com login -> 200 com dados).

## 7. Pontos abertos / pendencias nao-escopo

1. **CSRF nao implementado em nenhum POST do app.** Transversal —
   requer `Flask-WTF` global + token em todos os forms (login, setup_2fa,
   logout, trocar_senha, admin_catalogos, admin.usuarios, triagem).
   Decidir antes do deploy Oracle. **Prioridade: ALTA.**

2. **Parser `#upload-screen` tem `padding-top: 80px`.** Com header+nav
   agora no topo, sobra espaco grande acima do h1. Ajuste simples
   (`padding-top: 32px` ou estrutura mais adequada) pode entrar em 6d
   ou depois.

3. **`/analista` mantem `<header class="analista-header">` interno** com
   "Painel do Analista" + link "Voltar ao Operador". Redundante com o
   nav. Limpeza recomendada em 6b ou depois.

4. **"Minha conta" no dropdown do header** vira na Etapa 8 junto com a
   rota `/me`.

5. **CSRF + `Flask-WTF`** sera necessario antes do Oracle deploy (veja #1).

## 8. Como validar manualmente

Login/auth:
1. `/login` — h1 gold + subtitulo CCMO + form dark. Credenciais erradas
   -> flash vermelho escuro.
2. `/login/2fa` — mesma estrutura, h2 "Verificacao em dois fatores".
3. `/setup-2fa` — QR code com fundo branco sobre card dark.
4. `/trocar-senha` — form dark, valida senha atual, nova >=8 + maiuscula
   + especial. Sucesso redireciona pra `/` com flash info.

Navegacao:
5. `/` (parser, qualquer role) — header com user-chip, nav com icone
   Parser ativo.
6. Click user-chip -> dropdown "Trocar senha" + "Sair" (POST).
7. Login como `gestor` -> nav mostra 6 icones (parser + 5 admin).
8. Login como `operador_arei` ou `operador_alei` -> nav so tem Parser.
9. `/analista` (gestor) -> nav "Painel do Analista" ativo.
10. URLs admin respondem: `/admin/catalogos/{missoes,municipios,crpms,triagem-missoes}`,
    `/admin/usuarios` (ainda em light theme — Etapa 6/7).

## 9. Comando pra retomar

Quando seguir, comecar pela Etapa 6a (`crpms.html` dark theme) — e o menor
risco do bloco admin e estabelece o padrao de classes `.admin-wrap`,
`.admin-table`, `.admin-actions` que 6b/6c/6d/7 vao reusar.
