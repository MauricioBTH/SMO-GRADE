# PROMPT — Fase 6.3: Modelo N:N, BPMs de POA e 3 camadas analíticas

Data: 2026-04-22
Absorve: `PROMPT_FASE6_2_5.md` (triagem vira §8 deste documento)
Desloca: ALEI + Oracle Cloud para Fase 6.4 (antes era 6.3)

---

## 1. Objetivo

Evoluir SMO de **1:1 (fração→missão)** para **N:N (fração↔missões)** para capturar
o padrão real: 70% das frações executam 2–3 missões sequenciais no mesmo turno,
com o mesmo efetivo e comando.

Efeitos combinados:
- Normatizar entrada via grammar canônica (campanha de normatização inevitável).
- Introduzir catálogo `smo.bpms` para granularidade intra-POA.
- Operador AREI resolve `municipio_id` e `bpm_id` no preview (lista fechada).
- Analista cataloga **somente** `missao_id` assíncrono (triagem).
- Dashboard expõe **3 camadas de confiabilidade** que nunca se somam.

### 1.1 Modelo de entrada — definitivo

**AREI centralizado é o modelo permanente.** Decisão de 2026-04-22: ALEI
multi-unidade **não existirá** no roadmap. Todas as escalas chegam via
WhatsApp do escalante da unidade → operador AREI lê no celular/PC, copia o
texto e cola em `/importar-texto`.

Consequências práticas:
- Um único operador edita o que o parser errou antes de salvar.
- Não há `criado_por` planejado (nem migration que adicionaria).
- Não há `unidade_match_required` — AREI grava qualquer unidade.
- Não há consolidação por unidade — AREI é o próprio consolidador (vê tudo no painel).
- Preview é desenhado só pra AREI; não há restrição de UX pra ALEI futuro.

---

## 2. Modelo padronizado final

### 2.1 Bloco canônico

```
PELOTÃO DE PRONTIDÃO
Cmt: TEN PM RENATO (55) 99645-6325
Equipes: 05 (20 PMs)
Missão 1: Prontidão Município: Porto Alegre
Missão 2: Reserva de OCD Município: Canoas
Missão 3: Combate aos CVLIs Município: Porto Alegre (20° BPM)
Horário: 20:00 às 02:00
```

### 2.2 Regras

| Linha | Obrigatória | Tipo | Regra |
|---|---|---|---|
| Título | sim | texto livre | 1ª linha do bloco, CAIXA ALTA |
| `Cmt:` | sim | string | nome + telefone |
| `Equipes: N (M PMs)` | sim | 2 ints | N equipes, M efetivo total |
| `Missão K:` | ≥1 | texto | K = 1..N sequencial |
| `Município:` | sim por missão | catálogo fechado | operador escolhe no preview |
| `(X° BPM)` | obrigatório se POA **e** `em_quartel = false` | catálogo fechado | operador escolhe no preview |
| `em_quartel` (flag) | sim por missão | bool | parser infere `true` quando `missao_nome_raw` casa com Prontidão/Pernoite/Aquartelado; operador override no preview |
| `Horário:` | sim | `HH:MM às HH:MM` | único pro bloco — propaga pras N missões |

### 2.3 Invariantes

- Um bloco → **1 `fracao`** + **N `fracao_missoes`**.
- `cmt`, `equipes_n`, `efetivo_n`, `horario_inicio`, `horario_fim` vivem na fração.
- `missao_id`, `missao_nome_raw`, `municipio_id`, `bpm_id`, `em_quartel` vivem no vértice.
- Regra dura: `bpm_id IS NOT NULL` ↔ `municipio = POA` **AND** `em_quartel = FALSE`.
- Missão repetida em blocos distintos = vértices distintos (não deduplica).

---

## 3. Divisão de trabalho

| Ator | Responsabilidade | Campos | Momento |
|---|---|---|---|
| **Parser** | extração determinística | data, fração, cmt, equipes_n, efetivo_n, horário, `missao_nome_raw`, `municipio_nome_raw`, `bpm_raw` | entrada |
| **Operador AREI** (único ponto de entrada na 6.3) | cola texto WhatsApp, edita campos do parser se necessário, resolve catálogos fechados | todo conteúdo da fração + `municipio_id` (sempre), `bpm_id` (se POA) | preview antes de salvar |
| **Analista/Gestor** | cataloga missão | `missao_id` | assíncrono via triagem |

