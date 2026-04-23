# Prompt — Fase 6.2 (Catálogos: Missões, Municípios, CRPMs + evolução de `fracoes`)

Você vai implementar a **Entrega 6.2** do sistema SMO-GRADE (Sistema C2 do CPChq — Brigada Militar RS). Antes de qualquer código, leia a fonte de verdade arquitetural: `ARQUITETURA.md` e a auditoria da fase anterior `AUDITORIA_6_1.md` na raiz do repositório. A Fase 6.1 (migrations + schema `smo` + auth + roles + 2FA + `/admin/usuarios`) já está mergeada.

## Princípios inegociáveis (obrigatórios em todo código)

1. **Tipagem forte** — sem `Any`, sem casts cegos, sem `unknown`/`Record` genérico. Use `TypedDict`, `dataclass`, `Protocol`, `Literal`, tipos específicos. Em Python, `from __future__ import annotations` + tipos de retorno explícitos em toda função.
2. **Modularidade máxima** — nenhum arquivo ultrapassa **500 LOC**. Se um módulo crescer, divida por responsabilidade antes de continuar.
3. **Segurança ativa** — prepared statements (`%(...)s`/`%s`, nunca f-string em SQL), autoescape Jinja, todas as novas rotas com `@login_required` + role apropriado, FK `ON DELETE RESTRICT` nos catálogos, validação server-side de tudo.
4. **Front burro, lógica no backend** — matching fuzzy, agregações, rankings, filtros: tudo em Python. JS só renderiza JSON pronto.
5. **Design elegante, minimalista, intuitivo** — dropdowns em vez de campos livres onde houver catálogo; autocomplete server-side; sem poluição visual. Siga o estilo de `app/templates/admin/usuarios.html`.
6. **Auditoria de conformidade ao final** — produza `AUDITORIA_6_2.md` com LOC por arquivo, pontos de tipagem/segurança e autoavaliação dos 6 princípios.

## Contexto rápido

- **Tabelas atuais** (schema `smo`): `fracoes`, `cabecalho`, `usuarios`, `schema_migrations`.
- **Legado em `smo.fracoes`**: a coluna `missao` guarda texto livre (ex.: `"PATRULHAMENTO OSTENSIVO"`, `"OPERACAO CENTRO"`), sujeito a variação de digitação. Vamos normalizar via catálogo curado.
- **Arquivo-fonte para seed de municípios**: `API_Municipios_CRPMs.txt` na raiz. Contém as **21 CRPMs** do RS (Art. 3º) com suas circunscrições — cada CRPM tem lista de municípios separada por vírgula. Parser deve extrair sigla, nome, sede e a lista de municípios.

## Escopo da Entrega 6.2 (o que está dentro)

### 1. Migration 003 — Catálogos

Arquivo: `migrations/003_catalogos.sql`.

```sql
CREATE TABLE smo.crpms (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sigla       VARCHAR(20) UNIQUE NOT NULL,    -- "CPC", "CPM", "CRPM/VRS", etc.
  nome        VARCHAR(120) NOT NULL,
  sede        VARCHAR(80),
  ordem       SMALLINT NOT NULL UNIQUE,       -- I..XXI da norma
  ativo       BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE smo.municipios (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nome        VARCHAR(120) NOT NULL,
  crpm_id     UUID NOT NULL REFERENCES smo.crpms(id) ON DELETE RESTRICT,
  ativo       BOOLEAN NOT NULL DEFAULT TRUE,
  UNIQUE (nome, crpm_id)
);
CREATE INDEX idx_municipios_crpm ON smo.municipios(crpm_id);
CREATE INDEX idx_municipios_nome ON smo.municipios(LOWER(nome));

CREATE TABLE smo.missoes (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nome        VARCHAR(120) UNIQUE NOT NULL,   -- nome curado, caixa alta
  descricao   TEXT,
  ativo       BOOLEAN NOT NULL DEFAULT TRUE,
  criada_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_missoes_nome ON smo.missoes(LOWER(nome));
```

Seed (no próprio SQL ou via `scripts/seed_catalogos.py` — escolha o que for mais simples de manter idempotente):

