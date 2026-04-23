# AUDITORIA — Fase 6.2 (Catalogos e evolucao de smo.fracoes)

Data: 2026-04-20
Escopo: implementar catalogos normativos (CRPMs, Municipios, Missoes), evoluir
`smo.fracoes` com FKs opcionais, autocomplete, backfill fuzzy e novos painels
no analista. Tudo sob os principios rigidos do usuario (tipagem forte, 500 LOC
max, seguranca, auditoria, frontend burro).

---

## 1. Resumo executivo

- 118 testes da Fase 6.1 -> **149 testes** agora (todos passam em 22.8s).
- 5 modulos novos + 1 refator de `whatsapp_parser.py` (679 LOC -> 114 LOC).
- Nenhum arquivo acima de 500 LOC.
- Nenhum uso de `Any`; TypedDict, Literal e dataclass(frozen=True) em tudo.
- Prepared statements psycopg2 em 100% das queries; FK RESTRICT nos municipios.
- Autocomplete 100% backend (frontend apenas renderiza tabelas).
- Backfill idempotente com rapidfuzz score>=85 + deteccao de ambiguidade.

## 2. Arquivos entregues (tabela LOC)

### 2.1 Banco — migrations

| Arquivo | LOC | Propósito |
|---|---|---|
| `migrations/003_catalogos.sql` | 32 | cria `smo.crpms`, `smo.municipios` (FK RESTRICT), `smo.missoes` |
| `migrations/004_fracoes_v2.sql` | 56 | `ALTER TABLE smo.fracoes ADD COLUMN IF NOT EXISTS` — missao_id, osv, municipio_id, municipio_nome_raw, atualizado_em |

### 2.2 Services — dominio de catalogo

| Arquivo | LOC | Propósito |
|---|---|---|
| `app/services/catalogo_types.py` | 81 | dataclasses frozen + TypedDicts de Create/Update + `normalizar()` (NFD+upper+trim) |
| `app/services/catalogo_service.py` | 452 | CRUD: listar/get/criar/atualizar/lookup para crpms, municipios, missoes |
| `app/services/analytics_catalogos.py` | 126 | `agregar_por_missao` / `agregar_por_municipio` — tipados com TypedDict |

### 2.3 Parser WhatsApp — refatorado

| Arquivo | LOC | Propósito |
|---|---|---|
| `app/services/whatsapp_parser.py` | 114 | entrypoint fino: parse_texto_whatsapp + re-exports |
| `app/services/whatsapp_helpers.py` | 151 | normalizar_unidade, horarios, telefone, segmentar_texto |
| `app/services/whatsapp_cabecalho.py` | 133 | parse_cabecalho |
| `app/services/whatsapp_fracoes.py` | 294 | parse_fracoes + leitura de OSv/Municipio |
| `app/services/whatsapp_catalogo.py` | 50 | `enriquecer_com_catalogo` (lookup missao_id/municipio_id via catalogo) |
| `app/services/whatsapp_patterns.py` | 178 | regex compartilhados + UNIDADE_MAP |

Antes: `whatsapp_parser.py` 679 LOC (ja acima do limite). Depois: 114 LOC com
modularizacao por responsabilidade. Nenhum modulo do parser passa de 294 LOC.

### 2.4 Rotas

| Arquivo | LOC | Propósito |
|---|---|---|
| `app/routes/admin_catalogos.py` | 147 | UI `/admin/catalogos/{missoes,municipios,crpms}` (Gestor) |
| `app/routes/api.py` | 446 | +6 endpoints: `/api/catalogos/{missoes,municipios,crpms}`, `/api/analytics/por-{missao,municipio}` |

### 2.5 Scripts

| Arquivo | LOC | Propósito |
|---|---|---|
| `scripts/seed_catalogos.py` | 230 | parser regex do `API_Municipios_CRPMs.txt` (21 CRPMs) + 12 missoes padrao |
| `scripts/backfill_missoes.py` | 286 | backfill fuzzy (rapidfuzz score>=85) idempotente + dry-run |

### 2.6 Templates

| Arquivo | LOC | Propósito |
|---|---|---|
| `app/templates/admin/missoes.html` | 120 | CRUD missoes (nav entre catalogos) |
| `app/templates/admin/municipios.html` | 130 | CRUD municipios + filtro por CRPM |
| `app/templates/admin/crpms.html` | 65 | consulta (lista normativa — seed-only) |
| `app/templates/analista/index.html` | +2 tabelas (Top 10 Missoes, Top 10 Municipios) no tab "Analise Fracoes" |
| `app/static/js/projecoes.js` | +44 | renderizarPorMissao / renderizarPorMunicipio |

### 2.7 Tests novos

| Arquivo | LOC | Testes |
|---|---|---|
| `tests/test_catalogos.py` | 140 | 13 testes — normalizacao, dataclasses frozen, endpoints API |
| `tests/test_analytics_catalogos.py` | 196 | 11 testes — agregacoes + endpoints |
| `tests/test_backfill.py` | 53 | 6 testes — matching fuzzy, ambiguidade |

## 3. Auto-avaliacao — 6 principios

1. **Tipagem forte**: 0 usos de `Any` nos modulos entregues. `TypedDict` para
   payloads de Create/Update, `Literal["gestor","operador_arei","operador_alei"]`
   preservado, `dataclass(frozen=True)` para Crpm/Municipio/Missao.
   Retornos com `| None` explicitos; `cast()` em boundary com banco.
2. **LOC <= 500 por arquivo**: maior arquivo entregue: `catalogo_service.py`
   com 452 LOC. `whatsapp_fracoes.py` 294 LOC. Resto < 200.