Saúde do sistema = `% fracao_missoes com missao_id preenchido`. Nenhum outro
campo depende de humano após o preview.

---

## 4. Migration 005

`migrations/005_fracoes_nn_bpms.sql`:

```sql
-- 4.1 Novo catálogo smo.bpms (6 BPMs de POA; extensível)
CREATE TABLE IF NOT EXISTS smo.bpms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo VARCHAR(10) NOT NULL UNIQUE,   -- "1 BPM", "20 BPM"
    numero SMALLINT NOT NULL UNIQUE,      -- 1, 20 — para ordenação
    municipio_id UUID NOT NULL REFERENCES smo.municipios(id) ON DELETE RESTRICT,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4.2 Associação N:N
CREATE TABLE IF NOT EXISTS smo.fracao_missoes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fracao_id UUID NOT NULL REFERENCES smo.fracoes(id) ON DELETE CASCADE,
    ordem SMALLINT NOT NULL,                                             -- 1..N
    missao_id UUID REFERENCES smo.missoes(id) ON DELETE RESTRICT,        -- NULL até triagem
    missao_nome_raw VARCHAR(300) NOT NULL,
    municipio_id UUID NOT NULL REFERENCES smo.municipios(id) ON DELETE RESTRICT,
    bpm_id UUID REFERENCES smo.bpms(id) ON DELETE RESTRICT,              -- NULL fora de POA ou em quartel
    em_quartel BOOLEAN NOT NULL DEFAULT FALSE,                           -- missão ocorre no quartel (sem BPM)
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (fracao_id, ordem)
);

CREATE INDEX IF NOT EXISTS idx_fm_fracao    ON smo.fracao_missoes(fracao_id);
CREATE INDEX IF NOT EXISTS idx_fm_missao    ON smo.fracao_missoes(missao_id);
CREATE INDEX IF NOT EXISTS idx_fm_municipio ON smo.fracao_missoes(municipio_id);
CREATE INDEX IF NOT EXISTS idx_fm_bpm       ON smo.fracao_missoes(bpm_id);

-- 4.3 Colunas da fração viram DEPRECATED (drop na 6.5)
COMMENT ON COLUMN smo.fracoes.missao             IS 'DEPRECATED 6.3 → fracao_missoes.missao_nome_raw';
COMMENT ON COLUMN smo.fracoes.missao_id          IS 'DEPRECATED 6.3 → fracao_missoes.missao_id';
COMMENT ON COLUMN smo.fracoes.municipio_id       IS 'DEPRECATED 6.3 → fracao_missoes.municipio_id';
COMMENT ON COLUMN smo.fracoes.municipio_nome_raw IS 'DEPRECATED 6.3 → fracao_missoes.missao_nome_raw';
```

Idempotente (mesmo padrão de 003 e 004: `DO $$ IF NOT EXISTS ... $$`).

### 4.4 Backfill de dados existentes

`scripts/backfill_nn.py`:
- Para cada `smo.fracoes`, inserir 1 vértice em `fracao_missoes` com `ordem=1`,
  copiando `missao`, `missao_id`, `municipio_id`, `municipio_nome_raw`.
- `bpm_id = NULL` (não há como inferir retroativamente).
- Idempotente: só insere se não existir vértice pra essa fração.

### 4.5 Seed `smo.bpms`

`scripts/seed_bpms.py`:
- Parsear primeira linha de `API_Municipios_CRPMs.txt` (CPC / Porto Alegre):
  `9 BPM, 11 BPM, 20 BPM, 1 BPM, 21 BPM, 19 BPM`.
- Inserir com `municipio_id = <POA>` resolvido por nome.

---

## 5. Parser — evolução

### 5.1 Novos regex em `whatsapp_patterns.py`