- **21 CRPMs**: parse de `API_Municipios_CRPMs.txt`. Ordem I..XXI vira `ordem` 1..21. Extrair sigla (ex.: `CRPM/VRS`), nome completo, sede.
- **Municípios**: todos os municípios listados na norma, cada um com `crpm_id` apontando para o seu comando regional.
- **Missões iniciais**: lista curada mínima (pode iniciar com 8–12 padrões observados nos TXT já importados — `PATRULHAMENTO OSTENSIVO`, `OPERACAO CENTRO`, `ESCOLTA`, `CANIL`, `PATRES`, `PMOB`, `ROTA DAS CONVIVENCIAS`, etc.). Liste no prompt antes de semear.

### 2. Migration 004 — Evolução de `smo.fracoes`

Arquivo: `migrations/004_fracoes_v2.sql`.

```sql
ALTER TABLE smo.fracoes
  ADD COLUMN missao_id     UUID REFERENCES smo.missoes(id) ON DELETE RESTRICT,
  ADD COLUMN osv           VARCHAR(40),
  ADD COLUMN municipio_id  UUID REFERENCES smo.municipios(id) ON DELETE RESTRICT,
  ADD COLUMN atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE INDEX idx_fracoes_missao    ON smo.fracoes(missao_id);
CREATE INDEX idx_fracoes_municipio ON smo.fracoes(municipio_id);
```

Observações:
- A coluna `missao` (texto legado) permanece — será lida pelo backfill e depois marcada como deprecated em comentário, mas não removida nesta entrega.
- `atualizado_em` deve ser atualizada via trigger ou via service layer em todo UPDATE. Preferir service layer (simplicidade).

### 3. Backfill — `scripts/backfill_missoes.py`

Script idempotente que:
1. Lê todas as linhas de `smo.fracoes` com `missao_id IS NULL` e `missao` não-vazia.
2. Normaliza o texto: uppercase, sem acentos, trim.
3. Tenta match exato contra `smo.missoes.nome` (uppercase/sem acentos).
4. Se não casar exato, aplica **match fuzzy** (`rapidfuzz.ratio >= 85`) contra todas as missões ativas — registra `missao_id` só se houver um único candidato >= 85.
5. Casos ambíguos (>=85 em 2+ missões) ou sem match: escreve em `backfill_missoes_relatorio.txt` listando `fracao_id`, texto original, candidatos com score.
6. **Não inventa missões novas** — só vincula a existentes. Gestor revisa o relatório e, se necessário, adiciona missões ao catálogo antes de rodar de novo.

Dependência nova: `rapidfuzz==3.10.1` em `requirements.txt`.

### 4. Services tipados

- `app/services/catalogo_service.py` — CRUD de `crpms`, `municipios`, `missoes`. TypedDicts `MissaoCreate/Update`, `MunicipioCreate/Update`, `CrpmCreate/Update`. Validações: nome único por escopo, normalizador de caixa, `crpm_id` existente.
- `app/services/db_service.py` — **atualizar** `save_fracoes`/`fetch_fracoes_by_range` para incluir `missao_id`, `osv`, `municipio_id`. Mantém compat com callers legados (aceita payload sem as novas colunas, grava `NULL`).
- `app/services/whatsapp_parser.py` — quando extrair `MISSÃO:` / `OSv:` / `Município:` do texto, popular os 3 campos novos no dicionário de fração. Lookup de `missao`→`missao_id` e `municipio`→`municipio_id` via `catalogo_service`. Falhou o lookup: grava só o texto em `missao`/`municipio_nome_raw` (temporário), emite aviso no `resultado["avisos"]`.

### 5. Rotas de API

- `GET /api/catalogos/missoes?q=patr` — autocomplete, retorna até 20 missões que começam com ou contêm `q` (case-insensitive).
- `GET /api/catalogos/municipios?crpm=CRPM/VRS&q=novo` — autocomplete filtrado por CRPM.
- `GET /api/catalogos/crpms` — lista as 21 na ordem.
- Todas com `@login_required`. Leitura liberada para qualquer role autenticado.

