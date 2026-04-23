# AUDITORIA — Fase 6.2.5 (Triagem de Missoes Pendentes)

Data: 2026-04-20
Escopo: UI de triagem humana para catalogar os 2948 textos legados que o
backfill fuzzy (Fase 6.2) nao conseguiu casar automaticamente. Hotfix/
complemento da 6.2 — NAO e a 6.3 do roadmap.

---

## 1. Resumo executivo

- 149 testes (Fase 6.2) -> **161 testes** agora (0 falhas, 3.25s).
- 1 service novo + 1 rota estendida (+3 endpoints) + 1 template + 1 JS + 1
  arquivo de testes. Nenhum arquivo acima de 500 LOC.
- `token_set_ratio` (nao `token_sort_ratio`) para casar nome curto dentro de
  texto longo — resolve o problema central da 6.2 (score ~25 colapsando).
- Pre-processamento `_preparar_fuzzy` remove pontuacao antes do matching —
  necessario porque `token_set_ratio` compara tokens inteiros e "PRONTIDAO,"
  nao casa com "PRONTIDAO".
- Fluxo: commit imediato + modal. 1 UPDATE resolve todas as fracoes com
  aquele texto (idempotente via `WHERE missao_id IS NULL`).

## 2. Arquivos entregues (tabela LOC)

| Arquivo | LOC | Estado | Propósito |
|---|---|---|---|
| `app/services/triagem_missoes.py` | 322 | novo | dataclasses, agrupar/contar, sugerir, aplicar, criar+aplicar |
| `app/routes/admin_catalogos.py` | 245 | estendido (+98) | +3 rotas `/admin/catalogos/triagem-missoes{,/aplicar,/nova}` |
| `app/templates/admin/triagem_missoes.html` | 185 | novo | tabela + modal nativo `<dialog>` + paginacao |
| `app/static/js/triagem_missoes.js` | 49 | novo | abrir/fechar modal + fetch + reload (zero logica) |
| `tests/test_triagem_missoes.py` | 293 | novo | 12 testes (>8 do plano minimo) |

Total ~1094 LOC. Maior arquivo: service com 322 LOC (abaixo do limite de 500;
acima da estimativa inicial de 180 porque precisei de `_preparar_fuzzy` +
helpers de validacao que o prompt listava como “sanitizado” sem quantificar).

## 3. Contratos entregues — funcoes publicas do service

```
agrupar_pendentes(limit=20, offset=0) -> list[TextoPendente]
contar_pendentes() -> int
sugerir_candidatos(texto, catalogo, n=3, score_min=50) -> list[Candidato]
aplicar_mapeamento(texto, missao_id) -> AplicacaoResult
criar_e_aplicar(nome, descricao, texto) -> CriacaoResult
```

Retornos: `dataclass(frozen=True)` para `TextoPendente`, `Candidato`,
`AplicacaoResult`, `CriacaoResult`. Payloads da rota reusam `MissaoCreate`
(TypedDict) da 6.2.

## 4. Rotas entregues (todas `@role_required(["gestor"])`)

| Método | Rota | Body | Retorno |
|---|---|---|---|
| GET  | `/admin/catalogos/triagem-missoes` | `?pagina=1` | render_template |
| POST | `/admin/catalogos/triagem-missoes/aplicar` | JSON `{texto, missao_id}` | JSON ok/erro |
| POST | `/admin/catalogos/triagem-missoes/nova`    | JSON `{texto, nome, descricao?}` | JSON ok/erro |

Todos aceitam tambem `application/x-www-form-urlencoded` para debug via curl.

## 5. Auto-avaliacao — 6 principios

1. **Tipagem forte**: `from __future__ import annotations`, `dataclass(frozen=True)`
   para retornos, `TypedDict` reusado (MissaoCreate), `cast()` em boundary
   (cursor dict -> str), `| None` explicito. Zero `Any` no service.
2. **LOC <= 500**: maior arquivo 322 (`triagem_missoes.py`). Rotas estendidas
   ficaram em 245.
3. **Seguranca**:
   - `@role_required(["gestor"])` em todas as 3 rotas (teste: operador_alei -> 403).
   - Prepared statements em todas as queries (zero interpolacao).
   - Limites de input em constantes publicas (`MAX_TEXTO_LEN=500`,
     `MAX_NOME_LEN=120`, `MAX_DESCRICAO_LEN=300`) — truncados na rota antes
     do service e validados de novo dentro.
   - `criar_e_aplicar` em transacao atomica: INSERT + UPDATE no mesmo `conn`,
     `rollback` em qualquer excecao (teste cobrindo falha do UPDATE).
   - Idempotencia estrutural via `WHERE missao_id IS NULL` no UPDATE (teste
     verifica que a clausula esta no SQL).
4. **Frontend burro**: `triagem_missoes.js` tem 49 linhas e apenas:
   `abrirModal`, `fecharModal`, `_post`, `aplicar`, `criar`. Zero ordenacao,
   ranqueamento ou filtro — backend ja entrega pendentes agrupados +
   candidatos rankeados.
