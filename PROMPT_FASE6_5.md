# PROMPT — Fase 6.5: Soft-delete + histórico de uploads + UI preventiva de data

Data: 2026-04-23
Predecessora: Fase 6.4.1 (catálogo de unidades + sede) — commit `fd31151`
Motivação: operador AREI pode errar a data no texto do escalante e sobrescrever dados válidos. Hoje o `save_fracoes` faz `DELETE/INSERT` por `(unidade, data)` — destrutivo e sem auditoria.

---

## 1. Objetivo

Transformar gravação destrutiva em **versionada**:

- Nenhum dado é apagado: toda "sobrescrita" vira soft-delete + novo upload.
- Cada gravação é um **upload rastreável** (quem, quando, origem, texto original).
- UI de histórico permite **restaurar versão anterior** sem reimportar.
- UI preventiva reduz a chance do erro acontecer em primeiro lugar (banner "hoje", card de data detectada, modal de confirmação final).

### 1.1 Divisão em sub-entregas

Fase 6.5 é composta por duas sub-entregas sequenciais:

1. **6.5.a — UI preventiva** (prevenir erro humano; ~230 LOC, ~2h30)
2. **6.5.b — Soft-delete + histórico** (rede de segurança quando prevenção falha; ~1240 LOC, 2-3 dias)

Ordem recomendada: 6.5.a primeiro (reduz frequência de necessidade de restauração), depois 6.5.b. Mas o esquema de banco da 6.5.b é o mais crítico — **se houver aperto de tempo, priorizar 6.5.b**.

### 1.2 Princípios inegociáveis

Esta fase — como todas as anteriores (6.2, 6.3, 6.4, 6.4.1) — obedece aos **6 princípios** do projeto SMO-GRADE. Não são diretrizes opcionais; são condição para a fase ser aceita. Se um princípio conflitar com "entregar rápido", **o princípio ganha** e o escopo reduz.

1. **Tipagem forte — zero tolerância.**
   - Nenhum `Any`, `cast`, `# type: ignore` novo sem justificativa no comentário.
   - Dataclasses `frozen=True` para objetos de domínio (`Upload`, tal como `Unidade`/`Municipio`/`Missao`).
   - Retornos explícitos em toda função pública (`-> Upload`, `-> list[Upload]`, `-> None`).
   - `TypedDict` para payloads de request/response onde cabível.

2. **Modularidade — teto de 500 LOC por arquivo.**
   - `upload_service.py` deve nascer isolado (~220 LOC).
   - `db_service.py` cresce pra ~620 LOC se tudo entrar num arquivo só — **dividir** em `db_service_save.py` / `db_service_fetch.py` assim que passar de 500.
   - Se um módulo novo nasce acima de 300 LOC, pensar duas vezes — provavelmente é duas responsabilidades.

3. **Segurança — defesa por camadas.**
   - 100% das queries parametrizadas (psycopg2 `%s`, nunca `f"..."` em SQL).
   - Decorator de auth/role em TODOS os endpoints novos (`@operador_arei_required` em `/restaurar`, `@admin_required` em `/texto`).
   - CSRF em todos os POST (middleware já existente — garantir que endpoints novos herdam).
   - `texto_original` pode ter PII — acesso restrito e log de acesso no `AUDITORIA_6_5.md` como dívida se não implementado.
   - Nunca propagar input do cliente direto em `ORDER BY` / `LIMIT` / nome de coluna.

4. **Frontend burro — toda lógica no backend.**
   - JS faz: fetch, render, submit. Nunca: decidir se pode restaurar, validar permissão, compor SQL, recomputar invariantes.
   - Card de "data detectada" é puro render — a **detecção** da data vem do parser Python no JSON de preview.
   - Modal de confirmação mostra dados que o backend entregou; não recalcula contagens no cliente.
   - Botão "Restaurar" apenas chama endpoint — toda a lógica (cancelar ativo + undelete alvo + validar role) é transacional no backend.

