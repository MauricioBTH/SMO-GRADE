# AUDITORIA FASE 6.4.1 — catalogo de unidades + municipio-sede

Data: 23/04/2026
Escopo: introduzir `smo.unidades` (7 unidades: 1°-6° BPChq + 4° RPMon) com
`municipio_sede_id`. Resolver passa a derivar municipio para missoes em
quartel (Prontidao/Pernoite/Retorno) que nao trazem municipio na linha do
WhatsApp.

## 1. Motivacao

Ate 6.4, missoes em quartel caiam no validador com "sem municipio no
catalogo", pois a linha canonica do WhatsApp para Prontidao nao carrega
municipio. Mas missao + municipio e a dimensao-chave para analise — nao da
pra analisar C2 sem atribuir municipio a missao. Solucao: o municipio-sede
da unidade e uma informacao fechada e estavel, que o catalogo pode
conhecer; o resolver derivando essa dimensao elimina o falso-bloqueio.

## 2. Diff de schema (migration 007)

```sql
CREATE TABLE IF NOT EXISTS smo.unidades (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome              TEXT NOT NULL,
    nome_normalizado  TEXT NOT NULL UNIQUE,
    municipio_sede_id UUID NOT NULL REFERENCES smo.municipios(id) ON DELETE RESTRICT,
    ativo             BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_unidades_municipio_sede
    ON smo.unidades(municipio_sede_id);
```

Idempotente (padrao 003-006). `ON DELETE RESTRICT` em `municipio_sede_id`
protege contra deletar um municipio ainda referenciado como sede.

## 3. Seed das sedes (lista oficial do CPChq-CMDT)

| Unidade    | Municipio-sede   |
|------------|------------------|
| 1° BPChq   | Porto Alegre     |
| 2° BPChq   | Santa Maria      |
| 3° BPChq   | Passo Fundo      |
| 4° BPChq   | Caxias do Sul    |
| 5° BPChq   | Pelotas          |
| 6° BPChq   | Uruguaiana       |
| 4° RPMon   | Porto Alegre     |

Idempotente via `ON CONFLICT (nome_normalizado) DO NOTHING`. Rodar:
`python -m scripts.seed_unidades`.

## 4. Tabela LOC

| Arquivo                              | LOC | Status |
|--------------------------------------|-----|--------|
| migrations/007_unidades.sql          | 23  | OK     |
| scripts/seed_unidades.py             | 89  | OK     |
| app/services/unidade_service.py      | 104 | OK     |
| app/services/whatsapp_catalogo.py    | 196 | OK     |
| tests/test_unidades.py               | 200 | OK     |

Todos bem abaixo do teto de 500 LOC.

## 5. Normalizacao das variantes

`normalizar_codigo_unidade` aceita e unifica:

| Entrada       | Saida      |
|---------------|------------|
| `1° BPChq`    | `1 BPCHQ`  |
| `1º BPChq`    | `1 BPCHQ`  |
| `1°BPChq`     | `1 BPCHQ`  |
| `1ºBPChq`     | `1 BPCHQ`  |
| `1 BPChq`     | `1 BPCHQ`  |
| `1BPChq`      | `1 BPCHQ`  |
| `4° RPMon`    | `4 RPMON`  |
| `4ºRPMon`     | `4 RPMON`  |
| `4° rpmon`    | `4 RPMON`  |

Regex `(\d{1,3})\s*[°º]?\s*([A-Za-z]+)` extrai digito + sigla. Uppercase
da sigla garante matching idempotente. Coverage em `TestNormalizarCodigoUnidade`
(11 casos parametrizados + vazio/sem-digito).

## 6. Fluxo do resolver (whatsapp_catalogo)

```
for fr in fracoes:
    unidade_raw = fr["unidade"]  # "1° BPChq"
    for m in fr.missoes:
        _resolver_vertice(
            vertice=m,
            unidade_raw=unidade_raw,
            cache_uni={"1 BPCHQ": Unidade(...), ...},
            cache_muni_por_id={...},
            ...
        )
```

Regra de fallback em `_resolver_vertice`:

```python
if em_quartel and not vertice["municipio_id"] and unidade_raw:
    chave = unidade_service.normalizar_codigo_unidade(unidade_raw)
    uni_obj = cache_uni.get(chave)
    if uni_obj:
        vertice["municipio_id"] = uni_obj.municipio_sede_id
        vertice["municipio_nome_raw"] = cache_muni_por_id[sede_id].nome
    else:
        avisos.append("Unidade X sem municipio-sede cadastrado ...")
```

Precondicoes enforced:
- **Nao sobrescreve municipio digitado**: so fallback quando `municipio_id`
  ficou `None` (operador deixou em branco ou nao achou match no catalogo).
