# AUDITORIA FASE 6.4 — BPMs N:N (uma missao, multiplos BPMs em POA)

Data: 23/04/2026
Escopo: introduzir cardinalidade N:N entre vertices (`smo.fracao_missoes`)
e BPMs, mantendo backcompat 6.3 ate a 6.5 planejar a remocao da coluna
singular `fracao_missoes.bpm_id`.

## 1. Diff de schema (migration 006)

Nova tabela intermediaria — fonte de verdade dos BPMs por vertice:

```sql
CREATE TABLE IF NOT EXISTS smo.fracao_missao_bpms (
    fracao_missao_id UUID NOT NULL REFERENCES smo.fracao_missoes(id) ON DELETE CASCADE,
    bpm_id           UUID NOT NULL REFERENCES smo.bpms(id)           ON DELETE RESTRICT,
    criado_em        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (fracao_missao_id, bpm_id)
);
CREATE INDEX IF NOT EXISTS idx_fmb_bpm ON smo.fracao_missao_bpms(bpm_id);
```

Backfill idempotente a partir do singular; coluna legada marcada DEPRECATED:

```sql
INSERT INTO smo.fracao_missao_bpms (fracao_missao_id, bpm_id)
SELECT id, bpm_id FROM smo.fracao_missoes WHERE bpm_id IS NOT NULL
ON CONFLICT DO NOTHING;

COMMENT ON COLUMN smo.fracao_missoes.bpm_id IS
    'DEPRECATED 6.4 -> smo.fracao_missao_bpms (fonte de verdade). Cache do 1o BPM para analytics legadas; remocao planejada em 6.5.';
```

## 2. Tabela LOC dos arquivos tocados

Alvo do plano: todos os modulos sob 500 LOC.

| Arquivo                                        | LOC | Status  |
|------------------------------------------------|-----|---------|
| migrations/006_missao_bpms_nn.sql              | 41  | OK      |
| app/services/bpm_service.py                    | 156 | OK      |
| app/services/whatsapp_patterns.py              | 233 | OK      |
| app/services/whatsapp_fracoes.py               | 397 | OK      |
| app/services/whatsapp_catalogo.py              | 158 | OK      |
| app/services/db_service.py                     | 470 | OK      |
| app/validators/xlsx_validator.py               | 317 | OK      |
| app/routes/api.py                              | 368 | OK      |
| app/static/js/preview_missoes.js               | 488 | OK      |
| app/static/js/render_cards.js                  | 262 | OK      |
| app/static/css/upload.css                      | 806 | Heranca estilistica (CSS concentrada — fora do escopo de split 6.4) |
| tests/test_fracoes_nn.py                       | 398 | OK      |

## 3. Checklist dos 6 principios

1. **Tipagem forte, sem `any`/`cast`/`unknown` novos**
   - `MissaoVertice.bpm_ids: list[str]` e `bpm_raws: list[str]` no TypedDict.
   - `parse_lista_bpms(trecho: str) -> list[str]`, `_resolver_vertice` e
     `_inserir_vertices` tipam explicitamente lista e auxiliares.
   - Nao foram introduzidos `Any`, `cast` nem `unknown`/typing-ignore
     novos. Os 2 `# type: ignore[attr-defined]` em `whatsapp_catalogo.py`
     sao pre-existentes (import tardio de catalogo_service).

2. **Modularidade / 500 LOC max**
   - Maior modulo Python tocado: `db_service.py` com 470 LOC (abaixo do teto).
   - Helper de parse de lista ficou em `bpm_service.py` (local natural
     — ja concentra normalizacao de BPM), evitando novo modulo.

3. **Seguranca / sanitizacao / CSRF**
   - Todas as queries SQL em `db_service.py` sao parametrizadas via
     psycopg2 (sem f-strings sobre input).
   - `_coagir_bpm_raws` aplica `sanitize_text` em cada item da lista antes
     de armazenar no payload validado (defense in depth — o regex ja
     exclui caracteres problematicos).
   - `_coagir_bpm_ids` converte para `str` explicitamente e deduplica,
     protegendo contra repeticao ou payload malformado.
   - CSRF: nenhum endpoint novo; os endpoints de upload/salvar ja exigem
     CSRF via `@login_required` + middleware existente.