5. **Design consistente**: reusa `admin-wrap`, `admin-nav`, `admin-table`,
   `.admin-create`, `.flash` do shell dos outros admin/*. Modal nativo
   `<dialog>` sem libs externas.
6. **Auditoria**: este arquivo + docstrings nos servicos + comentarios
   explicando decisoes chave (token_set vs token_sort, `_preparar_fuzzy`).
7. **Dominio**: o catalogo passado a `sugerir_candidatos` vem de
   `catalogo_service.listar_missoes(somente_ativas=True)`. CANIL/PATRES/
   PRONTIDAO nao aparecem la como missao (sao fracoes) — logo nao sao
   sugeridos. Se o seed eventualmente contiver esses nomes, devem ser
   removidos manualmente.

## 6. Decisoes arquiteturais (o que foi debatido e porque)

### 6.1 `token_set_ratio` em vez de `token_sort_ratio`

`token_sort_ratio` ordena tokens e compara strings inteiras — penaliza
diferenca de comprimento. Texto longo (50 chars) comparado a nome curto
(9 chars) gerava score ~25. `token_set_ratio` compara o conjunto (aceita
subconjunto), entregando 100 quando o nome curto esta "dentro" do texto.

### 6.2 `_preparar_fuzzy` remove pontuacao antes do match

Descoberto durante testes: `normalizar("PRONTIDAO, RESERVA ...")` preserva
virgulas, e `token_set_ratio` considera "PRONTIDAO," como token distinto de
"PRONTIDAO". Score caia para 18.75. Solucao: regex `[^A-Z0-9 ]+` -> " "
apos `normalizar()`. `normalizar()` nao foi alterado para nao quebrar o
match exato do parser.

### 6.3 `score_min=50` (nao 85)

No backfill automatico, 85 protege contra matches errados sem humano na
cadeia. Aqui o gestor valida visualmente. Corte em 50 ordena a lista mas
nao esconde candidatos plausiveis. O gestor sempre tem a opcao "+ Nova" se
nada cabe.

### 6.4 JSON nas rotas POST

As rotas aceitam tanto JSON quanto form. JS usa fetch com JSON (evita
reload cru); curl/debug pode usar form. Retorno sempre JSON para o JS
decidir alert vs reload.

### 6.5 Modal + `location.reload()`

Alternativa descartada: atualizacao parcial via DOM (sem reload). Motivo:
violaria "frontend burro" — seria preciso reordenar a lista de pendentes no
cliente quando uma linha sai. Reload delega tudo ao backend.

### 6.6 Paginacao server-side (20/pagina)

Com dedupe, o prompt estimou 50-200 textos unicos para 3000 fracoes. 20/
pagina garante que o gestor raramente passa de 10 paginas. ORDER BY freq
DESC + tiebreak por texto ASC e estavel entre paginas.

## 7. Cobertura de testes (12 testes)

| # | Teste | O que prova |
|---|---|---|
| 1 | `ordena_por_freq_desc_tiebreak_por_texto_asc` | SQL ORDER BY correto + filtro `missao_id IS NULL AND missao <> ''` |
| 2 | `respeita_limit_e_offset` | params `(7, 14)` chegam ao LIMIT/OFFSET |
| 3 | `top_n_desc_acima_do_score_min` | ordenacao desc + respeita `n` |
| 4 | `catalogo_vazio` | `[]` sem DB |
| 5 | `token_set_ratio_casa_nome_curto_em_texto_longo` | contrato principal: score >= 50 no caso real dos 2948 |
| 6 | `update_filtra_por_missao_id_null` | SQL tem `missao_id IS NULL` e `SET missao_id` |
| 7 | `rollback_quando_update_falha` | `rollback=True`, `committed=False` — nenhuma missao orfa |
| 8 | `nome_vazio_rejeitado` | ValueError antes de abrir conexao |
| 9 | `get_sem_login_redireciona` | 302/401 sem sessao |
| 10 | `get_com_role_operador_retorna_403` | operador_alei bloqueado |
| 11 | `texto_pendente_frozen` | dataclass imutavel |
| 12 | `candidato_frozen` | dataclass imutavel |

Total da suite: **161 passed in 3.25s** (149 anteriores + 12 novos).

Pontos nao cobertos (aceitos):
- POST `/aplicar` e `/nova` em si — testados indiretamente pelo service. Um
  teste end-to-end exigiria mock mais pesado do banco e nao adiciona sinal
  alem do que ja esta testado.
- UniqueViolation em `criar_e_aplicar` — caminho simples (captura +
  rollback + ValueError amigavel); codigo identico ao padrao da Fase 6.2.

## 8. Proximos passos fora do escopo 6.2.5

- Rodar `python -m scripts.migrate` em producao (nao precisa migration nova).
- Navegar ate `/admin/catalogos/triagem-missoes` logado como gestor e triar
  os top-10 textos — devem resolver 60-80% das 2948 fracoes.
- Gestor descobrira missoes que faltam cadastrar; usar "+ Nova" cria e
  aplica numa so acao.
- Fase 6.3 (roadmap original): form ALEI + Oracle Cloud + hardening.
- Fase 7 (sugerida na 6.2): editor in-place no preview de parse.
- Triagem de municipios (mesma UI, outro alvo): fora do escopo porque a
  coluna `municipio_nome_raw` e nova e ainda nao populou historico.

## 9. Arquivos modificados (diff resumido)

```
A  app/services/triagem_missoes.py         +322
M  app/routes/admin_catalogos.py           +98 (3 rotas novas + helpers)
A  app/templates/admin/triagem_missoes.html +185
A  app/static/js/triagem_missoes.js        +49
A  tests/test_triagem_missoes.py           +293
A  AUDITORIA_6_2_5.md                      (este arquivo)
```
