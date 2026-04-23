# DECISÃO — Fluxo de recepção AREI (multi-ALEI)

Data: 2026-04-21
Escopo: Fase 6.3 (form web ALEI + deploy Oracle)
Decisor: Mauricio B (owner)

> **Nota**: este documento resolve um gap arquitetural que ficou em aberto
> quando decidimos o fluxo de **entrada** do ALEI
> ([`memory/decisao_fase6_3_alei_normalizacao.md`](../.claude/projects/c--Users-watso-gerador-cars-emprego/memory/decisao_fase6_3_alei_normalizacao.md)).
> Aquela decisão cobria como o ALEI **salva**. Esta cobre como o AREI
> **recebe e consolida** o que os 6 ALEIs salvam.

---

## 1. Problema

Hoje o SMO opera com **1 operador central (AREI)** que cola o texto do
WhatsApp e salva direto em `smo.fracoes` / `smo.cabecalho`. Não há
conceito de "quem mandou" — `smo.fracoes` nem tem coluna `criado_por`.

A Fase 6.3 introduz **6 operadores locais (ALEI)**, um por unidade BPChq.
Cada ALEI passa a poder salvar dados da própria unidade via UI (mesmo
parser, `unidade_match_required`). Isso abre 3 perguntas que não estavam
respondidas:

1. **Rastreabilidade**: quem salvou? Sem coluna `criado_por`, auditoria é cega.
2. **Recepção pelo AREI**: como AREI sabe quem já mandou a escala do dia
   e quem falta, sem depender de WhatsApp paralelo?
3. **Unicidade**: o que acontece se ALEI 1º BPChq salva 2x a mesma data?
   Sobrescreve? Duplica?

---

## 2. Modelo escolhido: **C — Publicação direta + tela de consolidação**

- ALEI salva direto em `smo.fracoes` / `smo.cabecalho`. Sem staging, sem
  aprovação. Publicação é imediata — cards e painel analista já veem.
- AREI ganha nova tela `/arei/consolidacao?data=DD-MM-AAAA`. Uma linha por
  unidade BPChq, com status visual:
  - ✓ **recebida** `às HH:MM por Fulano` (link "editar" reusando preview do parser)
  - ⏳ **pendente** (nenhum registro ainda para essa unidade+data)
  - ⚠ **com avisos** (parser levantou alertas — quantos, quais)
- Edição inline: AREI clica "editar" e cai no preview do parser já preenchido
  (rota `GET /arei/consolidacao/editar?unidade=X&data=Y` carrega fracoes
  existentes). Salvar atualiza em vez de inserir.

### Modelos rejeitados

**A — Publicação direta sem inbox.** Mais simples, mas perde visibilidade
operacional. AREI teria que ir no painel analista e filtrar pra saber
quem mandou. Descartado: resolve rastreio, não resolve "quem falta?".

**B — Staging + aprovação.** ALEI salva em `smo.fracoes_pending`, AREI
aprova em lote. Controle máximo, mas:
- Trava cards/painel até aprovação (fluxo militar é tempo real).
- Dobra o CRUD (pending + publicado = 2x as queries, 2x os testes).
- AREI vira gargalo operacional — se não aprovar, unidade some.

Descartado: custo alto pra um problema que C resolve com visibilidade.

---

## 3. Pré-requisitos — Migration 005 (antes da 6.3)

```sql
-- migrations/005_rastreabilidade.sql

ALTER TABLE smo.fracoes
    ADD COLUMN IF NOT EXISTS criado_por UUID
        REFERENCES smo.usuarios(id) ON DELETE SET NULL;

ALTER TABLE smo.cabecalho
    ADD COLUMN IF NOT EXISTS criado_por UUID
        REFERENCES smo.usuarios(id) ON DELETE SET NULL;

ALTER TABLE smo.cabecalho
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_cabecalho_unidade_data
    ON smo.cabecalho(unidade, data);

CREATE INDEX IF NOT EXISTS idx_fracoes_unidade_data
    ON smo.fracoes(unidade, data);
```

`ON DELETE SET NULL`: usuário deletado preserva os dados (audit trail).

**Backfill**: deixar `criado_por` NULL em registros legados. Opcional:
inferir pelo padrão "AREI salvou tudo até X data" e preencher, mas
arriscado se houver exceções — melhor deixar NULL + coluna `observacao`
se quiser comentar.

---

## 4. Regras de escrita (multi-ALEI)

### Unicidade (unidade, data)
- ALEI salvando (unidade_própria, data) **substitui** seus dados anteriores
  para aquela combinação. SQL:
  ```sql
  DELETE FROM smo.cabecalho WHERE unidade = :u AND data = :d;
  DELETE FROM smo.fracoes   WHERE unidade = :u AND data = :d;
  INSERT INTO smo.cabecalho (..., criado_por) VALUES (..., :uid);
  INSERT INTO smo.fracoes   (..., criado_por) VALUES (..., :uid);
  ```
  (Mesma lógica que [operador.py](app/routes/operador.py) usa hoje.)