- **So em_quartel**: missoes fora de quartel devem trazer municipio no
  texto — se nao trouxerem, erro do validador permanece (comportamento
  desejado, evita derivar "falsamente" para patrulhamento).
- **Degradacao segura**: se a tabela nao existe (rollout parcial), cache
  fica vazio e fallback vira no-op — parser continua funcionando.

## 7. Checklist dos 6 principios

1. **Tipagem forte**
   - `Unidade` dataclass frozen em `catalogo_types.py` (id, nome,
     nome_normalizado, municipio_sede_id, ativo).
   - Assinaturas do resolver explicitam `cache_uni: dict[str, object]` e
     `cache_muni_por_id: dict[str, object]` (objects = Unidade/Municipio —
     evita ciclo de import com `catalogo_types`).
   - Um novo `# type: ignore[attr-defined]` em `whatsapp_catalogo.py`
     para `unidade_service.normalizar_codigo_unidade` (segue padrao dos
     2 ja existentes no mesmo arquivo, por import tardio).

2. **Modularidade / 500 LOC max**
   - `unidade_service.py` 104 LOC (isolado de catalogo_service porque
     o catalogo de unidades tem semantica diferente — fechado, pequeno,
     sem CRUD de UI).
   - Assinatura de `_resolver_vertice` cresceu (era 6 params, agora 10),
     mas todos sao colaboradores explicitos — preferido a criar
     singleton ou contexto implicito.

3. **Seguranca**
   - Queries em `unidade_service` 100% parametrizadas via psycopg2.
   - `normalizar_codigo_unidade` nao propaga caracteres nao-alfanumericos
     para SQL (regex descarta tudo que nao e digito + letra).
   - Nenhum endpoint novo; acesso so via `whatsapp_catalogo` dentro do
     fluxo de upload ja autenticado.

4. **Frontend burro**
   - Nenhuma mudanca no frontend. Operador continua vendo "Municipio:"
     preenchido no preview — agora com o nome da sede no lugar do vazio.
   - Validador backend continua dono da regra.

5. **Design elegante / coerente**
   - Tabela segue exatamente o padrao dos demais catalogos SMO (UUID +
     nome_normalizado UNIQUE + timestamps + ativo).
   - Lookup API reusa o idioma de `lookup_bpm_por_codigo` /
     `lookup_missao_por_nome` (match por nome_normalizado, `None` quando
     nao encontrado).
   - `Unidade` dataclass frozen segue `Crpm`/`Municipio`/`Missao`/`Bpm`.

6. **Auditoria obrigatoria**
   - Este arquivo + 17 testes novos (240 total, era 223).

## 8. Testes

- Total: **240 passed** (era 223; +17 novos em `test_unidades.py`).
- Grupos novos:
  - `TestNormalizarCodigoUnidade` — 11 parametros + vazio/sem-digito.
  - `TestUnidadeDataclass` — frozen.
  - `TestResolverUnidadeSedeFallback` — 4 cenarios:
    1. em_quartel sem muni: deriva sede OK.
    2. em_quartel com muni explicito: nao sobrescreve.
    3. Unidade nao cadastrada: emite aviso.
    4. Nao em_quartel: fallback desligado.

Comando: `python -m pytest -q`
Saida: `240 passed in 3.38s`

## 9. Riscos residuais

1. **Unidade fora do catalogo (ex: 7° BPChq no futuro)**
   - Hoje `UNIDADES_SEDE` e lista fixa. Se CPChq criar nova unidade,
     admin precisa rodar seed manual. Custo aceitavel (unidades mudam
     muito raramente); automacao via UI admin fica para fase posterior.

2. **Municipio-sede incorreto no seed**
   - Lista foi validada com o usuario antes do seed. `ON DELETE RESTRICT`
     em municipio_sede_id impede remocao acidental do municipio no
     catalogo sem antes desvincular a unidade.

3. **Preview nao reflete a sede visualmente**
   - O operador AREI nao ve explicitamente "este municipio veio da sede".
     Atualmente aparece preenchido no combobox, o que preserva o fluxo
     usual. Se o operador quiser alterar, e livre. Nao adiciono badge
     de "derivado" — complexidade de UI nao proporcional ao beneficio.

## 10. Arquivos criados/modificados

**Criados**
- `migrations/007_unidades.sql`
- `scripts/seed_unidades.py`
- `app/services/unidade_service.py`
- `tests/test_unidades.py`
- `AUDITORIA_6_4_1.md` (este arquivo)

**Modificados**
- `app/services/catalogo_types.py` — +`Unidade` dataclass frozen.
- `app/services/whatsapp_catalogo.py` — cache de unidades,
  `cache_muni_por_id`, parametros adicionais em `_resolver_vertice`,
  fallback por sede para em_quartel sem municipio.