5. **Design elegante e coerente com o já existente.**
   - Views `_atuais` em vez de espalhar `WHERE deletado_em IS NULL` em 15 queries.
   - Soft-delete só na fração-pai; filhas (`fracao_missoes`, `fracao_missao_bpms`) herdam via JOIN — sem cascata redundante.
   - Tokens visuais (`gold-soft`, `dark-panel`, fontes, espaçamentos) seguem a base já estabelecida em 6.1 — **não introduzir nova paleta** no chip/card/modal.
   - Nomes de rota seguem o padrão `/api/<recurso>[/<id>/<acao>]` já usado em 6.3/6.4.

6. **Auditoria obrigatória — `AUDITORIA_6_5.md`.**
   - Escopo: motivação, diff de schema, tabela LOC por arquivo, fluxo de save/restaurar, checklist dos 6 princípios, matriz de testes, riscos residuais, screenshots da UI preventiva.
   - Sem o AUDITORIA, a fase **não está pronta** — mesmo com todos os testes passando.
   - Padrão de referência: `AUDITORIA_6_4_1.md`.

**Regra de ouro quando em dúvida:** se a escolha em cima da mesa compromete um desses 6 princípios em troca de velocidade, **parar e perguntar** antes de seguir. O usuário prefere escopo menor + padrão mantido a escopo completo + dívida técnica.

---

## 2. Sub-entrega 6.5.a — UI preventiva de data

### 2.1 Banner "hoje" persistente

Chip no topo do painel operador, visível em upload, preview e confirmação:

```
┌─────────────────────────────────────────────────┐
│  📅  Hoje: quinta-feira, 24/04/2026             │
└─────────────────────────────────────────────────┘
```

Implementação:
- `app/templates/_components/hoje_chip.html` (novo) — `<div class="hoje-chip">`
- Backend injeta data atual (server-side, evita drift de timezone do cliente)
- CSS em `base.css`: chip estilo dark-panel + gold-soft, fonte 14px, sticky ao topo

### 2.2 Card "data detectada" no preview

Acima do cabeçalho, card proeminente:

```
┌──────────────────────────────────────────────────┐
│  Data detectada no texto:                        │
│                                                  │
│    23/04/2026  (quarta-feira — ONTEM)            │
│                                                  │
│  ⚠ Divergente de hoje (24/04). Confirme se       │
│     o texto é de um dia anterior.                │
└──────────────────────────────────────────────────┘
```

Estados:
| Condição | Cor | Texto auxiliar |
|---|---|---|
| `data == hoje` | verde (gold-soft) | "Hoje" |
| `data == hoje-1` | amarelo | "ONTEM — confirme se é retroativo" |
| `data == hoje+1` | amarelo | "AMANHÃ — previsão antecipada?" |
| `\|data - hoje\| > 1 dia` | laranja | "DIVERGENTE — confirme" |
| data não detectada | vermelho | **bloqueia salvar** até operador escolher data no seletor |

Implementação:
- `app/static/js/preview_data_check.js` (novo) — helper de linguagem natural ("ontem"/"amanhã"/dia-da-semana)
- Renderizado em `preview_missoes.js` (ou módulo paralelo) antes do cabeçalho
- CSS em `upload.css`: `.data-detectada-card.verde/amarela/laranja/vermelha`

### 2.3 Modal de confirmação antes de salvar

Interceptar click em "Confirmar e Salvar":

```
┌─────────────────────────────────────────────────┐
│              Confirmar gravação                 │
├─────────────────────────────────────────────────┤
│                                                 │
│  Unidade:   1 BPChq                             │
│  Data:      23/04/2026 (ONTEM)                  │
│  Frações:   3 frações, 8 missões                │
│                                                 │
│  [se upload ja existe (6.5.b)]                  │
│  Já existe dado salvo para essa data:           │
│     Upload de 14:32 hoje por AREI-01            │
│     (será substituído; poderá ser restaurado    │
│      no histórico)                              │
│                                                 │
│         [ Cancelar ]    [ Confirmar 23/04 ]     │
└─────────────────────────────────────────────────┘
```

Regra crítica: **botão afirmativo carrega a data no label** (`Confirmar 23/04`), não é genérico "OK". Reduz piloto automático.