```python
RE_MISSAO_MUNICIPIO = re.compile(
    r"^\s*Miss[ãa]o\s+(?P<ordem>\d+)\s*:\s*"
    r"(?P<missao>.+?)\s+"
    r"Munic[ií]pio\s*:\s*"
    r"(?P<municipio>.+?)"
    r"(?:\s*\((?P<bpm>\d+°?\s*BPM)\))?\s*$",
    re.IGNORECASE,
)

RE_EQUIPES_EFETIVO = re.compile(
    r"^\s*Equipes?\s*:\s*(?P<n>\d+)\s*\((?P<efetivo>\d+)\s*PMs?\)",
    re.IGNORECASE,
)
```

### 5.2 Dataclasses

```python
@dataclass(frozen=True)
class MissaoParsada:
    ordem: int
    missao_nome_raw: str
    municipio_nome_raw: str
    bpm_raw: str | None
    em_quartel: bool   # heurística: True p/ Prontidão/Pernoite; operador confirma no preview

@dataclass(frozen=True)
class FracaoParsada:
    titulo: str
    cmt: str
    equipes_n: int
    efetivo_n: int
    horario_inicio: str   # "HH:MM"
    horario_fim: str
    missoes: tuple[MissaoParsada, ...]
```

### 5.3 Grammar antigas continuam parseáveis

Formato canônico §2.1 é **preferido**; formatos legados (7 grammars
identificadas em `smo_12_04.txt`) ainda passam pelo parser atual. O preview
sinaliza **amarelo** quando o bloco não está no padrão canônico — cria pressão
pela normatização sem bloquear.

### 5.4 Heurística `em_quartel`

Parser infere `em_quartel = True` quando `normalizar(missao_nome_raw)` casa com:

```python
RE_EM_QUARTEL = re.compile(
    r"^\s*(prontid[ãa]o|pernoite|aquartelado|em\s+quartel)",
    re.IGNORECASE,
)
```

Caso contrário `em_quartel = False`. Operador confirma/override no preview —
decisão final sempre humana. Quando `em_quartel = True`, `bpm_raw` extraído é
descartado (mesmo que exista no texto).

---

## 6. Preview — UX

**Princípio**: operador AREI pode **editar todos os campos** extraídos pelo
parser. O parser é melhor esforço; siglas novas, trechos mal formatados, linhas
truncadas ou juntadas acontecem. Bloquear edição força o operador a voltar pro
texto cru e re-colar — pior UX e pior dado.

Tela `/preview-importacao` passa a renderizar, por fração:

- Header editável: título, cmt, equipes/efetivo, horário.
- Lista de N missões — **todos os campos editáveis**:
  - `missao_nome_raw` — input de texto (operador corrige typos/erros de parse; triagem só cataloga `missao_id` depois).
  - **`em_quartel`** — toggle (switch). Default inferido pelo parser (§5.4). Quando ON, `bpm_id` desabilita e vai para NULL; `municipio_id` continua obrigatório (quartel fica em algum município).
  - **`municipio_id`** — dropdown **obrigatório**; default = melhor match fuzzy do `municipio_nome_raw`.
  - **`bpm_id`** — dropdown **obrigatório** se município = POA **e** `em_quartel = false`; disabled caso contrário.
- Operador pode **adicionar/remover blocos de missão** (caso parser tenha juntado 2 em 1 ou quebrado uma em 2). Ordem é renumerada automaticamente `1..N` ao salvar.
- Avisos amarelos (não bloqueiam, só informam):
  - município não casou no catálogo → operador escolhe manualmente.
  - BPM não detectado em bloco de POA com `em_quartel = false` → operador escolhe manualmente.
  - bloco fora do padrão canônico §2.1 → nota de normatização.
- Botão **Salvar** só ativa quando todas as missões têm `municipio_id` resolvido (+ `bpm_id` quando POA e não em quartel). Nenhuma outra validação bloqueia.

### 6.1 Backend do preview

`app/services/whatsapp_catalogo.py`:
- `enriquecer_com_catalogo` roda match fuzzy em município (`token_set_ratio ≥ 85`).
- Resolve `bpm_id` via tabela `smo.bpms` quando `bpm_raw` preenchido e município = POA.
- Insere aviso se `municipio_id` não resolveu, ou se POA sem `bpm_id`.

