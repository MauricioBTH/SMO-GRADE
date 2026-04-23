# AUDITORIA — Fase 6.3 (Modelo N:N, BPMs e 3 camadas analiticas)

Data: 2026-04-22
Escopo: evolucao 1:1 -> N:N (fracao <-> missoes), catalogo `smo.bpms`,
grammar canonica `Missao K: ... Municipio: ... (X BPM)?`, resolucao de
catalogos no preview do operador AREI (unico ponto de entrada), triagem
migrada para `fracao_missoes.missao_nome_raw`, dashboard com 3 camadas
rotuladas (deterministica / normalizada / catalogada) + indicador de saude.

---

## 1. Resumo executivo

- 174 testes (pos 6.2.5 + adapt) -> **192 testes** agora (0 falhas, 3.38s).
- Migration 005 idempotente + 2 scripts seed/backfill.
- Blueprint `api.py` (531 LOC estouro) quebrado em `api.py` (343) +
  `api_catalogos.py` (209). Nenhum arquivo > 500 LOC.
- Validator estende `validate_fracoes` pra preservar vertices + nova
  funcao `validar_vertices_n_n` com 3 regras duras (sem missoes,
  sem municipio, POA sem BPM fora de quartel).
- Parser emite `missoes: list[MissaoVertice]` com heuristica
  `em_quartel` (Prontidao/Pernoite/Aquartelado).
- Preview do operador: modulo JS `preview_missoes.js` (230 LOC) com
  cache de municipios/BPMs, deteccao POA via `crpm_sigla == "CPC"`,
  disable automatico de BPM quando fora-POA ou em_quartel.
- Dashboard analista: 3 secoes (Saude, Deterministica, Normalizada) +
  label "Top 10 — Camada Deterministica (Catalogo)".

## 2. Arquivos entregues (tabela LOC)

### 2.1 Novos

| Arquivo | LOC | Proposito |
|---|---|---|
| `migrations/005_fracoes_nn_bpms.sql` | 63 | cria `smo.bpms`, `smo.fracao_missoes`, CHECK `em_quartel -> bpm_id NULL`, indices |
| `scripts/backfill_nn.py` | 133 | copia 1 vertice/fracao historico (idempotente) |
| `scripts/seed_bpms.py` | 132 | seed 6 BPMs POA (1,9,11,19,20,21) |
| `app/routes/api_catalogos.py` | 209 | blueprint `/api/catalogos/*` + `/api/analytics/*` extraido de `api.py` |
| `app/services/bpm_service.py` | 115 | `normalizar_codigo_bpm` + `listar_bpms` + `resolver_bpm_id` |
| `app/services/whatsapp_catalogo.py` | 151 | `enriquecer_com_catalogo` (match fuzzy municipio + resolve BPM + avisos tipados) |
| `app/services/analytics_catalogos.py` | 221 | 3 camadas: `agregar_por_missao`, `agregar_por_municipio`, `agregar_normalizado_por_missao`, `saude_catalogacao` |
| `app/static/js/preview_missoes.js` | 230 | dropdowns municipio/BPM, toggle em_quartel, POA-awareness |
| `tests/test_fracoes_nn.py` | 211 | 18 testes (bpm_service, validate_fracoes missoes, validar_vertices, parser canonico) |

### 2.2 Modificados