Implementação:
- `app/static/js/modal_confirmar_salvar.js` (novo)
- Antes de 6.5.b: mostra só unidade/data/contagens
- Depois de 6.5.b: consulta `/api/uploads/existente?unidade=X&data=Y` e adiciona bloco "já existe"

### 2.4 Entregáveis 6.5.a

- `app/templates/_components/hoje_chip.html` — chip de data
- `app/static/js/preview_data_check.js` — card de data detectada + helper de linguagem natural
- `app/static/js/modal_confirmar_salvar.js` — modal final
- CSS em `base.css` e `upload.css`
- Testes: `tests/test_preview_data_check.py` (se houver helper de linguagem natural Python-side); JS não tem suite — validação manual
- Atualização `app/templates/operador/index.html` e preview correspondente pra incluir o chip e o card

---

## 3. Sub-entrega 6.5.b — Soft-delete + histórico de uploads

### 3.1 Modelo de dados

**Migration 008** — `migrations/008_uploads_soft_delete.sql`:

```sql
-- Tabela principal de uploads
CREATE TABLE IF NOT EXISTS smo.uploads (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id        UUID NOT NULL REFERENCES smo.usuarios(id) ON DELETE RESTRICT,
    unidade           TEXT NOT NULL,
    data              TEXT NOT NULL,
    criado_em         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    origem            TEXT NOT NULL DEFAULT 'whatsapp',  -- 'whatsapp' | 'xlsx' | 'edicao' | 'backfill'
    texto_original    TEXT,                              -- cru do WhatsApp, pra reprocessar
    substitui_id      UUID NULL REFERENCES smo.uploads(id) ON DELETE SET NULL,
    cancelado_em      TIMESTAMPTZ NULL,
    cancelado_por     UUID NULL REFERENCES smo.usuarios(id) ON DELETE RESTRICT,
    observacao        TEXT
);
CREATE INDEX IF NOT EXISTS idx_uploads_unidade_data
    ON smo.uploads(unidade, data, criado_em DESC);
CREATE INDEX IF NOT EXISTS idx_uploads_ativo
    ON smo.uploads(unidade, data) WHERE cancelado_em IS NULL;

-- Colunas de soft-delete e vinculação de upload em tabelas existentes
ALTER TABLE smo.fracoes
    ADD COLUMN IF NOT EXISTS upload_id    UUID NULL REFERENCES smo.uploads(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS deletado_em  TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS deletado_por UUID NULL REFERENCES smo.usuarios(id) ON DELETE SET NULL;
ALTER TABLE smo.cabecalho
    ADD COLUMN IF NOT EXISTS upload_id    UUID NULL REFERENCES smo.uploads(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS deletado_em  TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS deletado_por UUID NULL REFERENCES smo.usuarios(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_fracoes_ativas  ON smo.fracoes(unidade, data)    WHERE deletado_em IS NULL;
CREATE INDEX IF NOT EXISTS idx_cabecalho_ativo ON smo.cabecalho(unidade, data)  WHERE deletado_em IS NULL;
CREATE INDEX IF NOT EXISTS idx_fracoes_upload   ON smo.fracoes(upload_id);
CREATE INDEX IF NOT EXISTS idx_cabecalho_upload ON smo.cabecalho(upload_id);

-- Views de conveniência para leitura — reduzem risco de esquecer filtro
CREATE OR REPLACE VIEW smo.fracoes_atuais AS
    SELECT * FROM smo.fracoes WHERE deletado_em IS NULL;
CREATE OR REPLACE VIEW smo.cabecalho_atuais AS
    SELECT * FROM smo.cabecalho WHERE deletado_em IS NULL;
```

**Nota:** não se adiciona `upload_id` em `fracao_missoes` nem `fracao_missao_bpms` — elas herdam o estado de soft-delete da `fracao` pai via JOIN. Filtrar `WHERE fracao.deletado_em IS NULL` nas queries é suficiente. Reduz cascata de UPDATEs.

### 3.2 Backfill

