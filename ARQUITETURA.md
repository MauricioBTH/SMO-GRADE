# Arquitetura SMO-GRADE — Sistema C2 CPChq

Documento de arquitetura consolidado. Fonte única da verdade para decisões técnicas e de produto do sistema.

Atualizado: 2026-04-19

---

## 1. Visão Geral

Sistema de Comando e Controle de Meios Operacionais (SMO) do Comando de Polícia de Choque (CPChq) da Brigada Militar do Rio Grande do Sul.

Recebe dados de escala e emprego de efetivo das unidades subordinadas (1° ao 6° BPChq, 4° RPMon), armazena histórico, e produz análises/relatórios para o comandante.

**Stack atual:**

- Backend: Flask (Python 3.11+) + psycopg2
- Banco: PostgreSQL (Supabase hoje, servidor local da intel no destino)
- Frontend: Jinja2 + JS vanilla + Chart.js
- Parser: regex customizado para texto WhatsApp semi-padronizado

**Repositório:** https://github.com/MauricioBTH/SMO-GRADE

---

## 2. Fluxo de Informação

O dado percorre três camadas humanas antes de chegar ao banco:

```
Cmt de Pelotão (WhatsApp texto livre)
        ↓
Intel Local — ALEI (organiza parcialmente)
        ↓
Intel Regional — AREI (insere no sistema, normaliza)
        ↓
Banco de Dados (SMO) → Comandante (cards e análises)
```

Cada camada adiciona variação ao texto original. O **Operador Regional (AREI)** é a última camada humana antes do banco — e por isso concentra a responsabilidade de normalização no preview do app.

Com a Fase 6, o Operador Local (ALEI) passa a ter a opção de submeter via formulário web direto, eliminando a renormalização no regional para essas unidades.

---

## 3. Roles de Acesso

| Role | Permissões |
|---|---|
| **Gestor** | Acesso total, edição de qualquer dado, auditoria, gestão de usuários |
| **Operador AREI** | Cria missão nova no catálogo, **funde duplicatas**, edita dados de qualquer unidade local, supervisiona preview |
| **Operador ALEI** | Insere/edita dados **apenas da sua unidade**, pode criar missão nova (mas não funde duplicatas) |

Cada `Operador ALEI` é amarrado à sua unidade (ex.: `1°BPChq`) via campo `usuarios.unidade`. Middleware bloqueia submissão cross-unidade.

---

## 4. Matriz SMO (Texto WhatsApp Novo)

### 4.1 Por fração (campos estruturados)

- `Missão:` — **obrigatório**, FK para catálogo curado (`smo.missoes`)
- `OSv:` — **opcional**, texto livre com regex tolerante para número/ano
- `Município:` — **obrigatório**, lista fechada por unidade

Nomenclatura mantida como `Missão` e `OSv` por tradição militar. Não renomear para "Natureza" ou "Operação".

### 4.2 Cabeçalho (preservado)

Cabeçalho numérico e campo `Missões/Osv:` permanecem como hoje. Funcionam como espelho visual (cards, planilha em texto puro) e não são fonte de verdade para análise.

**Toda análise do app puxa de `fracoes.missao_id` e `fracoes.osv`, nunca do cabeçalho.**

### 4.3 Exemplo de fração no novo formato

```
2°/3° T
Cmt: 1° Sgt PM Kulmann (55) 99946-6614
Equipes: 06 (22 PMs)
Missão: CVLI
OSv: OSV-001/P3/2BPCHQ/2026
Município: Santa Maria
Hora: 07h às 19h
```

---

## 5. Catálogo Curado de Missões

### 5.1 Modelo