---

## 7. Triagem de missões (absorve 6.2.5)

Contratos de `PROMPT_FASE6_2_5.md` §3 aplicam **com 3 diferenças**:

| 6.2.5 original | 6.3 |
|---|---|
| agrupa por `smo.fracoes.missao` | agrupa por `smo.fracao_missoes.missao_nome_raw` |
| UPDATE em `smo.fracoes.missao_id` | UPDATE em `smo.fracao_missoes.missao_id` |
| também valida município | **não** — município saiu pra §6 |

Resto (UI `/admin/catalogos/triagem-missoes`, `token_set_ratio ≥ 50`, commit
imediato + modal "Nova missão", 3 rotas POST) idêntico. LOC estimada idêntica.

---

## 8. Dashboard — 3 camadas

Cada card/tabela do dashboard rotulado explicitamente:

| Camada | Fonte | Rótulo | Exemplos de card |
|---|---|---|---|
| **Determinístico** | parse + operador | `realtime` | nº frações/dia, efetivo empenhado, **nº missões-equivalente**, missão × município, densidade por BPM em POA, **% efetivo em quartel vs. rua** por unidade/dia |
| **Normalizado** | `missao_nome_raw` agrupado por NFD+upper+trim | `realtime (aproximado)` | ranking de missões por texto bruto, detecção de candidatas a catálogo |
| **Catalogado** | `missao_id` (triagem humana) | `saúde triagem: X%` | heatmap horário × missão, matriz de co-ocorrência, taxa de adoção do catálogo |

**Regras duras**:
- Cards de camadas diferentes **nunca somam** visualmente.
- Indicador de saúde exposto no topo: `% fracao_missoes com missao_id preenchido`,
  por unidade e por semana.
- Quando saúde < 80% numa unidade, cards catalogados dela recebem tarja
  "confiabilidade baixa — triagem pendente".

### 8.1 Ganho principal do N:N (independe de catálogo)

**Missões-equivalente** = `COUNT(fracao_missoes)` por fração. Mesmo com
`missao_id` todo NULL, essa métrica já entrega o que o modelo 1:1 invisibilizava:
a carga operacional real do comando. Disponível em tempo real.

---

## 9. Decisões finais (itens antes em aberto)

| Questão | Decisão |
|---|---|
| Pelotão/Esquadrão como entidade | **não** — título fica texto livre na fração |
| BPM obrigatório em POA sempre? | **não** — só se `em_quartel = false`. Missão em quartel (Prontidão etc.) não tem BPM, mesmo em POA. Flag no vértice, heurística no parser, override no preview |
| Horário composto (QTL/PREL/LOCAL/REC/LIB) | **fora de escopo** — só `horario_inicio`/`fim`. JSONB opcional fica pra Fase 7+ |
| OSv-como-métrica | **não** — OSv é campo esparso, ferramenta de consulta pontual, não entra em agregação |
| 6° Choque (N frações vs N missões) | **N missões em 1 fração** (modelo único) |
| Missão implícita via título (GDA/CUSTÓDIA) | **operador explicita** no preview como missão própria |
| Multi-município por missão (ex: "Pedro Osório, Cerrito") | **1:1** por enquanto. Se surgir frequente → `municipios_extras UUID[]` em Fase futura |

---

## 10. Arquivos