**Migration 008 (continuação)** ou **`scripts/backfill_uploads.py`**:

```sql
-- Cria 1 upload sintético por (unidade, data) existente e associa linhas
WITH usuarios_sistema AS (
    SELECT id FROM smo.usuarios WHERE email = 'sistema@smo.local' LIMIT 1
),
agrupados AS (
    SELECT DISTINCT unidade, data FROM smo.fracoes WHERE upload_id IS NULL
),
inseridos AS (
    INSERT INTO smo.uploads (usuario_id, unidade, data, origem, observacao)
    SELECT (SELECT id FROM usuarios_sistema), a.unidade, a.data, 'backfill',
           'Backfill fase 6.5 — upload pré-existente agrupado retroativamente'
    FROM agrupados a
    RETURNING id, unidade, data
)
UPDATE smo.fracoes f
   SET upload_id = i.id
  FROM inseridos i
 WHERE f.unidade = i.unidade AND f.data = i.data AND f.upload_id IS NULL;
-- idem para smo.cabecalho
```

Pré-requisito: um usuário "sistema" em `smo.usuarios` (seed separado ou migration auxiliar).

### 3.3 Serviço `upload_service.py`

Novo módulo `app/services/upload_service.py`, ~220 LOC:

```python
@dataclass(frozen=True)
class Upload:
    id: str
    usuario_id: str
    unidade: str
    data: str
    criado_em: datetime
    origem: str
    texto_original: str | None
    substitui_id: str | None
    cancelado_em: datetime | None
    cancelado_por: str | None
    observacao: str | None


def criar_upload(
    usuario_id: str, unidade: str, data: str,
    texto_original: str | None, substitui_id: str | None,
    origem: str = "whatsapp"
) -> Upload: ...

def upload_ativo_por_dia(unidade: str, data: str) -> Upload | None:
    """Upload mais recente e não-cancelado — o que está "valendo"."""

def listar_uploads_por_dia(unidade: str, data: str) -> list[Upload]:
    """Histórico completo do dia, ordenado desc."""

def cancelar_upload(upload_id: str, usuario_id: str) -> None:
    """Marca cancelado_em e soft-deleta fracoes/cabecalho vinculados."""

def restaurar_upload(upload_id: str, usuario_id: str) -> Upload:
    """Cancela o ativo atual (se houver) e undelete as linhas do upload alvo.
    Transacional. Falha se upload_id já é o ativo."""
```

Regras invariantes:
- Só pode haver 1 upload ativo (não-cancelado) por `(unidade, data)` — enforced em `criar_upload` e `restaurar_upload` via transação + check.
- `cancelar_upload` é idempotente; chamado duas vezes no mesmo ID é no-op.
- `restaurar_upload` requer que o upload alvo não esteja já ativo.

### 3.4 Modificações em `db_service.py`

**`save_fracoes(fracoes, usuario_id, texto_original)` — nova assinatura:**

```python
def save_fracoes(
    fracoes: list[FracaoRow],
    usuario_id: str,
    texto_original: str,
) -> tuple[int, str]:
    """Retorna (numero_inseridos, upload_id novo)."""
    # Um upload por (unidade, data). Se varios dias/unidades no batch,
    # cria N uploads. Transacional.
    pares = {(r["unidade"], r["data"]) for r in fracoes}
    with get_connection() as conn:
        with conn.cursor() as cur:
            upload_ids: dict[tuple[str, str], str] = {}
            for unidade, data in pares:
                # 1. Consulta ativo anterior
                ativo_anterior = upload_ativo_por_dia(unidade, data)  # usa mesmo cur
                # 2. Marca ativo anterior como cancelado + soft-delete suas linhas
                if ativo_anterior:
                    cur.execute("UPDATE smo.uploads SET cancelado_em=NOW(), cancelado_por=%s WHERE id=%s",
                                (usuario_id, ativo_anterior.id))
                    cur.execute("UPDATE smo.fracoes SET deletado_em=NOW(), deletado_por=%s "
                                "WHERE upload_id=%s AND deletado_em IS NULL",
                                (usuario_id, ativo_anterior.id))
                # 3. Cria novo upload
                cur.execute("INSERT INTO smo.uploads (usuario_id, unidade, data, texto_original, substitui_id) "
                            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                            (usuario_id, unidade, data, texto_original, ativo_anterior.id if ativo_anterior else None))
                upload_ids[(unidade, data)] = cur.fetchone()["id"]

            # 4. INSERT novas frações com upload_id
            for row in fracoes:
                uid = upload_ids[(row["unidade"], row["data"])]
                cur.execute("INSERT INTO smo.fracoes (..., upload_id) VALUES (..., %s) RETURNING id",
                            (..., uid))
                ...
```

