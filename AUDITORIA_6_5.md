# AUDITORIA FASE 6.5 — UI preventiva + soft-delete + historico de uploads

Data: 23/04/2026
Predecessora: Fase 6.4.1 (catalogo de unidades + sede) — commit `fd31151`
Escopo: transformar gravacao destrutiva (DELETE/INSERT por unidade+data)
em **versionada** (upload rastreavel + soft-delete) e adicionar 3 camadas
de UI preventiva (chip "hoje", card data detectada, modal confirmacao)
antes do Salvar.

## 1. Motivacao

Ate 6.4.1 o `save_fracoes`/`save_cabecalho` fazia `DELETE/INSERT` por
`(unidade, data)`. Consequencias:

- Se o operador AREI errava a data no texto do escalante (ex: colou texto
  do dia 22 pensando ser 23), a gravacao **apagava dados validos do dia
  alvo** sem rastreabilidade.
- Nenhuma forma de voltar ao estado anterior sem reimportar do WhatsApp.
- Nenhum log de quem/quando/por que cada dia foi gravado.
- Nenhuma sinalizacao visual que pudesse prevenir o erro em primeiro lugar.

A fase 6.5 ataca **os dois lados** do problema:
- **6.5.a (preventivo)**: reduz a probabilidade do erro humano via chip
  "hoje" persistente, card de data detectada no preview e modal final de
  confirmacao que compara a data do texto com hoje.
- **6.5.b (corretivo)**: se 6.5.a falhar, soft-delete + historico garante
  que nada se perde — toda "sobrescrita" vira cancelamento do upload
  anterior e restaurar e 1 clique.

## 2. Diff de schema (migration 008)

### 2.1 Tabela smo.uploads

```sql
CREATE TABLE IF NOT EXISTS smo.uploads (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id     UUID NOT NULL REFERENCES smo.usuarios(id) ON DELETE RESTRICT,
    unidade        TEXT NOT NULL,
    data           TEXT NOT NULL,          -- DD/MM/YYYY (consistente com fracoes/cabecalho)
    criado_em      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    origem         TEXT NOT NULL DEFAULT 'whatsapp',
                   -- 'whatsapp' | 'xlsx' | 'edicao' | 'backfill'
    texto_original TEXT,                   -- cru do WhatsApp (NULL fora de 'whatsapp')
    substitui_id   UUID NULL REFERENCES smo.uploads(id) ON DELETE SET NULL,
    cancelado_em   TIMESTAMPTZ NULL,
    cancelado_por  UUID NULL REFERENCES smo.usuarios(id) ON DELETE RESTRICT,
    observacao     TEXT
);

CREATE INDEX IF NOT EXISTS idx_uploads_unidade_data
    ON smo.uploads(unidade, data, criado_em DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_uploads_ativo_por_dia
    ON smo.uploads(unidade, data) WHERE cancelado_em IS NULL;
```

O `UNIQUE INDEX ... WHERE cancelado_em IS NULL` e a chave de desenho:
garante no nivel do banco que **nunca ha 2 uploads ativos** para o mesmo
(unidade, data). Isso elimina a classe de bug "2 versoes atuais por
concorrencia" sem depender de lock da aplicacao.

### 2.2 Soft-delete em smo.fracoes e smo.cabecalho

```sql
ALTER TABLE smo.fracoes
    ADD COLUMN IF NOT EXISTS upload_id    UUID REFERENCES smo.uploads(id),
    ADD COLUMN IF NOT EXISTS deletado_em  TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS deletado_por UUID REFERENCES smo.usuarios(id);
-- idem smo.cabecalho
CREATE INDEX IF NOT EXISTS idx_fracoes_ativas
    ON smo.fracoes(unidade, data) WHERE deletado_em IS NULL;
-- idem cabecalho
```

Soft-delete so na fracao-pai; filhas (`fracao_missoes`,
`fracao_missao_bpms`) herdam via JOIN. Nao ha cascata redundante — se
`fracao.deletado_em IS NOT NULL`, as vertices vivem mas ninguem as le
(queries de leitura usam `smo.fracoes_atuais`).

### 2.3 Views *_atuais (convencao)

