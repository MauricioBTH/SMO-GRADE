# PROMPT — Fase 6.2.5: Triagem de Missões Pendentes

> **SUPERSEDED em 2026-04-22** — escopo absorvido por `PROMPT_FASE6_3.md` §7.
> Mantido como referência histórica. Não executar como plano autônomo; usar 6.3.

Data: 2026-04-20
Continuação de: Fase 6.2 (catálogos + backfill fuzzy — ver `AUDITORIA_6_2.md`)

> **Nota de escopo**: esta é uma fase-hotfix/complemento da 6.2, NÃO a 6.3
> do roadmap original. A 6.3 (form ALEI + deploy Oracle Cloud) continua
> reservada conforme `ARQUITETURA.md` §roadmap. Esta 6.2.5 existe apenas
> para resolver o débito de catalogação dos 2948 registros legados que o
> backfill fuzzy não conseguiu casar, usando triagem humana via UI.

---

## 1. Contexto / estado atual

Após a Fase 6.2 o sistema tem:

- Catálogos normativos (`smo.crpms`, `smo.municipios`, `smo.missoes`).
- 9 missões ativas no banco (tamanho atual do `MISSOES_PADRAO`).
- 497 municípios vinculados aos 21 CRPMs.
- Coluna `smo.fracoes.missao_id` (FK opcional, `ON DELETE RESTRICT`).
- Parser enriquece `missao_id` para mensagens NOVAS via match exato (`normalizar()`).
- Script `scripts/backfill_missoes.py` usa rapidfuzz `token_sort_ratio >= 85`.
- 149 testes passando.

### Problema

Rodando `python -m scripts.backfill_missoes --dry-run` para as 3000 frações
históricas com `missao_id IS NULL`:

```
MISSOES:
  total lidos : 3000
  exatos      :   52
  fuzzy>=85   :    0
  ambiguos    :    0
  sem match   : 2948
```

O fuzzy falhou porque os textos históricos são descritivos e longos
(ex.: `"Prontidão, Reserva de OCD, Instrução Centralizada e Combate aos CVLIs – Área do 21º BPM"`)
enquanto o catálogo tem nomes canônicos curtos (`"PRONTIDAO"`). `token_sort_ratio`
compara conjuntos completos de tokens → colapsa para score ~25.

### Decisão do usuário

Construir uma **UI de triagem** (`/admin/catalogos/triagem-missoes`) onde:

1. Backend agrupa textos pendentes por frequência (dedupe: 3000 frações ≈
   50-200 textos únicos).
2. Para cada texto, backend sugere top-3 candidatos fuzzy (usando
   `token_set_ratio`, não `token_sort_ratio` — melhor para long-vs-short).
3. Gestor clica "aplicar" em um candidato OU "cadastrar nova" (modal).
4. Cada ação faz **1 UPDATE** que resolve todas as frações com aquele texto.

Fluxo escolhido: **commit imediato + modal**.

---

## 2. Arquivos a criar/modificar

| Arquivo | LOC est. | Status |
|---|---|---|
| `app/services/triagem_missoes.py` | ~180 | novo |
| `app/routes/admin_catalogos.py` | +~80 | estender |
| `app/templates/admin/triagem_missoes.html` | ~130 | novo |
| `app/static/js/triagem_missoes.js` | ~60 | novo |
| `tests/test_triagem_missoes.py` | ~140 | novo |
| `app/services/whatsapp_catalogo.py` | +~20 | estender — validação município |
| `tests/test_whatsapp_catalogo.py` | +~40 | estender (se existe) ou novo — validação |

Total ~650 LOC; nenhum arquivo > 200 LOC.

---

## 3. Contratos

### `app/services/triagem_missoes.py`

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class TextoPendente:
    texto: str
    freq: int        # quantas frações têm esse texto

@dataclass(frozen=True)
class Candidato:
    missao_id: str
    nome: str
    score: int       # 0..100

@dataclass(frozen=True)
class AplicacaoResult:
    missao_id: str
    missao_nome: str
    fracoes_atualizadas: int

@dataclass(frozen=True)
class CriacaoResult:
    missao_id: str
    missao_nome: str
    fracoes_atualizadas: int   # UPDATE feito no mesmo commit
```

#### Funções

```python
def agrupar_pendentes(limit: int = 20, offset: int = 0) -> list[TextoPendente]:
    """
    SELECT missao AS texto, COUNT(*) AS freq
      FROM smo.fracoes
     WHERE missao_id IS NULL AND missao <> ''
     GROUP BY missao ORDER BY freq DESC, texto ASC
     LIMIT :limit OFFSET :offset;
    """

def contar_pendentes() -> int:
    """Total de textos DISTINTOS pendentes — para paginação."""