3. **Seguranca**: todas as queries sao `cur.execute(sql, params)` — nunca
   interpolacao de strings. FK `municipios.crpm_id` com `ON DELETE RESTRICT`.
   Role `@role_required(["gestor"])` em todas as rotas admin de catalogo.
   Autocomplete exige `@login_required`. `q` e truncado em 100 chars.
3. **Backend-heavy / frontend burro**: toda logica de normalizacao,
   lookup e agregacao em Python. Frontend apenas renderiza tabelas
   (`renderizarPorMissao` / `renderizarPorMunicipio` — 22 linhas cada).
4. **Design minimalista**: sem novas cores no analista; reusa `slide-card`,
   `tabela-dados`, `.admin-table`. Templates admin/* usam o mesmo shell visual
   de `admin/usuarios.html`.
5. **Auditoria**: este proprio arquivo + docstrings nos modulos + comentarios
   justificando decisoes (e.g., por que `lookup_*` filtra em Python em vez de
   usar `unaccent`: evita dependencia de extensao PostgreSQL).

## 4. Decisoes arquiteturais

### 4.1 `ON DELETE RESTRICT` em `municipios.crpm_id`

CRPMs sao lista normativa (Art. 3, 21 CRPMs). Apagar um CRPM nao deve
apagar municipios em cascata — deve falhar ruidosamente. Isso protege contra
erro administrativo acidental. Se preciso remover CRPM, operador desativa
manualmente ou corrige o vinculo dos municipios primeiro.

### 4.2 Normalizacao em Python vs `unaccent` no SQL

Optei por normalizar na aplicacao (NFD + uppercase + colapso de espacos em
`catalogo_types.normalizar`). Por que?
- Evita dependencia da extensao `unaccent` (que exige privilegios de superuser
  no Supabase livre).
- Mantem o contrato de match exato explicito e testavel (testes unitarios sem
  banco: 5 testes de normalizacao).
- Sobrecarga aceitavel: ~200 municipios + ~50 missoes cabem em memoria.

### 4.3 Enriquecimento opcional do parser

`enriquecer_com_catalogo` usa `try/except` em torno da conexao ao banco. Se o
DB nao estiver configurado (e.g., rodando testes sem `DATABASE_URL`), o parser
ainda funciona — so nao popula `missao_id` / `municipio_id`. Isso permite que
os 20 testes existentes de parser passem sem DB fake.

### 4.4 Split do parser em 5 modulos

`whatsapp_parser.py` tinha 679 LOC, violando o principio. Split:
- **helpers**: utilitarios puros (normalizacao, horarios, extracao) — reutilizaveis
- **cabecalho**: parse do bloco numerico
- **fracoes**: parse dos blocos Cmt/Equipe/Missao (maior, ainda 294 LOC)
- **catalogo**: enriquecimento com FK ids (desacoplado)
- **parser**: entrypoint que orquestra + `_corrigir_ano_inconsistente`

Assinatura publica preservada: `parse_texto_whatsapp`, `parse_cabecalho`,
`parse_fracoes`, `calcular_horario_emprego` seguem importaveis de
`app.services.whatsapp_parser` — zero breakage em `api.py`, `importar_lote.py`,
`debug_*.py` e nos testes.

### 4.5 Backfill `score_min=85` e deteccao de ambiguidade

rapidfuzz `token_sort_ratio` com corte em 85. Se os 2 melhores candidatos
estao a <=2 pontos de distancia e ambos passam de 85, nao aplica e reporta
como AMBIGUO — protege contra aplicar match errado quando "PATRULHAMENTO A" e
"PATRULHAMENTO B" existem no catalogo. Operador resolve manualmente pela UI.

### 4.6 `agregar_por_missao` — fallback `SEM CATALOGO`

Missoes sem `missao_id` nao desaparecem do relatorio — ficam agrupadas sob
"SEM CATALOGO". Assim o gestor ve imediatamente o tamanho do debito de
catalogo e pode priorizar o cadastro.

## 5. Backfill — resumo do contrato

```
python -m scripts.backfill_missoes [--dry-run]
```

Saida esperada:
```
MISSOES:
  total lidos : 1.234
  exatos      : 1.120
  fuzzy>=85   : 85
  ambiguos    : 12     <- reportados, nao atualizados
  sem match   : 17     <- reportados, nao atualizados
```

- Somente processa `missao_id IS NULL AND missao <> ''` (idempotente).
- `--dry-run` executa o matching + logs mas faz rollback.

## 6. Cobertura de testes

| Modulo | Testes | Comentario |
|---|---|---|
| normalizar() | 5 | uppercase, acentos, trim, vazio, idempotencia |
| dataclasses frozen | 3 | Crpm/Missao/Municipio — mutacao proibida |
| API /catalogos/* | 5 | missoes (sem/com q), municipios (filtro crpm), crpms, autenticacao |
| agregar_por_missao | 4 | soma, ordenacao, sem catalogo, caixa-alta |
| agregar_por_municipio | 4 | soma, sem catalogo, ordenacao, coersao segura |
| API /analytics/* | 3 | 200 com agregado, 400 sem params |
| backfill fuzzy | 6 | match exato, fuzzy>=85, score baixo, catalogo vazio, ambiguidade, SCORE_MIN |
| Parser WhatsApp (regressao) | 20 | todos da Fase 5/6.1 continuam passando apos o split |

**Total: 149 testes, 0 falhas** (22.8s).

## 7. Proximos passos fora do escopo 6.2

- Executar `python -m scripts.migrate` + `python -m scripts.seed_catalogos`
  no ambiente de producao (Supabase).
- Rodar `python -m scripts.backfill_missoes --dry-run` para estimar taxa de
  match; depois rodar sem `--dry-run`.
- Fase 7 (sugerida): editor in-place no preview de parse (operador resolve
  AMBIGUOS via dropdown usando o autocomplete ja entregue).