```sql
CREATE TABLE smo.missoes (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nome_canonico   VARCHAR(80) UNIQUE NOT NULL,
  ativa           BOOLEAN DEFAULT TRUE,
  criada_em       TIMESTAMPTZ DEFAULT NOW(),
  criada_por      UUID REFERENCES smo.usuarios(id)
);

CREATE TABLE smo.missao_aliases (
  alias           VARCHAR(120) PRIMARY KEY,
  missao_id       UUID REFERENCES smo.missoes(id) ON DELETE CASCADE
);
```

### 5.2 Catálogo-semente

Extraído dos textos atuais no banco + arquivos `.txt` do repositório, validado pelo Gestor antes de entrar em produção. Exemplos recorrentes: `CVLI`, `PTM`, `Escola Segura`, `Kerb`, `Show`, `Prontidão`, `Guarda Batalhão`, `Apoio (Draco/MBA)`, `Policiamento Montado`, `Reserva de OCD`.

### 5.3 Match fuzzy

Quando operador digita/cola texto de missão:

| Similaridade | Indicador | Comportamento |
|---|---|---|
| ≥ 85% | Verde | Auto-sugere a missão canônica, operador confirma com Enter |
| 60% a 85% | Amarelo | Lista top-3 candidatos, operador escolhe |
| < 60% | Vermelho | Oferece botão "+ Criar nova missão" |

Algoritmo: trigram similarity (`pg_trgm` do Postgres) ou Levenshtein. Ao confirmar, texto original vira alias automaticamente — catálogo aprende sozinho.

### 5.4 Governança

Tela `/admin/missoes` (AREI e Gestor):

- Lista com contagem de uso por missão
- Merge de duplicatas (aliases migram automaticamente)
- Desativar missão sem apagar histórico (ex.: eventos sazonais como Kerb)
- Relatório "missões criadas nos últimos N dias" para auditoria

---

## 6. Modelo de Dados (Schema `smo`)

Todas as tabelas SMO ficam em schema dedicado `smo.*`, isoladas do `public` para convivência futura com tabelas do sistema Grade no mesmo Postgres.

### 6.1 Tabelas principais

- `smo.usuarios` — login, role, unidade vinculada, TOTP
- `smo.missoes` — catálogo canônico
- `smo.missao_aliases` — aprendizado automático
- `smo.municipios` — lista fechada (replicada da API do Grade)
- `smo.cabecalho` — dados agregados por unidade/data (schema atual + colunas de auditoria)
- `smo.fracoes` — uma linha por fração, com `missao_id` (FK), `osv` (texto), `municipio_id` (FK)
- `smo.audit_log` — trail de INSERT/UPDATE/DELETE

### 6.2 Colunas novas em `fracoes`

```sql
ALTER TABLE smo.fracoes
  ADD COLUMN missao_id    UUID REFERENCES smo.missoes(id),
  ADD COLUMN osv          VARCHAR(120),
  ADD COLUMN municipio_id UUID REFERENCES smo.municipios(id),
  ADD COLUMN atualizado_em TIMESTAMPTZ DEFAULT NOW();
```

Campo `missao` existente (texto livre) permanece durante transição para suportar dados legados, depois é descartado.

### 6.3 Migrations

Scripts SQL numerados em `migrations/NNN_descricao.sql`, idempotentes, aplicáveis com `psql -f` ou script Python. Substituem `init_tables()` hardcoded.

---

## 7. Autenticação e Segurança

### 7.1 Credenciais

- Usuário + senha (bcrypt)
- **2FA TOTP obrigatório** para Gestor e Operador AREI
- 2FA opcional para Operador ALEI (reduz fricção na ponta)
- Sessão expira em 8h
- Rate limit: 5 tentativas de login / min / IP

### 7.2 Infraestrutura

