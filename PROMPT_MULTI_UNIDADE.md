# Prompt: Suporte Multi-Unidade no Parser WhatsApp

## Contexto

Sistema C2 CPChq (Flask + Supabase). O operador cola texto WhatsApp no frontend, backend parseia cabecalho + fracoes, preview editavel, confirma e salva.

**Problema atual:** o parser trata o texto inteiro como 1 unidade. Se o operador colar 7 unidades juntas, todas as fracoes saem com `unidade='1 BPChq'` (primeiro match) e o cabecalho mistura dados.

**Objetivo:** suportar texto de 1 OU N unidades no mesmo fluxo. Quando N=1, comportamento identico ao atual.

## Marcador de unidade

Cada unidade começa com (com ou sem `*`):
```
DADOS PARA PLANILHA DE COMANDO E CONTROLE DE MEIOS OPERACIONAIS
BRIGADA MILITAR
CPChq
1° BATALHÃO DE POLICIA DE CHOQUE
Previsão do dia 15/04/2026
```
ou:
```
*DADOS PARA PLANILHA DE COMANDO E CONTROLE DE MEIOS OPERACIONAIS*
*BRIGADA MILITAR*
*CPChq*
*1° BATALHÃO DE POLICIA DE CHOQUE*
*Previsão do dia 11/04/2026*
```

Regex confiavel para split: `r"(?=(?:^|\n)\*?DADOS\s+PARA\s+PLANILHA)"` (lookahead para manter o marcador no segmento).

---

## Etapa 1 — Backend: segmentar e parsear

### Arquivo: `app/services/whatsapp_parser.py`

**Funcao atual:**
```python
def parse_texto_whatsapp(texto: str) -> ParseResult:
    cabecalho, avisos = parse_cabecalho(texto)
    fracoes = parse_fracoes(texto)
    return ParseResult(cabecalho=cabecalho, fracoes=fracoes, avisos=avisos)
```

**Mudanca:** Retorno passa a ter `cabecalhos` (lista) ao inves de `cabecalho` (dict). Manter retrocompat: se N=1, `cabecalhos` tem 1 item.

```python
class ParseResult(TypedDict):
    cabecalhos: list[CabecalhoRow]   # era "cabecalho: CabecalhoRow"
    fracoes: list[FracaoRow]
    avisos: list[str]
```

Nova funcao `_segmentar_texto(texto)`:
- Split por lookahead do marcador "DADOS PARA PLANILHA"
- Retorna lista de strings (1 por unidade)
- Se nao encontra marcador, retorna `[texto]` (caso 1 unidade sem header)

Nova logica em `parse_texto_whatsapp`:
```python
def parse_texto_whatsapp(texto: str) -> ParseResult:
    segmentos = _segmentar_texto(texto)
    cabecalhos, todas_fracoes, avisos = [], [], []
    for seg in segmentos:
        cab, av = parse_cabecalho(seg)
        fracoes = parse_fracoes(seg)
        cabecalhos.append(cab)
        todas_fracoes.extend(fracoes)
        avisos.extend(av)
    if not todas_fracoes:
        avisos.append("Nenhuma fracao identificada")
    return ParseResult(cabecalhos=cabecalhos, fracoes=todas_fracoes, avisos=avisos)
```

**IMPORTANTE:** `parse_cabecalho` e `parse_fracoes` ja existem e funcionam para 1 unidade. NAO modificar essas funcoes — so chamar N vezes. O loop do bloco numerico em `parse_cabecalho` ja tem um `break` no marcador de segunda unidade (remover esse break, pois cada segmento agora contem so 1 unidade).

---

## Etapa 2 — API: adaptar endpoints

### Arquivo: `app/routes/api.py`

**`POST /api/parse-texto`** (linha 94-120):
- Muda `cabecalho` para `cabecalhos` no response:
```python
resultado = parse_texto_whatsapp(texto)
fracoes = [dict(f) for f in resultado["fracoes"]]
cabecalhos = [dict(c) for c in resultado["cabecalhos"]]

return jsonify({
    "sucesso": True,
    "fracoes": fracoes,
    "cabecalhos": cabecalhos,
    "avisos": resultado["avisos"],
    "total_fracoes": len(fracoes),
    "total_cabecalhos": len(cabecalhos),
}), 200
```

**`POST /api/salvar-texto`** (linha 123-162):
- Recebe `cabecalhos` (lista) ao inves de `cabecalho` (dict):
```python
cabecalhos_raw = body.get("cabecalhos", [])
# ...
cabecalho = validate_cabecalho(cabecalhos_raw)
```
- Resto do fluxo (save_fracoes, save_cabecalho) ja aceita listas.