**Equivalente em `save_cabecalho`.**

**Queries de leitura — filtro obrigatório:**

Substituir em TODAS as queries de leitura `FROM smo.fracoes` por `FROM smo.fracoes_atuais`. Lista de arquivos a atualizar:
- `app/services/db_service.py` — `fetch_fracoes_by_range`, `fetch_vertices_by_range`, etc.
- `app/services/analytics_fracoes.py`
- `app/services/analytics_cabecalho.py`
- `app/services/analytics_catalogos.py`
- Qualquer `SELECT ... FROM smo.fracoes` remanescente

**Teste de robustez:** criar `tests/test_sem_leak_deletado.py` que faz `grep` no código por `FROM smo.fracoes` (sem `_atuais`) e falha. Previne regressão quando alguém adicionar query nova.

### 3.5 Endpoints novos em `app/routes/api.py`

| Método | Path | Descrição |
|---|---|---|
| `GET` | `/api/uploads?unidade=X&data=Y` | Lista histórico do dia — usado pela tela de histórico |
| `GET` | `/api/uploads/existente?unidade=X&data=Y` | Retorna metadata do upload ativo (usado pelo modal de confirmação 6.5.a) — `{existe: bool, criado_em, usuario_nome}` |
| `POST` | `/api/uploads/<id>/restaurar` | Restaura upload — só role `operador_arei` ou `admin` |
| `GET` | `/api/uploads/<id>/texto` | Retorna `texto_original` — pra debug/reprocessar |

Permissões:
- Listar/ver: operador, analista, admin.
- Restaurar: operador_arei, admin.
- Ver texto original: admin (pode conter PII).

### 3.6 UI de histórico

Nova tela: `/operador/historico/<unidade>/<data>`

- `app/templates/operador/historico.html` (novo)
- `app/static/js/historico_uploads.js` (novo)

Layout:

```
Histórico — 1 BPChq — 23/04/2026

┌──────┬───────────┬──────────┬───────────┬──────────┬─────────┐
│ Hora │ Usuário   │ Status   │ Origem    │ Frações  │ Ação    │
├──────┼───────────┼──────────┼───────────┼──────────┼─────────┤
│14:32 │ AREI-01   │ ATUAL    │ whatsapp  │ 3        │ —       │
│12:15 │ AREI-01   │ substit. │ whatsapp  │ 3        │Restaurar│
│10:02 │ AREI-02   │ substit. │ whatsapp  │ 5        │Restaurar│
└──────┴───────────┴──────────┴───────────┴──────────┴─────────┘
```

Clique em "Restaurar" abre modal de confirmação:

> "Vai desfazer o upload atual (14:32 por AREI-01) e voltar pro de 12:15. Os dados atuais NÃO serão perdidos — poderão ser restaurados depois. Confirmar?"

### 3.7 Entregáveis 6.5.b

- `migrations/008_uploads_soft_delete.sql` (schema + views)
- `scripts/backfill_uploads.py` (ou inline na migration)
- `app/services/upload_service.py` (novo)
- `app/services/db_service.py` (refactor + views)
- `app/routes/api.py` (+4 endpoints + mudança em `/api/salvar-texto` para passar `usuario_id`, `texto_original`)
- `app/templates/operador/historico.html`
- `app/static/js/historico_uploads.js`
- Queries atualizadas em `analytics_*.py` (views `_atuais`)
- `tests/test_uploads.py` (matriz restore/substitute/cancel; ~350 LOC)
- `tests/test_sem_leak_deletado.py` (previne regressão de filtro)
- `AUDITORIA_6_5.md`