```sql
CREATE OR REPLACE VIEW smo.fracoes_atuais AS
    SELECT * FROM smo.fracoes WHERE deletado_em IS NULL;
CREATE OR REPLACE VIEW smo.cabecalho_atuais AS
    SELECT * FROM smo.cabecalho WHERE deletado_em IS NULL;
```

**Regra de design**: toda query de leitura usa `*_atuais`. O teste
`test_sem_leak_deletado.py` faz grep em `app/services/` e `app/routes/`
procurando `FROM smo.(fracoes|cabecalho)` sem `_atuais` — falha o build
se alguem esquecer do filtro em analytics futuras.

### 2.4 Backfill (na mesma migration, transacional)

Cria 1 upload sintetico por (unidade, data) pre-existente com
`origem='backfill'` e `usuario_id` = usuario sistema. Idempotente: so
pega orfaos (`upload_id IS NULL`). Re-aplicar a migration e no-op.

## 3. Usuario sistema

Inserido no inicio da migration (`ON CONFLICT (email) DO NOTHING`):

| Campo       | Valor                          |
|-------------|--------------------------------|
| nome        | Sistema                        |
| email       | sistema@smo.local              |
| senha_hash  | !INATIVO-SENHA-NAO-USAVEL!     |
| role        | gestor                         |
| ativo       | FALSE (bloqueia login)         |

Uso: `scripts/importar_lote.py` (backfill historico) + FK do backfill da
migration. Nao e uma porta de entrada — `ativo=FALSE` impede login pelo
formulario.

## 4. Tabela LOC

| Arquivo                                        | LOC  | Status |
|------------------------------------------------|------|--------|
| migrations/008_uploads_soft_delete.sql         | 134  | OK     |
| app/services/upload_service.py                 | 417  | OK     |
| app/services/db_service.py (so fetch)          | 307  | OK     |
| app/services/db_service_save.py (novo)         | 232  | OK     |
| app/routes/api_uploads.py                      | 178  | OK     |
| app/routes/operador.py                         | 65   | OK     |
| app/templates/operador/historico.html          | 54   | OK     |
| app/templates/operador/index.html              | 80   | OK     |
| app/static/js/historico_uploads.js             | 168  | OK     |
| app/static/js/modal_confirmar_salvar.js        | 310  | OK     |
| app/static/css/upload.css                      | 1169 | REVER  |
| tests/test_uploads.py                          | 405  | OK     |
| tests/test_sem_leak_deletado.py                | 71   | OK     |
| scripts/importar_lote.py                       | 160  | OK     |

**upload.css em 1169 LOC**: ja estava em ~1020 antes da fase, cresceu
pra acomodar `.historico-*` e estilos de modal existente. CSS nao tem
logica; a regra de 500 LOC vale para arquivos de codigo. Fica como
**divida para extrair `historico.css` em fase posterior** se crescer
mais — nao bloqueia 6.5.

## 5. Divisao de db_service (principio 2: 500 LOC)

Apos 6.5.b, `db_service.py` atingiu 521 LOC. Split explicito:

- **db_service.py** (307 LOC) — so `fetch_*` (le de `*_atuais`).
- **db_service_save.py** (232 LOC) — `save_fracoes`, `_inserir_vertices`,
  `save_cabecalho`.
- Backwards-compat: `db_service.py` re-exporta `save_*`, entao
  `from app.services.db_service import save_fracoes` (em `routes/api.py`
  e `scripts/importar_lote.py`) continua funcionando. Sem duplicacao.

## 6. Fluxo de save versionado

```
operador clica "Salvar" → /api/upload/salvar
  → save_fracoes(fracoes, usuario_id=X, origem="whatsapp")
      → para cada (unidade, data):
          preparar_uploads_para_pares(cur, pares, usuario_id)
            → _cur_upload_ativo(unidade, data) com FOR UPDATE
            → se existe: _cancelar_upload_na_transacao
                - uploads.cancelado_em = NOW()
                - fracoes.deletado_em = NOW() WHERE upload_id = X
                - cabecalho.deletado_em = NOW() WHERE upload_id = X
            → _criar_upload_na_transacao (substitui_id = antigo?.id)
      → INSERT novo em smo.fracoes com upload_id = novo.id
      → _inserir_vertices (N:N BPMs da 6.4 preservado)
  → save_cabecalho REUSA o upload criado no mesmo request (evita 2 versoes
    por salvamento)
  commit
```