| Arquivo | LOC est. | Ação |
|---|---|---|
| `migrations/005_fracoes_nn_bpms.sql` | ~80 | novo |
| `scripts/backfill_nn.py` | ~120 | novo |
| `scripts/seed_bpms.py` | ~60 | novo |
| `app/services/whatsapp_patterns.py` | +30 | estender |
| `app/services/whatsapp_fracoes.py` | +80 | estender (emitir `MissaoParsada[]`) |
| `app/services/whatsapp_catalogo.py` | +60 | estender (resolve `bpm_id`; avisos) |
| `app/services/db_service.py` | +80 | gravar N vértices por fração |
| `app/services/triagem_missoes.py` | ~180 | novo (herdado 6.2.5) |
| `app/services/analytics_catalogos.py` | +120 | agregações N:N + 3 camadas |
| `app/routes/admin_catalogos.py` | +80 | 3 rotas triagem |
| `app/routes/api.py` | +40 | preview aceita N missões |
| `app/templates/preview-importacao.html` | ~200 | reescrever (N missões + dropdowns município/BPM) |
| `app/templates/admin/triagem_missoes.html` | ~130 | novo |
| `app/templates/analista/index.html` | +80 | 3 camadas rotuladas |
| `app/static/js/preview_importacao.js` | ~120 | dropdowns município/BPM |
| `app/static/js/triagem_missoes.js` | ~60 | novo |
| `tests/test_fracoes_nn.py` | ~140 | novo |
| `tests/test_triagem_missoes.py` | ~140 | novo |
| `tests/test_whatsapp_catalogo.py` | +60 | bpm + avisos |
| `tests/test_analytics_catalogos.py` | +80 | 3 camadas + missões-equivalente |

Total: ~1.800 LOC novos + ~600 modificados. Nenhum arquivo > 500 LOC.

---

## 11. Princípios (reforço)

1. **Tipagem forte** — zero `Any`; `dataclass(frozen=True)` nos retornos; `TypedDict` para payloads; `Literal` onde aplicável.
2. **500 LOC max por arquivo.**
3. **Segurança** — prepared statements sempre; CSRF em POSTs; `@role_required`; validação de tamanho em inputs.
4. **Frontend burro** — dropdowns com dados pré-carregados; JS só abre/fecha modal e chama fetch+reload; zero lógica de negócio.
5. **Domínio** — CANIL / PATRES / PRONTIDÃO / (provavelmente) PMOB são **frações**, não missões. Não sugerir no catálogo.
6. **Auditoria** — gerar `AUDITORIA_6_3.md` no formato de `AUDITORIA_6_2.md`.

---

## 12. Critérios de aceitação

- [ ] Migration 005 aplicada idempotentemente.
- [ ] Backfill copia 100% das frações existentes para `fracao_missoes` sem perda.
- [ ] Seed `smo.bpms` cria 6 registros (BPMs de POA).
- [ ] Parser reconhece grammar canônica §2.1; formatos legados ainda parseáveis com aviso.
- [ ] Preview bloqueia Salvar enquanto houver município/BPM não resolvidos.
- [ ] Triagem resolve os 2.948 `missao_nome_raw` históricos a <100.
- [ ] Dashboard exibe as 3 camadas com rótulos explícitos e indicador de saúde.
- [ ] Cards "missões-equivalente" e "densidade por BPM (POA)" funcionando em tempo real.
- [ ] 149 testes existentes + ~30 novos passando.

---

## 13. Fora de escopo (move pra 6.4+)

- Deploy Oracle Cloud Free + hardening remoto (Fase 6.4 — **sem** form ALEI; AREI central é definitivo).
- Checkpoints compostos QTL/PREL/LOCAL/REC/LIB (Fase 7+, JSONB opcional).
- Pelotão/esquadrão como entidade separada (Fase 7+ se virar necessidade).
- Multi-município por missão (Fase futura, só se a frequência justificar).
- Dashboards de auditoria OSv (ferramenta pontual via query direta, não card fixo).
- Drop das colunas legadas em `smo.fracoes` (Fase 6.5 — após 2-3 ciclos de confiança).

---

## 14. Como começar no próximo chat

1. Ler este arquivo inteiro.
2. Ler `AUDITORIA_6_2.md` (estado atual pós-catálogos).
3. Ler `PROMPT_FASE6_2_5.md` §3 (contratos de triagem — idênticos, apenas fonte diferente).
4. Ler `app/services/whatsapp_fracoes.py` (como parser emite frações hoje).
5. Ler `smo_12_04.txt` (realidade do texto WhatsApp, 7 grammars).
6. Aplicar migration 005 + seed bpms + backfill nn.
7. Evoluir parser (patterns → fracoes) + testes.
8. Reescrever preview com dropdowns município/BPM.
9. Implementar triagem (idêntica à 6.2.5, só troca a fonte).
10. Dashboard 3 camadas + missões-equivalente.
11. `AUDITORIA_6_3.md`.