- `unidade_match_required` já garante que ALEI só grava pra própria
  unidade — ver [app/auth/decorators.py:40](app/auth/decorators.py#L40).

### Edição por AREI
- AREI pode editar qualquer unidade+data. Mesmo SQL acima, mas
  `criado_por` **não** é sobrescrito — preserva autoria original, AREI
  vira "editor" (coluna futura `editado_por` se quisermos rastrear).
- Decisão nesta rodada: **não criamos `editado_por` agora**. Se
  precisar, entra como migration 006.

### Gestor
- Acesso total, mesmo tratamento de AREI.

---

## 5. Contrato da tela `/arei/consolidacao`

### Rota
```
GET /arei/consolidacao?data=DD-MM-AAAA
  role: gestor OU operador_arei (não ALEI)
  query: data (default: hoje)
```

### Service
```python
# app/services/consolidacao_service.py

@dataclass(frozen=True)
class StatusUnidade:
    unidade: str                # "1 BPChq", "2 BPChq", ...
    status: Literal["recebida", "pendente", "com_avisos"]
    recebida_em: datetime | None    # cabecalho.created_at
    criado_por_nome: str | None     # JOIN usuarios
    avisos: int                      # contagem de avisos do parser
    total_fracoes: int
    link_editar: str

def status_do_dia(data: str) -> list[StatusUnidade]:
    """Retorna 6 linhas (uma por unidade BPChq), sempre na mesma ordem.
    Unidades sem cabecalho para a data aparecem como 'pendente'."""
```

### Template
- Header/nav compartilhados (após design polish).
- Tabela 6 linhas (UNIDADES_VALIDAS do [app/models/user.py:17](app/models/user.py#L17)).
- Seletor de data (date input, default = hoje).
- Badge colorido por status (verde/cinza/âmbar).
- Link "editar" ou "ver" dependendo do status.
- Refresh manual (sem WebSocket — fluxo militar admite F5).

### Segurança
- `@role_required(["gestor", "operador_arei"])`.
- `data` validado como formato DD-MM-AAAA (regex) antes de ir pro SQL.
- SQL com prepared statement, sempre.

---

## 6. Edição inline (preview do parser em modo update)

AREI clica "editar" → `GET /arei/consolidacao/editar?unidade=X&data=Y`.
Reusa o preview do parser (mesmo componente visual), mas:
- Campos pré-preenchidos vindo do banco.
- `POST /api/salvar-texto` aceita um modo `{"update": true}` que aplica
  o DELETE+INSERT em vez de INSERT puro.
- Após salvar, redirect para `/arei/consolidacao?data=Y`.

**Importante**: o parser já foi desenhado pra ser idempotente
(DELETE+INSERT por unidade+data é o padrão atual). A mudança é
principalmente a rota de entrada e pré-preenchimento.

---

## 7. Impacto em rotas existentes

| Rota/serviço | Mudança |
|---|---|
| `POST /api/salvar-texto` | Preencher `criado_por = current_user.id` no INSERT. Manter `unidade_match_required` para ALEI. |
| `POST /api/upload` (xlsx) | Idem — preencher `criado_por`. |
| Painel analista | Nenhuma mudança obrigatória. Opcional: filtro por "criado_por" se gestor quiser ver produtividade. |
| Cards do operador | Nenhuma. Continua lendo `smo.fracoes` como hoje. |

---

## 8. Testes (mínimo por ponto)

1. **Migration 005**: aplica idempotente (rodar 2x não quebra).
2. **`criado_por` no salvar**: ALEI salva → `criado_por = id_alei`.
3. **Unicidade**: ALEI salva 2x (mesma unidade, mesma data) → só 1 cabecalho persiste.
4. **Isolamento por unidade**: ALEI 1º BPChq tenta salvar pra "2 BPChq" → 403 (`unidade_match_required` já cobre; regredir).
5. **`status_do_dia`**: 3 unidades com cabecalho + 3 sem → retorna 6 linhas (3 "recebida", 3 "pendente").
6. **Role gate consolidação**: ALEI GET `/arei/consolidacao` → 403.
7. **Edição inline**: AREI edita unidade X → preserva `criado_por` original.

---

## 9. O que NÃO está decidido ainda (defer pro momento da 6.3)

- **"Fechar o dia"**: existe botão "fechar escala do dia" que impede
  edições futuras? Adiar — operação atual é permissiva. Se virar
  necessidade, entra como flag `fechada_em` no cabecalho.
- **Notificação**: AREI é notificado quando uma unidade manda? Começar
  sem notificação, refresh manual. Se a dor aparecer, adicionar
  polling leve (5min) ou WebSocket.
- **`editado_por` / audit log**: adiar. Se auditoria militar exigir,
  migration 006 adiciona coluna + trigger.
- **Download da consolidação**: gerar PDF/xlsx da tela? Não pra 6.3.

---

## 10. Relação com outras decisões

- **Entrada ALEI** (parser compartilhado, triagem retroativa): ver
  [`memory/decisao_fase6_3_alei_normalizacao.md`](.claude/projects/c--Users-watso-gerador-cars-emprego/memory/decisao_fase6_3_alei_normalizacao.md). Complementa esta decisão.
- **Design polish** (atual): zero impacto. Polish é visual/navegação.
  Quando a consolidação for construída, usa o header/nav já prontos.
- **Fase 6.2.5** (triagem): independente. Triagem opera em
  `missao_id IS NULL`, indiferente a quem criou a fração.
- **Roadmap**: esta decisão entra no escopo da 6.3 junto com "form ALEI"
  e "deploy Oracle". Pode ser a entrega visível mais importante da fase
  pro chefe (antes era só "agora tem ALEI"; agora é "AREI vê o dia em
  uma tela").