def sugerir_candidatos(
    texto: str, catalogo: dict[str, str], n: int = 3, score_min: int = 50,
) -> list[Candidato]:
    """rapidfuzz token_set_ratio (NÃO token_sort_ratio).
    Retorna top-N acima de score_min, desc por score.
    Catálogo vazio → []."""

def aplicar_mapeamento(texto: str, missao_id: str) -> AplicacaoResult:
    """UPDATE smo.fracoes SET missao_id=:id, atualizado_em=NOW()
        WHERE missao=:texto AND missao_id IS NULL
       RETURNING id;
    Valida que missao_id existe em smo.missoes antes (FK já protege, mas
    erro amigável)."""

def criar_e_aplicar(
    nome: str, descricao: str | None, texto: str,
) -> CriacaoResult:
    """Transação atômica:
        INSERT INTO smo.missoes(nome, descricao) RETURNING id;
        UPDATE smo.fracoes SET missao_id=:id WHERE missao=:texto AND missao_id IS NULL;
    Normaliza `nome` via catalogo_types.normalizar antes do insert."""
```

### `app/routes/admin_catalogos.py` (estender)

| Método | Rota | Role | Body / query |
|---|---|---|---|
| GET | `/admin/catalogos/triagem-missoes` | gestor | `?pagina=1` |
| POST | `/admin/catalogos/triagem-missoes/aplicar` | gestor | `{texto, missao_id}` |
| POST | `/admin/catalogos/triagem-missoes/nova` | gestor | `{texto, nome, descricao}` |

Todas com CSRF token. `texto` limitado a 500 chars. `nome` a 120 chars.

### Template `admin/triagem_missoes.html`

- Reusa shell visual de `admin/missoes.html` (nav entre catálogos).
- Tabela:
  - Coluna "Texto" (truncada a 80 chars com tooltip full).
  - Coluna "Frações" (freq).
  - Coluna "Candidatos": 3 botões `[Aplicar NOME (score)]` + `[+ Nova]`.
- Paginação simples (← anterior / próxima →).
- Modal `<dialog>` nativo HTML para "Nova missão".

### JS `triagem_missoes.js`

```js
// Apenas: abrir modal, fechar modal, submit via fetch, location.reload().
// Zero lógica de negócio.
function abrirModal(texto) { ... }
function fecharModal() { ... }
async function aplicar(texto, missaoId) { ... fetch ... reload }
async function criar(texto, form) { ... fetch ... reload }
```

---

## 4. Segurança

- `@role_required(["gestor"])` em **todas** as 3 rotas.
- Queries com `cur.execute(sql, params)` — zero interpolação.
- CSRF token nos 2 POSTs (mesmo padrão de `/admin/catalogos/missoes`).
- Input sanitizado:
  - `texto` max 500 chars
  - `nome` max 120 chars, normalizado via `catalogo_types.normalizar`
  - `descricao` max 300 chars, opcional
- `criar_e_aplicar` em transação atômica (`with conn:` + rollback em erro).

---

## 5. Testes (8 mínimos)

1. `agrupar_pendentes` ordena por freq desc, tiebreak por texto asc.
2. `agrupar_pendentes` respeita `limit` e `offset`.
3. `sugerir_candidatos` retorna top-N acima do score_min, desc.
4. `sugerir_candidatos` com catálogo vazio → `[]`.
5. `sugerir_candidatos` usa `token_set_ratio` (texto longo bate em
   nome canônico curto — teste: `"PRONTIDAO RESERVA DE OCD INSTRUCAO"` casa
   com `"PRONTIDAO"` acima de 50).
6. `aplicar_mapeamento` só afeta `missao_id IS NULL` (não sobrescreve
   vínculos existentes).
7. `criar_e_aplicar` rollback quando UPDATE falha (nenhuma missão criada).
8. GET `/admin/catalogos/triagem-missoes` sem role gestor → 403/redirect.

Testes de DB podem usar `monkeypatch` em `get_connection` ou fixture com
SQLite-compat (mesmo padrão dos tests existentes).

---

## 6. Princípios a respeitar (reforço)

1. **Tipagem forte**: zero `Any`; `dataclass(frozen=True)` para retornos;
   `TypedDict` para payloads de rota; `Literal` onde aplicável.
2. **500 LOC max por arquivo**: com a estimativa atual, o maior é o service
   (~180 LOC).
3. **Segurança**: prepared statements sempre, CSRF, role, limites de
   tamanho de input, validação antes do banco.
4. **Frontend burro**: JS só abre/fecha modal e chama fetch+reload. Toda
   lógica (agrupar, ranquear, aplicar) é backend.
5. **Auditoria**: ao concluir, escrever `AUDITORIA_6_2_5.md` com tabela LOC
   + decisões + cobertura de testes, seguindo o formato de `AUDITORIA_6_2.md`.
6. **Domínio**: lembrar — **CANIL, PATRES, PRONTIDAO, PMOB** são **frações**,
   não missões. Não sugerir esses como missão ao usuário.

---

## 7. Pontos sutis que já foram debatidos

- **Por que `token_set_ratio` e não `token_sort_ratio`**: o ratio antigo
  penalizava textos longos comparados a nomes curtos. `token_set_ratio`
  tolera subconjunto (aceita o nome curto "dentro" do texto longo).
- **Por que score_min 50 (não 85)**: aqui o humano valida. A UI mostra top-3
  mesmo com score modesto; o gestor decide. O fuzzy só ordena a lista,
  não decide sozinho.
- **Idempotência**: `WHERE missao_id IS NULL` garante que clicar "aplicar"
  duas vezes no mesmo texto não sobrescreve (nem corrompe) vínculos.
- **Dedupe é o 80/20**: os top 10 textos devem cobrir 60-80% das 3000
  frações. A UI deve deixar óbvio quanto cada texto "vale".
- **Modal vs redirect (já decidido: modal)**: evita perder contexto da
  fila de triagem; transação atômica em 1 request.
- **Ordem de trabalho do gestor**: ordem natural já é por frequência, então
  ele naturalmente resolve os casos de maior impacto primeiro.

---

## 7.1 Escopo extra — validação de município no parser

Regra do domínio (decidida em 2026-04-22):

> **Município é lista fechada obrigatória.** OSv é string livre. Missão entra
> crua e o analista cataloga a posteriori via triagem.

Implicação direta no parser: hoje `enriquecer_com_catalogo` tenta match do
município e deixa `municipio_id = NULL` silenciosamente se não achar. Pela
nova regra, **o parser deve sinalizar** no `avisos` quando:

- a fração tem `municipio_nome_raw` não-vazio, e
- `normalizar(municipio_nome_raw)` não casa com nenhum nome de `smo.municipios`.

Motivo: o operador AREI precisa ver o aviso antes de confirmar a importação
e corrigir o texto. Sem isso, o município errado entra silenciosamente como
SEM CATALOGO e distorce o dashboard.

### Mudanças em `app/services/whatsapp_catalogo.py`

```python
def enriquecer_com_catalogo(fracoes, avisos):
    # ... lookup existente ...
    for f in fracoes:
        raw = f.get("municipio_nome_raw", "").strip()
        if raw and not f.get("municipio_id"):
            avisos.append({
                "tipo": "municipio_nao_catalogado",
                "fracao_titulo": f.get("titulo", ""),
                "municipio_raw": raw,
                "mensagem": f"Municipio '{raw}' nao encontrado no catalogo.",
            })