4. **Frontend burro**
   - `preview_missoes.js` nao valida regra de negocio — apenas renderiza
     chips, filtra o catalogo cacheado do backend (/api/catalogos/bpms) e
     coleta `bpm_ids`. A exigencia de BPM em POA e o zeramento por
     `em_quartel` sao enforced em `validate_fracoes` / `validar_vertices_n_n`.
   - `render_cards.js` concatena codigos: sem logica alem do `join(', ')`.

5. **Design elegante / coerente**
   - Chip-picker reusa o idioma visual do combobox de municipio
     (input + `<ul>` absoluto + classe `aberta`). Mesma paleta (`gold-soft`
     / `dark-panel` / `border-muted`), tokens ja definidos em base.css.
   - Chips herdam a cor `gold` usada em badges — sem nova paleta.

6. **Auditoria obrigatoria**
   - Este arquivo. Checklist + LOC + riscos residuais + amostras + diff.

## 4. Pipeline de dados — panorama

```
WhatsApp texto
  |
  v
whatsapp_patterns.RE_MISSAO_MUNICIPIO  -> captura 'bpm' como trecho raw
  |
  v
whatsapp_fracoes._materializar_missoes -> bpm_service.parse_lista_bpms(trecho)
  |                                        => MissaoVertice.bpm_raws: list[str]
  v
whatsapp_catalogo._resolver_vertice    -> cache_bpm[normalizar(raw)]
  |                                        => MissaoVertice.bpm_ids: list[str]
  v
xlsx_validator._normalizar_vertices    -> _coagir_bpm_ids/_raws
                                          em_quartel=True zera bpm_ids
  |
  v
db_service._inserir_vertices           -> smo.fracao_missoes (bpm_id = cache 1o)
                                          smo.fracao_missao_bpms (N linhas)
  |
  v
db_service.fetch_vertices_by_range     -> LATERAL + ARRAY_AGG(bpm_id ORDER BY numero)
                                          => row.bpm_codigos: list[str]
  |
  v
api._hidratar_bpm_codigos               -> preenche bpm_codigos quando ausente
  |
  v
render_cards.js                         -> (bpm_codigos || []).join(', ')
```

## 5. Matriz das 8 variantes (entrada -> `bpm_raws`)

Validada por `TestParseListaBpms` e `TestParserCanonicoMultiBpm`:

| # | Entrada no texto WhatsApp             | bpm_raws produzidos |
|---|---------------------------------------|---------------------|
| 1 | `(20 BPM, 1 BPM)`                      | `['20 BPM', '1 BPM']` |
| 2 | `(20 BPM e 1 BPM)`                     | `['20 BPM', '1 BPM']` |
| 3 | `(20° e 1° BPM)`                       | `['20 BPM', '1 BPM']` |
| 4 | `(20/1 BPM)`                           | `['20 BPM', '1 BPM']` |
| 5 | `20 BPM, 1 BPM`                        | `['20 BPM', '1 BPM']` |
| 6 | `20 BPM e 1 BPM`                       | `['20 BPM', '1 BPM']` |
| 7 | `20° e 1° BPM`                         | `['20 BPM', '1 BPM']` |
| 8 | `20 BPM; 1 BPM`                        | `['20 BPM', '1 BPM']` |

Casos auxiliares cobertos: `(20 BPM)`, `20 BPM`, `(11BPM)`, `(9º BPM)`,
duplicatas colapsadas, `' e '` case-insensitive, strings vazias/brancas.

## 6. Invariantes enforced no backend

- `em_quartel=True` => `bpm_ids=[]` (forcado em `_normalizar_vertices`).
- POA (`crpm_sigla == 'CPC'`) + `em_quartel=False` => `len(bpm_ids) >= 1`
  (bloqueio em `validar_vertices_n_n`).