### 6. Admin de catálogos (`/admin/catalogos/*`) — Gestor apenas

- `/admin/catalogos/missoes` — listar, criar, editar nome, ativar/desativar
- `/admin/catalogos/municipios` — listar com filtro por CRPM, criar, editar, ativar/desativar (não excluir — FK com `RESTRICT`)
- `/admin/catalogos/crpms` — **read-only** (não tem botão de criar/editar; os 21 são constantes normativas)
- Rotas em `app/routes/admin.py` (ou split em `admin_catalogos.py` se passar de 200 LOC).
- Templates em `app/templates/admin/` reusando o estilo de `usuarios.html`.
- Todas com `@role_required(["gestor"])`.

### 7. Analytics novos (painel do analista)

- Endpoint `GET /api/analytics/por-missao?data_inicio=&data_fim=&unidade=` — retorna `[{missao: str, total_pms: int, total_equipes: int, horas: float}]` ordenado por `total_pms` desc.
- Endpoint `GET /api/analytics/por-municipio?...` — análogo, por município (join fracoes→municipios).
- Dois charts novos no painel do analista (`app/templates/analista/...`) — barra horizontal top 10 missões e top 10 municípios no período.
- Toda agregação **em Python/SQL no backend** — JS só plota com Chart.js (já usado no projeto).

### 8. Testes

`tests/test_catalogos.py`:
- CRUD de missão: criar, editar nome, não permitir duplicado, desativar
- CRUD de município com `crpm_id` válido/inválido
- Autocomplete filtra por CRPM e por `q`
- FK `ON DELETE RESTRICT` impede deletar missão em uso

`tests/test_backfill.py`:
- Match exato liga `missao_id` corretamente
- Match fuzzy ≥85 com um só candidato vincula
- Match ambíguo não vincula; registra no relatório

`tests/test_analytics_por_missao.py`:
- Agrega corretamente por missão no período
- Filtro por unidade respeita; sem unidade retorna todas

Manter os 118 testes da 6.1 passando.

### 9. Atualizações na UI existente

- Forms de criação/edição de fração (se houver tela — checar `operador_arei` atual): trocar o campo `missao` de texto livre por `<select>` populado via `/api/catalogos/missoes`; campo `municipio` por `<select>` que depende do CRPM selecionado (encadeado). Backend **continua aceitando texto livre** temporariamente para não quebrar imports de TXT, mas UI força catálogo.
- Se não houver tela de edição de fração hoje, documentar em `AUDITORIA_6_2.md` §8 e deixar para 6.3.

### 10. Auditoria final — `AUDITORIA_6_2.md`

Ao terminar, produza o relatório seguindo o template de `AUDITORIA_6_1.md`:

- Arquivos novos/modificados com LOC
- Arquivos próximos/acima de 500 LOC (idealmente zero)
- Pontos de tipagem: `Any`, `dict` sem params, casts — ou "nenhum"
- Pontos de segurança: SQL parametrizado, FK com RESTRICT, role apropriado em cada rota nova, validação server-side dos lookups de catálogo
- Resultado do backfill em DB de teste: N linhas vinculadas, N ambíguas, N sem match
- Autoavaliação dos 6 princípios, passou/falhou com justificativa

## O que NÃO está em escopo da 6.2 (não faça)

- Form ALEI de edição de fração no browser — é **6.3**
- Deploy Oracle Cloud / endurecimento — **6.3**
- Audit log via triggers — **6.5**
- Remoção da coluna `missao` textual (só após backfill consolidado em 6.3+)
- Cadastro novo de CRPMs pela UI — fora de escopo (lista normativa fechada)

## Como operar

- Use `TodoWrite` para rastrear cada item do escopo; marque em andamento/concluído ao longo da execução.
- Antes de editar um arquivo existente, leia-o.
- Prefira `Edit` a `Write` em arquivos existentes.
- Rode `python -m pytest -q` ao final e confirme verde.
- Não toque em nada fora do escopo listado.
- Ao final, pare e aguarde revisão humana antes de seguir para 6.3.