```

### O que NÃO muda no escopo 6.2.5

- **Não rejeita** a fração — só adiciona aviso. O parse continua completo,
  a fração entra com `municipio_id = NULL`.
- **Não muda o formato de entrada** do texto WhatsApp. Se no futuro
  (Fase 6.3 + form ALEI) o usuário usa dropdown, aí sim a rejeição é
  no front.
- **Não toca em missão** — missão segue fluxo "entra cru, triagem depois"
  (que é o core da 6.2.5).
- **Não toca no card** — escopo travado pelo usuário.

### Testes adicionais (~2)

1. `enriquecer_com_catalogo` adiciona aviso quando município não está no
   catálogo (texto raw preenchido, id fica NULL).
2. Não adiciona aviso quando o município casa (fluxo feliz).

---

## 8. Próximos passos após a 6.2.5

- **Triagem de municípios**: mesma UI, para `municipio_nome_raw`. Fora do
  escopo da 6.2.5 porque a coluna ainda está vazia (migration 004 é nova).
  Vai encher naturalmente com parse de mensagens novas.
- **Expansão do `MISSOES_PADRAO`**: usuário analisará em lotes pequenos
  (3-5 por vez) com Claude. A triagem também serve como mecanismo de
  descoberta — o próprio ato de triar revela missões que faltam cadastrar.
- **Fase 6.3 (roadmap original)**: form web ALEI + deploy Oracle Cloud
  Free + hardening. Ver `ARQUITETURA.md` §roadmap e `PROMPT_FASE6_2.md` §157.
- **Fase 7 (sugerida em AUDITORIA_6_2)**: editor in-place no preview de
  parse para operador resolver ambiguidades na hora da importação.

---

## 9. Como começar no próximo chat

1. Ler este arquivo inteiro.
2. Ler `AUDITORIA_6_2.md` (contexto do que já está pronto).
3. Ler `app/services/catalogo_service.py` (padrão de service existente).
4. Ler `app/routes/admin_catalogos.py` (padrão de rota existente).
5. Ler `app/templates/admin/missoes.html` (shell visual a reusar).
6. Implementar os 5 arquivos acima na ordem: service → rotas → template → js → testes.
7. Rodar `pytest -q`; garantir 149 testes anteriores + ~8 novos passando.
8. Escrever `AUDITORIA_6_2_5.md`.