---

## 4. Sequência de execução sugerida

Na sessão nova, executar em ordem:

1. **6.5.a.1** — banner "hoje" no painel operador (30min, trivial)
2. **6.5.a.2** — card de data detectada no preview (1h)
3. **6.5.a.3** — modal de confirmação (1h, versão sem "já existe")
4. **Commit parcial** `feat(6.5.a): UI preventiva de data`
5. **6.5.b.1** — migration 008 + backfill + seed usuário sistema
6. **6.5.b.2** — `upload_service.py` + testes unitários do service
7. **6.5.b.3** — refactor `save_fracoes` / `save_cabecalho` + testes de substituição
8. **6.5.b.4** — trocar queries de leitura pras views `_atuais` + teste anti-leak
9. **6.5.b.5** — endpoints `/api/uploads/*`
10. **6.5.b.6** — UI de histórico + integração com modal 6.5.a (bloco "já existe")
11. **6.5.b.7** — AUDITORIA_6_5.md
12. **Commit final** `feat(6.5): soft-delete + histórico de uploads`

Passos 1-4 podem ser commit separado se 6.5.b entrar depois (é o cenário mais provável — 6.5.a resolve UX imediato).

---

## 5. Queries afetadas — checklist

Antes de fechar a fase, validar que TODAS as queries de leitura filtram soft-delete:

```bash
# Este grep não pode retornar nada fora de db_service.save_* ou upload_service:
grep -rn "FROM smo.fracoes[^_]" app/services/ app/routes/
grep -rn "FROM smo.cabecalho[^_]" app/services/ app/routes/
```

Tudo que aparecer ou é escrita (save) ou precisa virar `_atuais`.

---

## 6. Checklist dos 6 princípios

1. **Tipagem forte**: `Upload` dataclass frozen; `upload_service` tipa retornos; nenhum `Any/cast`.
2. **Modularidade / 500 LOC max**: `upload_service.py` ~220, `db_service.py` cresce pra ~620 mas só porque acumula 3 fases — avaliar split em save/fetch se ficar >500 pós-refactor. Outros arquivos ficam bem abaixo.
3. **Segurança**:
   - Todas queries parametrizadas.
   - `restaurar_upload` valida role via decorator de autenticação.
   - `texto_original` pode conter PII (nomes, telefones) — acesso via endpoint restrito a admin.
   - CSRF em endpoints POST via middleware existente.
4. **Frontend burro**: restauração, validação de permissão e transacional no backend. JS só chama endpoint e mostra resultado.
5. **Design elegante**:
   - Views `_atuais` reduzem risco de regressão sem invadir queries individuais.
   - Soft-delete em fração-pai; filhas herdam via JOIN (sem cascata redundante).
   - UI de histórico segue tokens `gold-soft`/`dark-panel` existentes.
6. **Auditoria obrigatória**: `AUDITORIA_6_5.md` com checklist + LOC + riscos + pipeline + screenshots da UI preventiva.

---

## 7. Riscos residuais a nomear

1. **Esquecer filtro `deletado_em IS NULL`** em query nova → dados deletados vazam.
   - Mitigação: views `_atuais` + teste grep anti-leak + code review.

2. **Crescimento indefinido**: linhas soft-deletadas acumulam. Pra CPChq (7 unidades × 365 dias × ~20 frações/dia) ≈ 50k linhas/ano — irrelevante em 10 anos.

3. **Concorrência**: dois operadores uploading mesmo `(unidade, data)` ao mesmo tempo → race em `criar_upload`. Mitigar com `SELECT ... FOR UPDATE` na consulta do ativo anterior, dentro da transação.

4. **Restauração depois de muitos uploads sobrepostos** → UI com 10+ versões fica confusa. Paginar ou colapsar em "ver mais" depois de 5.

5. **Texto original contém PII**: guardar criptografado seria ideal; no MVP, restringir acesso via role. Registrar na AUDITORIA_6_5 como dívida.