- Duplicatas em `bpm_ids` sao removidas preservando ordem.
- `bpm_id` legado (singular) no payload e coagido para `bpm_ids` de 1 item
  — transicao 6.3 -> 6.4 sem breaking change.

## 7. Testes

- Total de testes: **223 passed** (era 194 antes da fase; +29 novos).
- Novos grupos:
  - `TestParseListaBpms` — 17 parametros cobrindo 8 variantes + auxiliares.
  - `TestParserCanonicoMultiBpm` — 8 parametros validando o pipeline
    end-to-end via `parse_texto_whatsapp`.
  - `TestValidarVerticesNN64` — 4 casos: preserva lista, em_quartel zera,
    compat singular, deduplicacao.
  - `TestValidarVerticesNN.test_poa_com_multiplos_bpms_ok` — POA com 2
    BPMs passa validacao.

Comando: `python -m pytest -q`
Saida: `223 passed in 3.48s`

## 8. Riscos residuais e follow-ups

1. **Coluna legada `smo.fracao_missoes.bpm_id`**
   - Ainda presente como cache do 1o BPM. Analytics legadas em
     `app/services/analytics_catalogos.py` podem ainda le-la — a remocao
     esta planejada para 6.5, depois de migrar os agregados para usar
     `fracao_missao_bpms`.

2. **UI do preview re-cria o chip-picker a cada evento em `chk`/`muni`**
   - Ao mudar municipio, BPMs sao zerados de proposito (podem nao
     pertencer ao novo muni); ao marcar `em_quartel`, tambem. Efeito
     colateral: nao preservamos selecao entre municipios similares. Custo
     aceitavel no fluxo atual (operador AREI) — se incomodar, e trivial
     filtrar os que seguem validos.

3. **Hidratacao silenciosa de `bpm_codigos`**
   - `_hidratar_bpm_codigos` ignora ids nao resolvidos (defense in depth
     para rollouts parciais). Se o catalogo deletar um BPM em uso,
     `ON DELETE RESTRICT` protege; mas se uma inconsistencia ocorrer, o
     operador ve chip menor sem stack trace — logs do backend
     permanecem o canal de deteccao.

4. **CSS concentrada em `upload.css` (806 LOC)**
   - Fora do teto proposto, mas e heranca pre-6.4. Nao expandi — apenas
     adicionei o bloco dos chips (~95 LOC). Refactor em proximas fases.

## 9. Arquivos criados/modificados

**Criados**
- `migrations/006_missao_bpms_nn.sql`
- `AUDITORIA_6_4.md` (este arquivo)

**Modificados**
- `app/services/bpm_service.py` — `parse_lista_bpms` + constantes regex.
- `app/services/whatsapp_patterns.py` — `RE_MISSAO_MUNICIPIO` com captura
  de lista de BPMs (8 variantes) na named group `bpm`.
- `app/services/whatsapp_fracoes.py` — emite `bpm_raws: list[str]`.
- `app/services/whatsapp_catalogo.py` — resolve lista, aviso por raw nao
  encontrado.
- `app/services/db_service.py` — `_inserir_vertices` insere N linhas em
  `fracao_missao_bpms`; `fetch_vertices_by_range` agrega via LATERAL +
  `ARRAY_AGG(bpm.codigo ORDER BY bpm.numero)`.
- `app/validators/xlsx_validator.py` — `MissaoVertice.bpm_ids/bpm_raws`,
  `_coagir_bpm_ids/_raws`, `validar_vertices_n_n` checa lista.
- `app/routes/api.py` — `_hidratar_bpm_codigos` plural.
- `app/static/js/preview_missoes.js` — chip-picker substitui select
  singular, `coletarVertices` emite `bpm_ids: string[]`.
- `app/static/js/render_cards.js` — `(bpm_codigos || []).join(', ')`.
- `app/static/css/upload.css` — estilos `.bpm-chips` e afins.
- `tests/test_fracoes_nn.py` — parametrizados + TestValidarVerticesNN64.