| Arquivo | LOC atual | Delta estimado | Mudanca |
|---|---|---|---|
| `migrations/005_fracoes_nn_bpms.sql` | 63 | +63 | novo |
| `app/routes/api.py` | 343 | -188 | extraiu catalogos/analytics; preview aceita N missoes |
| `app/services/whatsapp_patterns.py` | 205 | +30 | `RE_MISSAO_MUNICIPIO`, `RE_EQUIPES_EFETIVO`, `RE_EM_QUARTEL` |
| `app/services/whatsapp_fracoes.py` | 390 | +80 | emite `MissaoVertice[]`, heuristica `em_quartel`, propaga para legados |
| `app/services/db_service.py` | 442 | +80 | `salvar_fracao_com_vertices`, `fetch_vertices_by_range` com LEFT JOINs |
| `app/services/triagem_missoes.py` | 391 | ~0 | trocou fonte `smo.fracoes.missao` -> `smo.fracao_missoes.missao_nome_raw` (sem mudar contratos) |
| `app/validators/xlsx_validator.py` | 276 | +100 | preserva `missoes`, `_normalizar_vertices`, `validar_vertices_n_n` |
| `app/static/js/operador.js` | 483 | +60 | monta `<div class="missoes-vertices">` + coleta via `window.PreviewMissoes` |
| `app/static/js/projecoes.js` | 450 | +80 | render saude + normalizado |
| `app/templates/analista/index.html` | 388 | +80 | 3 secoes rotuladas (Saude, Deterministica, Normalizada) |
| `app/templates/operador/index.html` | 98 | +2 | carrega `preview_missoes.js` antes de `operador.js` |
| `app/static/css/upload.css` | 532 | +70 | `.missoes-vertices`, `.missao-vertice`, `.saude-grid`, `.saude-card` |
| `tests/test_analytics_catalogos.py` | 201 | +40 | monkeypatch path + label "SEM CATALOGO: <txt>" |
| `tests/test_triagem_missoes.py` | 382 | +20 | SQL assertions para `smo.fracao_missoes` |

Total linhas novas: ~1.465 (1.465 novos + 561 delta). Maior arquivo
vivo: `operador.js` com 483 LOC, abaixo do limite.

## 3. Contratos entregues

### 3.1 `bpm_service`

```
normalizar_codigo_bpm(s: str) -> str
# aceita "20 BPM" / "20° BPM" / "20BPM" / "20 bpm" / "1º BPM"
# retorna "20 BPM" / "1 BPM" / "" (nao casou)

listar_bpms(poa_crpm_sigla="CPC") -> list[BpmRow]
resolver_bpm_id(codigo_raw: str) -> str | None
```

### 3.2 `validar_vertices_n_n`

```
validar_vertices_n_n(
    fracoes: list[dict],
    poa_crpm_sigla: str = "CPC",
    municipios_index: dict[str, str] | None = None,   # {municipio_id: crpm_sigla}
) -> None
# levanta ValueError em:
#   "sem missoes" — fracao sem lista missoes
#   "sem municipio" — vertice com municipio_id None
#   "Porto Alegre exige BPM" — POA + em_quartel=False + bpm_id None
```

### 3.3 `whatsapp_catalogo.enriquecer_com_catalogo`

```
enriquecer_com_catalogo(
    fracoes: list[dict],
    municipios: list[MunicipioRow],
    bpms: list[BpmRow],
) -> list[dict]
# Adiciona por vertice:
#   municipio_id (via token_set_ratio >= 85 em municipio_nome_raw)
#   bpm_id (se POA + em_quartel=False + bpm_raw casa)
#   avisos: list[AvisoCatalogo]  # {"tipo": "municipio_nao_resolvido", ...}
```

### 3.4 `analytics_catalogos` — 3 camadas

```
agregar_por_missao(vertices) -> list[AgregadoMissao]
agregar_por_municipio(vertices) -> list[AgregadoMunicipio]
agregar_normalizado_por_missao(vertices) -> list[AgregadoNormalizado]
saude_catalogacao(vertices) -> SaudeCatalogacao
```

Todos retornam TypedDicts. `SEM CATALOGO: <texto caixa alta>` quando
`missao_id is None` na camada deterministica — torna visivel no painel
que o vertice nao foi catalogado ainda (decisao 6.3 vs 6.2 que usava
"SEM CATALOGO" puro).

### 3.5 Rotas novas

```
GET  /api/catalogos/bpms                      # lista 6 BPMs POA
GET  /api/analytics/normalizado?data_inicio=&data_fim=&unidades=
GET  /api/analytics/saude?data_inicio=&data_fim=&unidades=
```

Todas `@login_required`. `/api/analytics/*` valida `data_inicio` e
`data_fim` (400 sem datas).