6. **Backfill não tem texto_original**: uploads retroativos ficam com `texto_original = NULL`. OK — identificável pela origem `backfill`.

7. **`atualizado_em` nas tabelas**: com soft-delete, semântica muda — `atualizado_em` passa a refletir "última mudança incluindo deleção lógica". Documentar.

---

## 8. Testes obrigatórios

`tests/test_uploads.py` — matriz:

- Criar upload novo (sem anterior) → ativo, 0 substituições.
- Criar upload sobre existente → anterior fica cancelado e soft-deletado; novo fica ativo; `substitui_id` aponta pro anterior.
- Cancelar upload → linhas ficam soft-deletadas.
- Restaurar upload anterior → ativo atual cancela e é soft-deletado; alvo volta a ser ativo e undelete.
- Restaurar upload que já é ativo → erro amigável.
- Listar histórico → retorna ordem desc por `criado_em`.
- Leitura via `fracoes_atuais` → não vê soft-deleted.
- Leitura direta via `fracoes` → vê tudo (pra debug).
- Concurrency: 2 uploads simultâneos no mesmo (unidade, data) → segundo falha ou wins-last (documentar escolha).
- Views refletem corretamente após cada operação.

Suite total esperada: 240 → ~275 passed.

---

## 9. Dependências e pré-requisitos

- Usuário "sistema" em `smo.usuarios` — seed ou migration auxiliar antes da 008.
- Assume role `operador_arei` já distinguível no modelo de auth (ver `app/services/auth.py` ou equivalente — checar se existe antes de começar).
- Precisa do contexto do usuário logado em `/api/salvar-texto` — checar como `session["user_id"]` é exposto ao backend hoje.

---

## 10. Arquivos a criar / modificar — resumo

**Criar:**
- `migrations/008_uploads_soft_delete.sql`
- `scripts/backfill_uploads.py` (opcional, pode ser inline)
- `app/services/upload_service.py`
- `app/templates/_components/hoje_chip.html`
- `app/templates/operador/historico.html`
- `app/static/js/preview_data_check.js`
- `app/static/js/modal_confirmar_salvar.js`
- `app/static/js/historico_uploads.js`
- `tests/test_uploads.py`
- `tests/test_sem_leak_deletado.py`
- `AUDITORIA_6_5.md`

**Modificar:**
- `app/services/db_service.py` — refactor save + views em reads
- `app/services/analytics_fracoes.py` / `analytics_cabecalho.py` / `analytics_catalogos.py` — usar `_atuais`
- `app/routes/api.py` — +4 endpoints, modificar `/api/salvar-texto` para passar usuario_id/texto
- `app/templates/operador/index.html` (ou similar) — incluir chip "hoje"
- `app/static/css/base.css` — tokens do chip
- `app/static/css/upload.css` — estilos card data + modal

---

## 11. Escopo total

| Sub-entrega | LOC | Tempo estimado |
|---|---|---|
| 6.5.a (UI preventiva) | ~230 | ~2h30 |
| 6.5.b (soft-delete + histórico) | ~1240 | 2-3 dias |
| **Total** | **~1470** | **~3 dias** |

---

## 12. Contexto pra próxima sessão

- Branch de trabalho: `main` (sem feature branch no fluxo atual).
- Commit de referência imediatamente anterior: `fd31151` (feat 6.4 + 6.4.1).
- Estado do banco: migration 007 aplicada, `smo.unidades` populada com 7 unidades.
- Suite de testes: 240 passed.
- **Antes de começar**, ler:
  - Este documento
  - `AUDITORIA_6_4.md` e `AUDITORIA_6_4_1.md` (padrão de auditoria esperado)
  - `app/services/db_service.py:11-75` (save_fracoes atual)
  - `app/services/auth.py` ou equivalente (modelo de permissões)
- **Verificar pré-requisito**: existe coluna/campo pra identificar o usuário logado no payload de `/api/salvar-texto`? Se não, isso vira sub-item 0 — expor `session["user_id"]` no route.