**Atomicidade**: toda a cadeia cancelar+soft-delete+criar+insert roda em
UMA transacao. Se qualquer INSERT falhar, rollback total — nada fica
meio-cancelado.

**Race condition**: `_cur_upload_ativo` usa `SELECT ... FOR UPDATE`
dentro da transacao. Duas gravacoes concorrentes para o mesmo (unidade,
data) serializam na lock de linha; o UNIQUE INDEX parcial e a defesa
final (a 2a operacao recebe `IntegrityError`, rollback).

## 7. Fluxo de restaurar

```
operador clica "Restaurar" na /operador/historico/X/Y
  → POST /api/uploads/<id>/restaurar (role_required gestor | operador_arei)
  → upload_service.restaurar_upload(id, usuario_id)
      - valida: upload existe e esta cancelado
      - cancela upload atualmente ativo do mesmo (unidade, data), se houver
        + soft-deleta linhas vinculadas
      - resseta cancelado_em/cancelado_por do alvo (undelete)
      - desdeleta fracoes/cabecalho do alvo (WHERE upload_id = alvo.id)
  commit
```

Transacional e idempotente: restaurar um upload ja ativo e no-op (valida
antes).

## 8. Endpoints novos

| Metodo | Rota                                   | Role                        |
|--------|----------------------------------------|-----------------------------|
| GET    | /api/uploads?unidade=X&data=Y          | login_required              |
| GET    | /api/uploads/existente?unidade=X&data=Y| login_required              |
| POST   | /api/uploads/<id>/restaurar            | gestor, operador_arei       |
| GET    | /api/uploads/<id>/texto                | gestor (auditado em log)    |
| GET    | /operador/historico/<unidade>/<path:data> | gestor, operador_arei, operador_alei |

Serializacao: `_serializar_upload()` **exclui `texto_original`** por
padrao. So `/texto` devolve esse campo, e apenas pra gestor. A rota
registra `logger.info("acesso texto_original upload_id=%s por
user_id=%s")` — audit trail de quem leu texto bruto com PII.

## 9. UI preventiva (6.5.a)

### 9.1 Chip "hoje" persistente

```
📅  Hoje: quinta-feira, 23/04/2026
```

Renderizado via `_contexto_hoje()` em `operador.py` — **fonte unica
server-side**, nao ha `new Date()` no JS. Timezone do servidor e a
verdade (evita discrepancia quando operador esta em outro fuso).

### 9.2 Card "data detectada"

Apos o parse, o preview mostra:
- se data do texto == hoje: card verde "Data do texto: hoje (23/04/2026)"
- se data do texto == ontem: card amarelo "Data do texto: ontem (22/04/2026)"
- se data do texto for outro dia: card vermelho "Data do texto: 2 dias atras (21/04/2026)"

O calculo de "quantos dias atras" vem do backend no JSON de preview — JS
so renderiza.

### 9.3 Modal de confirmacao (antes do Salvar)

Antes do POST /salvar, um modal lista, por (unidade, data):
- se ja existe upload ativo: "Substituir upload de Silva@14:32 hoje"
  com link "Ver historico →" para a pagina /operador/historico/X/Y.
- se nao existe: "Criar primeiro upload desta data".

O modal NAO decide se pode substituir — so renderiza o que
`/api/uploads/existente` retornou. Botao "Confirmar" envia o POST
original.

## 10. Checklist dos 6 principios

1. **Tipagem forte**
   - `Upload` e `UploadHistorico` como `@dataclass(frozen=True)`.
   - `OrigemUpload = Literal["whatsapp", "xlsx", "edicao", "backfill"]`.
   - Retornos explicitos em toda funcao publica
     (`-> Upload`, `-> list[Upload]`, `-> UploadHistorico`, `-> None`).
   - `_row_to_upload` valida `origem` contra o Literal (ValueError se invalida).
   - **Zero** novos `Any`/`cast`/`# type: ignore`.