- HTTPS obrigatório (Let's Encrypt)
- Cloudflare grátis na frente (DDoS + rate limit adicional)
- `fail2ban` no VPS bloqueando força-bruta
- Audit log de toda ação sensível (via triggers Postgres)
- Backup `pg_dump` diário para storage externo

### 7.3 Exposição

Servidor fica na **rede paralela da intel** (internet aberta, não intranet institucional). VPS dedicado ou futuramente servidor físico da intel. Nunca expor Postgres diretamente — sempre através da API Flask.

---

## 8. API REST Versionada

Endpoints agrupados sob `/api/v1/...` desde o início, para servir como contrato estável quando o sistema Grade for consumir dados do SMO no futuro.

Nunca quebrar `/api/v1/*` sem bumpar para `/api/v2/*`.

---

## 9. Fluxos de UI

### 9.1 Operador ALEI (form web direto)

1. Login no navegador do PC da mesa da intel local
2. Dashboard da unidade com histórico de escalas
3. Botão "+ Nova Previsão" → seleciona data
4. Preenche **cabeçalho** (campos numéricos validados)
5. Adiciona **frações** uma a uma:
   - Cmt + telefone
   - Equipes + PMs
   - Missão (combobox com busca no catálogo, botão "+ Criar nova" se ausente)
   - OSv (texto opcional)
   - Município (dropdown da área da unidade)
   - Horário início/fim
6. **Preview** em tempo real do texto WhatsApp formatado
7. Submete → banco recebe dado estruturado + sistema gera texto WhatsApp pronto para copiar
8. ALEI cola o texto gerado no grupo WhatsApp da cadeia (pro regional/Cmdo), como antes

O **benefício líquido** pro ALEI é gerar o texto WhatsApp sem erro em 30% do tempo. Adoção acontece por atração, não imposição.

### 9.2 Operador AREI (preview de normalização)

Para unidades que ainda submetem via WhatsApp cru (transição):

1. Operador cola texto WhatsApp recebido no preview
2. Parser extrai frações e campos brutos
3. Para cada fração, sistema sugere:
   - Missão (match fuzzy, verde/amarelo/vermelho)
   - Município (dropdown pré-selecionado quando inferível do texto)
4. Operador confirma/corrige/cria novo
5. Submete → banco recebe estruturado

Com adoção crescente do form ALEI, AREI tende a virar supervisor de exceções, não digitador primário.

---

## 10. Análise e Charts

Todos os agregados analíticos derivam de `fracoes` com joins em `missoes` e `municipios`. Charts confiáveis habilitados:

- Emprego por **unidade** (existente)
- Emprego por **município** (novo)
- Emprego por **missão** (novo, via catálogo curado)
- **Matriz missão × município** (cross dos dois eixos)
- **Série temporal** de uma missão específica ao longo do período
- **Rastreabilidade por OSv** — lista todas as frações amparadas por uma OSv

Drill-down a partir de qualquer agregado leva até a lista de frações subjacentes.

---

## 11. Portabilidade e Fusão com Grade

### 11.1 Princípio

SMO permanece autônomo no curto prazo. Será fundido ao sistema Grade (stack React/Tailwind/shadcn, Postgres local da intel) quando o momento político permitir — hoje o chefe prioriza entregas pequenas e frequentes do SMO para justificar pedido de recursos.

### 11.2 Hooks preparados desde já

- Schema `smo.*` isolado
- Migrations numeradas
- `DATABASE_URL` neutro (não `SUPABASE_DB_URL`)
- Zero dependência Supabase-específica — só `psycopg2` + SQL padrão
- API REST versionada
- Assets vendor baixados localmente (sem CDN externa) — requisito de rede fechada
- Auditoria obrigatória (requisito militar)

### 11.3 No dia da fusão

- Schema + dados migram via `pg_dump`/`pg_restore` para Postgres local
- Frontend Flask/Jinja é **aposentado** e substituído por telas React do Grade que consomem `/api/v1/*`
- Backend Flask pode permanecer como serviço de ingestão/parser ou ser reescrito em Node; decisão adiada para o momento da fusão
- Usuários não se recadastram se Grade adotar o mesmo modelo de auth

### 11.4 Anti-pattern: não fazer agora

- Reescrever em Node/React preventivamente — desperdício
- Criar auth compartilhada com Grade — Grade ainda não tem auth consolidada
- Migrar storage/assets pro Grade — SMO não tem storage relevante

---

## 12. Infraestrutura

### 12.0 Estado atual

- Flask rodando **localmente** no PC do operador regional (`localhost:5000`)
- DB no **Supabase free tier** (projeto `nrjpjftblrrmvyjptefr`), já ativo e funcional
- Custo atual: **R$0**
- Limitação: só o PC do regional acessa o app; ALEI não tem como preencher form remoto

### 12.1 Infra-alvo oficial (sem verba) — Oracle Cloud Free Tier

Arquitetura alvo para habilitar acesso de ALEI/AREI/Gestor via internet, mantendo custo zero:

```
ALEI (PC intel local)   ──┐
AREI (PC intel regional) ├──HTTPS──► Oracle Free VPS ────► Supabase (DB)
Gestor (qualquer PC)     ──┘         (Flask + nginx)       (free tier)
```

- **Oracle Cloud Always Free**: 4 OCPU ARM + 24 GB RAM ou 2 x86 micro, permanente
- Região **`sa-saopaulo-1`** (São Paulo) — latência baixa para RS
- nginx + gunicorn + Let's Encrypt
- Cloudflare free na frente (DNS + DDoS)
- Cron interno a cada 5 min faz `curl localhost:5000/health` para evitar desativação por ociosidade
- Backup `pg_dump` semanal do Supabase para Supabase Storage (1 GB grátis)
- **Acesso via IP direto do Oracle** até o sistema consolidar — sem domínio próprio. HTTPS com certificado autoassinado ou via Cloudflare Tunnel. Aceitável na fase de validação.
- **Custo total: R$0 permanente**. Domínio próprio (~R$40/ano) fica como upgrade futuro, quando adoção justificar nome amigável.

### 12.2 Upgrade pago (se e quando a verba vier)

- **VPS Hetzner** (~R$28/mês) — 2vCPU / 4GB RAM — recomendado quando a Oracle apertar ou se quiser SLA previsível
- Migração Oracle → Hetzner é trocar IP e redeployar (1h)

### 12.3 Longo prazo (fusão com Grade)

- Servidor físico dedicado da intel — Postgres local substitui Supabase
- SMO Flask migra para o mesmo host ou é consumido via API pelo Grade
- VPN/WireGuard opcional para camada extra de acesso
- `DATABASE_URL` já neutro torna essa migração trivial

### 12.4 Latência double-hop

Cada request do usuário faz: **browser → Oracle (São Paulo) → Supabase (EUA) → Oracle → browser**. Na prática, 200-400ms por chamada. Imperceptível para forms, eventualmente perceptível em charts pesados. Se virar gargalo, mitigação futura: cache em memória no Oracle ou migração para Postgres no próprio Oracle.

### 12.5 Por que não Vercel

- Serverless tem cold start e timeouts que quebram parsing pesado
- Conexões Postgres de serverless são caras (obriga pooler)
- Hospedagem cloud pública EUA contradiz o destino final em servidor militar local
- Oracle Free já oferece VPS tradicional grátis — Vercel vira retrabalho

---

## 13. Fases do Projeto

| Fase | Status | Escopo |
|---|---|---|
| 1 | Concluída | Flask + Supabase + parser xlsx |
| 2 | Concluída | Painel do Analista com filtros |
| 3 | Concluída | Cards analíticos formato slide |
| 4 | Concluída | Projeções pandas/numpy, 86 testes pytest |
| 5 | Concluída | Entrada via texto WhatsApp (operador regional) |
| **6** | **Próxima** | Matriz nova (Missão/OSv/Município), catálogo curado, roles, form ALEI, hooks de portabilidade |
| 6.5 | Planejada | Hardening militar: audit_log robusto, assets locais, scripts backup, docs de deploy |
| 7+ | Futura | Bot WhatsApp (só se Fase 6 mostrar adoção <60% da ponta). **Sem PWA no SMO** — mobilidade será atendida pelo app mobile do sistema Grade no futuro. |
| Fusão | Indefinida | Integração com sistema Grade — aguarda momento político e maturidade do Grade |

### 13.1 Cortes de entrega da Fase 6 (troféus pro chefe)

- **Entrega 6.1** (~1 semana) — **executada no PC local (como hoje)**: migrations + schema `smo` + auth + roles funcionando. Demo pro chefe no próprio PC do regional.
- **Entrega 6.2** (~1,5 semana) — **ainda local**: matriz nova + parser atualizado + catálogo curado + preview AREI + charts novos. Demo pro chefe segue no PC do regional.
- **Entrega 6.3** (~1 semana) — **sobe para Oracle Free**: form web ALEI + tela gestão de catálogo + deploy hardening. Esta entrega **exige infra exposta** e é o evento que justifica (ou dispensa) pedido de verba.

Racional do corte: 6.1 e 6.2 iteram rápido sem atrito de deploy; 6.3 marca o momento de ir ao ar, virando "lançamento" pras locais e argumento concreto para verba.

---

## 14. Decisões Arquiteturais Rejeitadas

Documentadas para não serem revisitadas sem novo contexto:

### 14.1 Extrair região/operação de texto livre via classificador

Proposto inicialmente: dicionário de sinônimos + regex + classificação pós-parse. **Rejeitado** em 2026-04-19 — "muito trabalho, não vai pegar exato, erro invalida análise". Solução correta: controlar na entrada (matriz nova) ao invés de adivinhar na saída.

### 14.2 Enum "Tipo de Emprego" macro

Proposto como eixo complementar à missão (Policiamento Ostensivo, Prontidão, Apoio, etc.). **Rejeitado** em 2026-04-19 — não agrega valor distinto de `missao`. Não reintroduzir.

### 14.3 Município como texto livre

Proposto como alternativa ao dropdown. **Rejeitado** — inviabiliza análise confiável (grafias variadas: "S. do Livramento" vs "Sant'Ana" vs "Livramento"). Mantido como lista fechada.

### 14.4 Integrar SMO ao Grade agora

Proposto: reescrever SMO em React dentro do Grade. **Rejeitado** — contradiz estratégia de entregas pequenas e frequentes do chefe. Integração adiada para momento futuro com hooks preparados.

### 14.5 Hospedar no Vercel

Proposto. **Rejeitado** — serverless inadequado para Flask + parsing pesado, e hospedagem cloud pública EUA contradiz destino final em servidor militar local. VPS escolhido.

### 14.7 Reescrever fluxo como script CLI local diário

Proposto como alternativa de custo zero (`python app.py` no terminal, sem web). **Rejeitado** — elimina o form ALEI, exige presença física no PC do regional, e é passo atrás em relação ao Flask local atual. Modelo atual (Flask local + Supabase) já cobre o cenário sem verba; Oracle Free cobre o cenário com acesso remoto.

### 14.6 Remover campo `Missões/Osv` do cabeçalho

Proposto: derivar das frações, eliminar redundância. **Rejeitado** — cards e planilha em texto puro coexistem com o app, e o cabeçalho alimenta esses formatos. Mantido como espelho visual. Análise ignora.

---

## 15. Referências Cruzadas

- `PROMPT_FASE5.md` — especificação original da Fase 5 (texto WhatsApp)
- `PROMPT_MULTI_UNIDADE.md` — suporte multi-unidade no parser
- `app/services/whatsapp_parser.py` — parser principal
- `app/services/whatsapp_patterns.py` — regex e mapeamentos
- `app/models/database.py` — inicialização de schema (será migrado para `migrations/`)
- `app/services/supabase_service.py` — CRUD (será renomeado para `db_service.py` quando migrar)
