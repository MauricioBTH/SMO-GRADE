# PROMPT — Sistema C2 CPChq (Flask + Supabase + PostgreSQL)

Cole este prompt inteiro no novo chat para continuar o desenvolvimento.

---

## CONTEXTO DO PROJETO

Estou desenvolvendo um **Sistema de Comando e Controle de Meios Operacionais** para a **Brigada Militar — Comando de Policia de Choque (CPChq)** do Rio Grande do Sul.

### O que ja existe (Fase 0 — concluida)

Um arquivo `index.html` standalone que:
- Recebe upload de um `dados.xlsx` com duas abas (`fracoes` e `cabecalho`)
- Renderiza cards visuais por unidade (7 unidades: 1 a 6 BPChq + 4 RPMon)
- Agrupa cards do 1 BPChq por tipo de fracao (prontidao, patres, canil_batedores, operacao); demais unidades agrupam por faixa horaria (manha/tarde/noite)
- Gera cada card como imagem PNG para envio via WhatsApp
- Identidade visual: preto #000000, laranja #F7B900, branco #FFFFFF, cinza #57575A
- Logos das 7 unidades + CPChq embutidos em base64
- Layout mobile-first (cards 380px fixos) com grid responsivo no desktop

### Estrutura do dados.xlsx

**Aba `fracoes`** (36 registros atualmente):
```
unidade | data | turno | fracao | tipo | comandante | telefone | equipes | pms | horario_inicio | horario_fim | missao
```

Valores de `tipo`: prontidao, patres, canil, batedores, operacao

**Aba `cabecalho`** (1 registro por unidade):
```
unidade | data | turno | oficial_superior | tel_oficial | tel_copom | operador_diurno | tel_op_diurno | horario_op_diurno | operador_noturno | tel_op_noturno | horario_op_noturno | efetivo_total | oficiais | sargentos | soldados | vtrs | motos | ef_motorizado | armas_ace | armas_portateis | armas_longas | animais | locais_atuacao | missoes_osv
```

**Unidades:** 1 BPChq, 2 BPChq, 3 BPChq, 4 BPChq, 5 BPChq, 6 BPChq, 4 RPMon

### Arquivos no projeto (c:\Users\watso\gerador_cars_emprego\)
- `index.html` — painel do operador (standalone, funcional)
- `dados.xlsx` — planilha modelo com dados reais
- `logos_CPChq/` — 8 logos PNG (logo-1BPChq.png a logo-6BPChq.png, logo-4RPMon.png, logo-CPChq.png)

---

## O QUE PRECISA SER DESENVOLVIDO

### Arquitetura

```
Flask (hospedado no Render - tier gratuito)
  |-- /operador    --> upload xlsx, gera cards, salva no Supabase
  |-- /analista    --> dashboards, projecoes com pandas
  |-- /api/        --> endpoints REST
  |-- Supabase (PostgreSQL)
       |-- tabela fracoes (historico diario acumulado)
       |-- tabela cabecalho (resumos diarios acumulados)
```

- **Operador e analista acessam pelo mesmo link**, de qualquer rede
- **Supabase** como banco PostgreSQL (tier gratuito: 500MB, 50k req/mes)
- **Render** para hospedar o Flask (tier gratuito)

### Dois perfis de usuario

**Operador da mesa:**
- Alimenta diariamente com xlsx (fluxo atual)
- Gera cards para WhatsApp (formato vertical ~380px, como ja funciona)
- Ao carregar o xlsx, os dados sao salvos automaticamente no Supabase (historico)

**Analista:**
- Acessa painel separado (`/analista`)
- Le dados historicos do Supabase
- Gera projecoes e comparativos
- Cards em formato slide (16:9, fontes maiores, visual de apresentacao)

---

## FASES DE DESENVOLVIMENTO

### Fase 1 — Flask + Supabase (base)
- Criar projeto Flask com estrutura de pastas
- Configurar conexao com Supabase (PostgreSQL via psycopg2 ou supabase-py)
- Criar tabelas no Supabase: `fracoes` e `cabecalho` (mesma estrutura do xlsx + campo `created_at`)
- Migrar o `index.html` atual para template Flask em `/operador`
- No upload do xlsx: alem de renderizar, inserir dados no Supabase
- Manter toda a funcionalidade atual de geracao de cards

### Fase 2 — Painel do Analista (leitura + filtros)
- Rota `/analista` com painel proprio
- Leitura do historico do Supabase
- Filtros: por periodo (data inicio/fim), por unidade, mensal, semestral
- Tabelas e resumos dos dados historicos
- Mesma identidade visual (preto, laranja, branco, cinza)

### Fase 3 — Cards analiticos formato slide
- Layout 16:9 para apresentacoes
- Graficos de evolucao (Chart.js ou similar): efetivo, VTRs, armamento por periodo
- Cards comparativos entre unidades
- Exportacao como PNG (mesmo conceito do operador)

### Fase 4 — Projecoes e comparativos
- Media movel e tendencia por unidade (pandas/numpy)
- Comparativo mesmo periodo do ano anterior
- Sazonalidade (mes a mes)
- Indicadores: crescimento/reducao de efetivo, cobertura por area

---

## IDENTIDADE VISUAL

- Laranja: #F7B900
- Preto: #000000
- Branco: #FFFFFF
- Cinza: #57575A
- Logos das unidades disponiveis na pasta `logos_CPChq/`
- Design clean, intuitivo, elegante

## REGRAS DE AGRUPAMENTO DOS CARDS (manter no operador)

- 1 BPChq: agrupa por tipo de fracao (prontidao > patres > canil_batedores > operacao), ordena por horario_inicio dentro de cada grupo
- Demais unidades: agrupa por faixa horaria (manha/tarde/noite), ordena por horario_inicio
- Sempre gera card "Resumo da Jornada" como primeiro card

---

## INSTRUCOES

1. Comece pela **Fase 1**
2. Crie a estrutura do projeto Flask no diretorio `c:\Users\watso\gerador_cars_emprego\`
3. Mantenha o `index.html` original como referencia/backup
4. Use o `dados.xlsx` existente para testes
5. Me peca as credenciais do Supabase quando precisar (eu crio o projeto la)
6. A cada fase concluida, me mostre o que foi feito e valide antes de seguir


## PRINCÍPIOS INEGOCIÁVEIS

1. Tipagem forte, sem any, sem as, sem cast, sem unknow, sem record, sem passtrought
2. modularidade máxima, máx 500loc, separação de responsabilidades e funções
3. segurança contra ataques (zod, sanitizehtml, xss, Dompurify, sql injection)
4. front burro, lógica no backend
5. Design elegante, minimalista, intuitivo e clean
6. Auditoria de conformidade pra verificar se os principios foram rigorosamente cumprido 
---