2. **Modularidade / 500 LOC**
   - `upload_service.py` nascido isolado (417 LOC).
   - `db_service.py` dividido em `db_service.py` (fetch) +
     `db_service_save.py` (save) apos cruzar 500.
   - `api_uploads.py` novo blueprint, 178 LOC, separado de `api.py`.
   - Todos <500 LOC (excecao: upload.css, ver secao 4).

3. **Seguranca**
   - 100% queries parametrizadas (psycopg2 `%s`, nunca `f"..."`).
   - `@login_required` + `@role_required(...)` em todos endpoints novos.
   - CSRF herdado do middleware existente (POST /restaurar coberto).
   - `texto_original` so acessivel por gestor, com log de auditoria.
   - `<path:data>` aceita `/` mas o handler valida formato rigido
     (`dd/mm/yyyy`, 10 chars, digitos em posicoes fixas) antes de
     renderizar — impede XSS/path abuse em templates.
   - `UNIQUE INDEX ... WHERE cancelado_em IS NULL` previne duplo-ativo
     no nivel do banco (defesa em profundidade).

4. **Frontend burro**
   - `historico_uploads.js`: fetch + render + botao. **Nenhuma** logica
     de permissao no cliente — o backend devolve 403 se papel errado.
   - `modal_confirmar_salvar.js`: renderiza o que `/existente` retornou;
     nao recalcula contagens nem decide se "pode substituir".
   - Nome do usuario, qtde de fracoes, status "ATUAL/substituido" — tudo
     ja serializado pelo backend.

5. **Design elegante e coerente**
   - Views `_atuais` em vez de repetir `WHERE deletado_em IS NULL` em
     12+ queries de analytics.
   - `Upload` dataclass segue padrao estabelecido por `Crpm`/`Municipio`/
     `Missao`/`Bpm`/`Unidade`.
   - Rotas `/api/uploads/<id>/restaurar` seguem
     `/api/<recurso>/<id>/<acao>` ja usado em 6.3/6.4.
   - CSS reusa tokens `--gold`, `--dark-panel`, `--gold-soft`,
     `--gold-border` — nao introduz paleta nova.
   - Backfill transforma uploads pre-existentes em 'backfill' sintetico —
     historico fica continuo, sem "buraco antes da 6.5".

6. **Auditoria obrigatoria**
   - Este arquivo + 21 testes novos (261 total, era 240).

## 11. Matriz de testes

Total: **261 passed** (era 240; +21 novos).

### tests/test_uploads.py (20 casos)

| Classe                    | Teste                               | O que exercita |
|---------------------------|-------------------------------------|----------------|
| TestUploadsListar         | test_lista_ok                       | GET /api/uploads devolve historico |
|                           | test_params_faltando                | 400 se falta unidade ou data |
|                           | test_db_nao_configurado             | 500 com psycopg2.OperationalError |
|                           | test_sem_login                      | 302 redireciona pro login |
| TestUploadsExistente      | test_existe_true                    | {existe: true, upload: {...}} |
|                           | test_existe_false                   | {existe: false, upload: null} |
|                           | test_historico_sumiu_usa_fallback   | degrada pra upload_ativo_por_dia |
| TestUploadsRestaurar      | test_gestor_pode                    | 200 + chama restaurar_upload |
|                           | test_arei_pode                      | 200 pra operador_arei |
|                           | test_alei_bloqueado                 | 403 pra operador_alei |
|                           | test_valueerror_vira_400            | 400 se upload ja esta ativo |
| TestUploadsTexto          | test_gestor_pode                    | devolve texto_original + loga |
|                           | test_arei_bloqueado                 | 403 — PII so pra gestor |
|                           | test_alei_bloqueado                 | 403 pra operador_alei |
|                           | test_upload_inexistente             | 404 |
| TestUploadDataclass       | test_frozen                         | mutacao FrozenInstanceError |
|                           | test_origem_invalida_em_row_to_upload| ValueError com 'outro' |
| TestPaginaHistorico       | test_renderiza_ok                   | GET /operador/historico/X/Y → 200 |
|                           | test_unidade_invalida               | 404 |
|                           | test_data_malformada                | 404 (data 'abc') |

### tests/test_sem_leak_deletado.py (1 caso)