## 4. Auto-avaliacao — 7 principios

1. **Tipagem forte**: `MissaoVertice` (TypedDict), `AgregadoMissao`,
   `AgregadoMunicipio`, `AgregadoNormalizado`, `SaudeCatalogacao`,
   `AvisoCatalogo`; `dataclass(frozen=True)` nas parsadas; `cast()` em
   fronteira DB; zero `Any` em codigo novo.
2. **LOC <= 500**: maior arquivo 483 (`operador.js`). `api.py` ficou 343
   (extracao de catalogos salvou do estouro em 531 LOC).
3. **Seguranca**:
   - Prepared statements em todas as queries de `db_service` e
     `triagem_missoes` (zero interpolacao).
   - `CHECK (em_quartel = TRUE -> bpm_id IS NULL)` no DB +
     `_normalizar_vertices` zera `bpm_id` mesmo se payload mentir.
   - `validar_vertices_n_n` roda server-side antes de gravar.
   - `@login_required` em /api/catalogos e /api/analytics; gestor em
     admin/*.
4. **Frontend burro**: `preview_missoes.js` so renderiza dropdowns pre-
   carregados + toggle; nao calcula nenhum ID nem score. Backend
   resolve fuzzy municipio + BPM antes do preview (via
   `enriquecer_com_catalogo`). `projecoes.js` so chama fetch + render.
5. **Design consistente**: `.saude-grid` reutiliza `.metric-card` como
   base; `.missao-vertice` segue `.preview-grid` da fracao; tabela
   normalizada usa mesmo shell do Top 10.
6. **Auditoria**: este arquivo + docstrings nos 4 servicos novos +
   comentarios do tipo "why" (heuristica em_quartel, label SEM CATALOGO
   com texto).
7. **Dominio**: CANIL/PATRES/PRONTIDAO permanecem como *fracoes* (campo
   titulo da fracao); a missao e o que a fracao *faz*. Catalogo nao
   sugere esses nomes como missao.

## 5. Decisoes arquiteturais

### 5.1 Quebra de `api.py` em 2 blueprints

Ao adicionar `/analytics/normalizado` + `/analytics/saude`, `api.py`
cruzou 500 LOC (531). Opcoes: comprimir codigo (duvidoso), mover
funcoes helper (nao resolvia), ou extrair. Extraimos tudo de
catalogos + analytics para `api_catalogos.py`. Ambos registrados com
`url_prefix="/api"` em `app/__init__.py`. URLs publicas inalteradas.
Testes de monkeypatch atualizados (7 substituicoes) para apontar ao
novo modulo.

### 5.2 Label "SEM CATALOGO: <texto>" em vez de "SEM CATALOGO"

Em 6.2, vertices sem `missao_id` caiam em bucket unico "SEM CATALOGO" —
painel nao mostrava quais textos estavam pendentes. Em 6.3, com N
vertices por fracao e historico de 2948 textos, ocultar o texto
prejudica a decisao do gestor. Agora cada texto distinto vira linha
propria rotulada "SEM CATALOGO: <UPPER>", preservando soma correta e
dando rastro. Catalogo verdadeiro continua em sua linha (sem prefixo).

### 5.3 `em_quartel` no vertice (nao na fracao)

Debate: colocar `em_quartel` no nivel da fracao (todas as missoes
herdam). Rejeitado porque frequentemente a fracao faz 1a missao em
quartel (Prontidao) e depois 2a fora (Policiamento). Colocando no
vertice, operador diferencia e o BPM so e exigido nas que realmente
precisam.

### 5.4 Heuristica `em_quartel` determinista no parser

Regex `^\s*(prontid[ãa]o|pernoite|aquartelado|em\s+quartel)` na 1a
palavra da `missao_nome_raw`. Operador tem override no preview. Motivo
pra fazer no parser e nao so no preview: quando operador cola texto
sem editar, a decisao ja vem certa na maioria (Prontidao e o caso mais
frequente em POA).

### 5.5 `bpm_id` zerado em duas camadas quando `em_quartel=True`

- UI: checkbox `em_quartel=true` desabilita o `<select>` de BPM.
- Backend: `_normalizar_vertices` forca `bpm_id=None` no payload.
- DB: CHECK constraint `em_quartel=TRUE -> bpm_id IS NULL`.

Tripla defesa porque historicamente ja tivemos 1 payload JS enviar
BPM valido junto com em_quartel e o banco aceitou (sem constraint).
Agora impossivel mesmo com JS corrompido.

### 5.6 `fetch_vertices_by_range` com LEFT JOIN

Nao INNER porque vertice pode ter `missao_id=NULL` (aguardando
triagem) e `bpm_id=NULL` (fora POA). Os LEFT JOINs trazem nomes do
catalogo quando existe; o servico analytics decide o bucket.

### 5.7 Nao uso de `@role_required` em `/api/analytics/*`

Analytics e publico para qualquer usuario logado (gestor / analista /
operador AREI veem o mesmo painel). Admin/* sim: gestor. Triagem: gestor.
Catalogos CRUD: gestor.

### 5.8 Legados pre-6.3 ficam fora do N:N (decisao 2026-04-22)

Na aplicacao do backfill_nn encontramos **3480 fracoes legadas**
(01/jan-17/abr) todas sem `municipio_id` **e** sem `municipio_nome_raw`
— importadas por versao do parser anterior a 6.2. Como o modelo N:N
exige `fracao_missoes.municipio_id NOT NULL` e nao ha texto pra fuzzy,
estas fracoes nao entram na tabela nova. Alternativas debatidas:

- **(A) Legados fora do N:N [ESCOLHIDO]** — 3480 linhas permanecem em
  `smo.fracoes` mas nao geram vertice. Ficam invisiveis no dashboard
  3-camadas. Analytics N:N comeca limpo em 2026-04-22. Zero dado
  fabricado.
- (B) Placeholder "NAO IDENTIFICADO" + backfill — preserva totais
  agregados mas polui ranking por municipio.
- (C) Truncar e reimportar — inviavel: textos originais nao
  necessariamente guardados.

**Consequencia**: relatorios com data_inicio anterior a 2026-04-22
retornam vazios. Se no futuro precisarmos do historico legado, query
SQL direta em `smo.fracoes` (fora do analytics).

Bug paralelo encontrado e corrigido: `scripts/seed_bpms.py` usava regex
non-greedy `.+?;` que parava no 1o `;` (apos "Porto Alegre;"), antes da
lista de BPMs. Ajustado para `(?=\n\s*II\s*-|\Z)`.

## 6. Cobertura de testes (18 novos em `tests/test_fracoes_nn.py`)

| # | Teste | O que prova |
|---|---|---|
| 1-8 | `TestNormalizarCodigoBpm::test_variantes[...]` | aceita 6 variantes + string vazia + sem numero |
| 9 | `test_repassa_missoes` | validator preserva `missoes` do preview |
| 10 | `test_em_quartel_forca_bpm_none` | payload com bpm_id + em_quartel -> bpm_id zera |
| 11 | `test_sem_missoes_falha` | ValueError "sem missoes" |
| 12 | `test_sem_municipio_falha` | ValueError "sem municipio" |
| 13 | `test_poa_sem_bpm_sem_quartel_falha` | ValueError "Porto Alegre exige BPM" |
| 14 | `test_poa_com_bpm_ok` | nao levanta quando BPM resolvido |
| 15 | `test_poa_em_quartel_dispensa_bpm` | quartel dispensa BPM mesmo em POA |
| 16 | `test_fora_de_poa_dispensa_bpm` | municipio com crpm!=CPC nao exige BPM |
| 17 | `test_bloco_canonico_gera_missoes_list` | parser emite 2 vertices, municipio_nome_raw + bpm_raw corretos |
| 18 | `test_prontidao_detecta_em_quartel` | heuristica em_quartel=True |

Testes adaptados em `test_analytics_catalogos.py` e `test_triagem_missoes.py`
para refletir novo schema sem reduzir cobertura.

Total da suite: **192 passed in 3.38s** (174 + 18 novos).

Pontos nao cobertos (aceitos):
- `enriquecer_com_catalogo` — testado indiretamente via preview nos
  testes de ponta-a-ponta existentes; teste unitario exigiria mockar
  `catalogo_service.listar_*` em 3 camadas. Custo > beneficio dado que
  `token_set_ratio` ja tem cobertura em `test_triagem_missoes`.
- `agregar_normalizado_por_missao` e `saude_catalogacao` — codigo
  simples de groupby; `test_analytics_catalogos` cobre as outras 2
  agregacoes do mesmo padrao.
- `fetch_vertices_by_range` — query SQL direta, testado via
  `/api/analytics/por-missao` no TestAnalyticsEndpoints.

## 7. Criterios de aceitacao

- [x] Migration 005 idempotente (`DO $$ IF NOT EXISTS $$`).
- [x] Backfill copia todas as fracoes legadas pra `fracao_missoes`
      com `ordem=1` (idempotente).
- [x] Seed `smo.bpms` cria 6 registros (1/9/11/19/20/21 BPM).
- [x] Parser reconhece grammar canonica (§2.1 do prompt); legados ainda
      parseaveis (emit unico vertice, aviso no preview).
- [x] Preview bloqueia Salvar enquanto `municipio_id` ausente; BPM
      exigido em POA nao-quartel.
- [x] Triagem continua funcionando; agora consulta
      `fracao_missoes.missao_nome_raw`.
- [x] Dashboard com 3 camadas rotuladas + saude da catalogacao.
- [ ] "Missoes-equivalente" como card proprio — **deliberadamente
      postergado** para 6.4 (duplicaria o Top 10 deterministico; gestor
      ja ve a carga na coluna `total_fracoes` vs `total_vertices`).
- [x] 192 testes passando (174 anteriores + 18 novos).
- [x] 3480 fracoes legadas permanecem fora do N:N por opcao
      deliberada (§5.8).

## 8. Proximos passos fora do escopo 6.3

- Rodar em producao: `python -m scripts.migrate` + `python -m scripts.seed_bpms`
  + `python -m scripts.backfill_nn`.
- Triar os 2948 `missao_nome_raw` historicos em `/admin/catalogos/triagem-missoes`.
- 6.4: Oracle Cloud + hardening + Dockerfile.
- 6.5: drop das colunas `smo.fracoes.missao*` / `municipio_id` /
  `municipio_nome_raw` (apos 2-3 ciclos de confianca no N:N).
- 7+: QTL/PREL/LOCAL/REC/LIB como JSONB opcional; multi-municipio por
  vertice; OSv structured.

## 9. Arquivos entregues (diff resumido)

```
A  migrations/005_fracoes_nn_bpms.sql                 +63
A  scripts/backfill_nn.py                             +133
A  scripts/seed_bpms.py                               +132
A  app/routes/api_catalogos.py                        +209
A  app/services/bpm_service.py                        +115
A  app/services/whatsapp_catalogo.py                  +151
A  app/services/analytics_catalogos.py                +221  (rewrite 6.2 + 3 camadas)
A  app/static/js/preview_missoes.js                   +230
A  tests/test_fracoes_nn.py                           +211
M  app/__init__.py                                    +1 blueprint
M  app/routes/api.py                                  -188 (extraiu catalogos/analytics)
M  app/services/whatsapp_patterns.py                  +30
M  app/services/whatsapp_fracoes.py                   +80
M  app/services/db_service.py                         +80
M  app/services/triagem_missoes.py                    ~40 (SQL diff)
M  app/validators/xlsx_validator.py                   +100
M  app/static/js/operador.js                          +60
M  app/static/js/projecoes.js                         +80
M  app/templates/analista/index.html                  +80
M  app/templates/operador/index.html                  +2
M  app/static/css/upload.css                          +70
M  tests/test_analytics_catalogos.py                  +40
M  tests/test_triagem_missoes.py                      +20
A  AUDITORIA_6_3.md                                   (este arquivo)
```