---

## Etapa 3 — Frontend: preview multi-unidade

### Arquivo: `app/static/js/operador.js`

**Estado:** mudar `previewCabecalho` (objeto) para `previewCabecalhos` (array):
```javascript
var previewCabecalhos = [];  // era: var previewCabecalho = null;
```

**Receber resposta** (btn-interpretar handler, linha 107-108):
```javascript
previewCabecalhos = result.data.cabecalhos;
previewFracoes = result.data.fracoes;
```

**`montarPreview(avisos)`** — renderizar N cabecalhos:
```javascript
function montarPreview(avisos) {
  // Avisos (sem mudanca)
  // ...

  // Cabecalhos — 1 bloco por unidade
  var cabContainer = document.getElementById('preview-cabecalho');
  cabContainer.innerHTML = '';
  previewCabecalhos.forEach(function (cab, idx) {
    var wrapper = document.createElement('div');
    wrapper.className = 'cabecalho-unidade';
    wrapper.setAttribute('data-cab-idx', idx);
    if (previewCabecalhos.length > 1) {
      var title = document.createElement('h4');
      title.textContent = cab.unidade || ('Unidade ' + (idx + 1));
      wrapper.appendChild(title);
    }
    var grid = document.createElement('div');
    grid.className = 'preview-grid';
    CAMPOS_CABECALHO.forEach(function (c) {
      grid.appendChild(criarCampo(c, cab[c.key]));
    });
    wrapper.appendChild(grid);
    cabContainer.appendChild(wrapper);
  });

  renderizarPreviewFracoes();
}
```

**`coletarPreview()`** — coletar N cabecalhos:
```javascript
function coletarPreview() {
  var cabecalhos = [];
  document.querySelectorAll('.cabecalho-unidade').forEach(function (wrapper) {
    var cab = {};
    wrapper.querySelectorAll('input').forEach(function (inp) {
      var key = inp.getAttribute('data-key');
      cab[key] = inp.type === 'number' ? parseInt(inp.value, 10) || 0 : inp.value;
    });
    var idx = parseInt(wrapper.getAttribute('data-cab-idx'), 10);
    var orig = previewCabecalhos[idx] || {};
    cab.operador_diurno = orig.operador_diurno || '';
    cab.tel_op_diurno = orig.tel_op_diurno || '';
    cab.horario_op_diurno = orig.horario_op_diurno || '';
    cab.operador_noturno = orig.operador_noturno || '';
    cab.tel_op_noturno = orig.tel_op_noturno || '';
    cab.horario_op_noturno = orig.horario_op_noturno || '';
    cabecalhos.push(cab);
  });

  var fracoes = [];
  document.querySelectorAll('.fracao-form').forEach(function (form) {
    var f = {};
    form.querySelectorAll('input').forEach(function (inp) {
      var key = inp.getAttribute('data-key');
      f[key] = inp.type === 'number' ? parseInt(inp.value, 10) || 0 : inp.value;
    });
    fracoes.push(f);
  });

  return { cabecalhos: cabecalhos, fracoes: fracoes };
}
```

**btn-confirmar** (linha 288): mudar `dados.cabecalho` para `dados.cabecalhos` no body do fetch.

**btn-add-fracao**: usar `previewCabecalhos[0]` ao inves de `previewCabecalho`.

### Arquivo: `app/templates/operador/index.html`

- Mudar `<h3>Cabecalho</h3>` para `<h3>Cabecalhos</h3>` (linha 50)
- O container `preview-cabecalho` continua — agora recebe N blocos via JS

---

## Etapa 4 — Testes

1. Adaptar `tests/test_api_fase4.py` se algum teste usa `/parse-texto` — mudar `cabecalho` para `cabecalhos[0]`
2. Novo teste: colar texto com 2+ unidades → verificar que `len(cabecalhos) == N` e fracoes tem unidades distintas
3. Teste regressao: colar texto de 1 unidade → `len(cabecalhos) == 1`, mesmo comportamento

---

## Dados de teste

Arquivo `smos.md` na raiz contem o texto real do dia 15/04 com 7 unidades (1°-6°BPChq + 4°RPMon). Usar como fixture para teste multi-unidade.

## Regras

- NAO criar arquivos novos
- NAO modificar `parse_cabecalho()` nem `parse_fracoes()` — so chamar N vezes
- Remover o `break` por "DADOS PARA PLANILHA" que foi adicionado em `parse_cabecalho` (cada segmento ja contem so 1 unidade)
- Manter `max 500 LOC` por arquivo
- Rodar `pytest` ao final — 100 testes existentes devem passar