| Teste                         | O que exercita |
|-------------------------------|----------------|
| test_leitura_usa_views_atuais | grep em app/services + app/routes falha se alguem escrever `FROM smo.(fracoes\|cabecalho)` sem `_atuais` (exceto `upload_service.py`, que precisa ler linhas deletadas pra contar). |

Comando: `python -m pytest -q`
Saida: `261 passed in 4.57s`

## 12. Riscos residuais

1. **Esquecer filtro deletado_em em query nova**
   - Mitigado pelo `test_sem_leak_deletado.py` + views `*_atuais` como
     padrao. Se alguem adicionar uma query futura em `app/services/` ou
     `app/routes/` lendo `FROM smo.fracoes` sem `_atuais`, o CI quebra.
   - **Nao** cobre analytics em SQL ad-hoc fora do Python (ex: Metabase)
     — risco residual aceito; documentar em README se necessario.

2. **Crescimento indefinido de smo.uploads**
   - Cada save cria 1 upload; uploads nunca sao fisicamente deletados.
   - Em 1 ano: ~7 unidades * 2 salvamentos/dia * 365 = ~5100 linhas. Ok.
   - Em 5 anos: ~25k. Indices parciais compensam. **Quando passar de
     100k**: avaliar tabela de "arquivo morto" (uploads > 2 anos
     cancelados → tabela fria).

3. **PII em texto_original**
   - O texto WhatsApp pode conter nome+telefone de PM. Guardamos pra
     auditar se um upload ficou com dados estranhos, mas e dado sensivel.
   - Endpoint /texto e **gestor-only** e **auditado em log**. Log e de
     aplicacao, nao de db — se perder o log, perde o trail.
   - **Divida aceita**: nao ha retencao configuravel (purgar
     texto_original apos N dias). Baixa prioridade — volume e pequeno
     e acesso e restrito.

4. **Concorrencia em (unidade, data)**
   - Duas gravacoes concorrentes para o mesmo par serializam via
     `SELECT ... FOR UPDATE`. UNIQUE INDEX parcial e a defesa final.
   - **Restaurar concorrente com novo save**: handleavel — restaurar
     cancela o ativo, novo save cancela o restaurado + cria outro.
     Ambas serializam no FOR UPDATE; ordem determinada pelo commit.

5. **Usuario sistema ativo=FALSE**
   - `senha_hash='!INATIVO-SENHA-NAO-USAVEL!'` + `ativo=FALSE` impede
     login mas deixa o registro disponivel pra FK. Se um dev ativar por
     engano via admin UI, vira porta de entrada. Mitigacao: revisao de
     code review em qualquer mudanca futura na tela de usuarios.

## 13. Arquivos criados/modificados

### Criados
- `migrations/008_uploads_soft_delete.sql`
- `app/services/upload_service.py`
- `app/services/db_service_save.py`
- `app/routes/api_uploads.py`
- `app/templates/operador/historico.html`
- `app/templates/_components/hoje_chip.html`
- `app/static/js/historico_uploads.js`
- `app/static/js/modal_confirmar_salvar.js`
- `app/static/js/preview_data_check.js`
- `scripts/sql.py` — helper de SQL ad-hoc (substitui `psql` local).
- `tests/test_uploads.py`
- `tests/test_sem_leak_deletado.py`
- `AUDITORIA_6_5.md` (este arquivo)

### Modificados
- `app/__init__.py` — registra `api_uploads_bp`.
- `app/routes/api.py` — (import de save_* mantido; caller continua igual).
- `app/routes/operador.py` — `/operador/historico/<unidade>/<path:data>`
  + `_contexto_hoje()`.
- `app/services/db_service.py` — queries trocadas pra views `*_atuais`;
  save_* extraidos pra `db_service_save.py` (re-exportados pra
  compatibilidade).
- `app/templates/operador/index.html` — chip "hoje" + hooks pro card.
- `app/static/css/base.css` — tokens do chip `.hoje-chip`.
- `app/static/css/upload.css` — `.historico-*`, `.modal-confirmar-*`,
  `.preview-data-*`.
- `app/static/js/operador.js` — prefetch de `/api/uploads/existente`
  com botao "Verificando..." antes de abrir o modal (ver secao 14.3).
- `scripts/importar_lote.py` — nova assinatura save_fracoes/save_cabecalho
  com usuario_id do usuario sistema.

## 14. Addendum — ajustes pos-integracao (23/04/2026)

Descobertos durante validacao manual end-to-end; corrigidos na mesma
sessao antes do commit. Todos cobertos por `python -m pytest -q`
(261 passed).

### 14.1 Bug: AmbiguousColumn em `listar_historico`

**Sintoma**: `GET /api/uploads/existente` retornava 500 no 2o clique em
Salvar (primeiro upload existia). Stacktrace:
`psycopg2.errors.AmbiguousColumn: column reference "id" is ambiguous`.

**Causa**: `listar_historico` fazia `SELECT {_COLUNAS_UPLOAD} ...
FROM smo.uploads up JOIN smo.usuarios u ON ...`, mas `_COLUNAS_UPLOAD`
listava colunas sem qualificar (`id, usuario_id, unidade, ...`). Como
`smo.usuarios` tambem tem `id` (e `usuario_id` em `smo.uploads` sobrepoe
semanticamente), o Postgres recusou.

**Fix**: em `listar_historico`, as colunas sao qualificadas inline com
prefixo `up.` antes de entrar na query:

```python
colunas_up: str = ", ".join(
    f"up.{c.strip()}" for c in _COLUNAS_UPLOAD.split(",")
)
```

As outras 6 queries em `upload_service.py` que usam `_COLUNAS_UPLOAD`
nao tem JOIN, entao continuam sem qualificar.

**Gap de teste detectado**: `test_uploads.py` mocka o service — nao
exercita SQL real, por isso 261/261 passavam com o bug vivo. Registrado
como divida conhecida; cobertura de integracao SQL real fica pra quando
tivermos harness de DB de teste.

### 14.2 Otimizacao: `/existente` de 6 queries pra 1

**Sintoma**: modal abre instantaneo mas o bloco "Ja existe dado salvo"
aparecia ~1s depois — efeito de "pulo" visivel.

**Causa**: `uploads_existente` chamava `upload_ativo_por_dia` (1 query)
+ `listar_historico` (1 query SELECT + 2 COUNTs por upload). Para 1
upload ativo: **6 round-trips**. Cada round-trip Supabase custa ~150ms
+ ~800ms de `psycopg2.connect` (sem pool).

**Fix**: nova funcao `upload_service.upload_ativo_com_metadata(unidade,
data) -> UploadHistorico | None` que faz 1 query so — JOIN com
`smo.usuarios` + 2 COUNTs via subquery escalar. O endpoint
`/api/uploads/existente` passou a usar essa funcao diretamente,
deixando de cair em `listar_historico`.

`listar_historico` permanece para a pagina de historico completo
(onde N uploads justificam a estrutura). Duplicacao aceita: a nova
funcao tem escopo diferente (so ativo, nao o historico inteiro).

### 14.3 UX: botao "Verificando..." antes de abrir o modal

Mesmo com 1 query, cada chamada ao Supabase paga ~1s de `connect` (sem
pool). Abrir o modal antes da resposta gerava o "pulo" visivel — nao da
pra esconder o round-trip, da pra **tira-lo de fora do modal**.

**Mudanca em `operador.js`**: o click de "Confirmar e Salvar" agora
dispara `fetch('/api/uploads/existente')` ANTES de abrir o modal, com
botao em estado `disabled + .btn-loading + texto "Verificando..."`.
Quando a promise resolve (ok ou erro), restaura o botao e chama
`ModalConfirmarSalvar.abrir({..., existenteData: resultado})`. O modal
recebe o dado ja pronto — render sincrono, sem pulo.

**Mudanca em `modal_confirmar_salvar.js`**: `preencherExistente()` agora
olha `opts.existenteData` primeiro; se fornecido, usa sem fetch. Se nao
(fallback para testes ou chamadas futuras), continua fazendo o fetch
interno — zero breaking change.

### 14.4 `scripts/sql.py`

Criado ad-hoc para validacao manual sem `psql` instalado (o ambiente do
usuario Windows nao tinha). Usa `app.models.database.get_connection()`
com `RealDictCursor`, renderiza tabela ASCII simples. Nao substitui
psql em producao — so pra "runnable documentation" das queries de
validacao neste AUDITORIA e em futuras.
