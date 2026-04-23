/**
 * Renderizacao/coleta dos vertices N:N no preview (Fase 6.3).
 *
 * Exposto como window.PreviewMissoes para o operador.js manter-se enxuto.
 * Toda logica de validacao (municipio obrigatorio, BPM em POA) continua no
 * backend — aqui so renderizamos dropdowns e coletamos o que o usuario escolheu.
 */
(function () {
  'use strict';

  var cacheMunicipios = null;  // [{id, nome, crpm_sigla}]
  var cacheBpms = null;        // [{id, codigo, numero, municipio_id}]
  var SIGLA_POA = 'CPC';

  function fetchJson(url) {
    return fetch(url).then(function (r) {
      return r.json().then(function (d) {
        if (!r.ok) throw new Error(d.erro || url);
        return d;
      });
    });
  }

  function carregarCatalogos() {
    if (cacheMunicipios && cacheBpms) return Promise.resolve();
    return Promise.all([
      fetchJson('/api/catalogos/municipios?q=').then(function (d) {
        cacheMunicipios = d.municipios || [];
      }).catch(function () { cacheMunicipios = []; }),
      fetchJson('/api/catalogos/bpms').then(function (d) {
        cacheBpms = d.bpms || [];
      }).catch(function () { cacheBpms = []; }),
    ]);
  }

  function municipioPorId(id) {
    if (!id || !cacheMunicipios) return null;
    for (var i = 0; i < cacheMunicipios.length; i++) {
      if (cacheMunicipios[i].id === id) return cacheMunicipios[i];
    }
    return null;
  }

  function rotuloMunicipio(m) {
    return m.nome + ' (' + m.crpm_sigla + ')';
  }

  function normalizarTexto(s) {
    return (s || '')
      .toString()
      .normalize('NFD')
      .replace(/\p{M}/gu, '')
      .toLowerCase()
      .trim();
  }

  function filtrarMunicipios(q) {
    var termo = normalizarTexto(q);
    var base = cacheMunicipios || [];
    if (!termo) return base.slice(0, 50);
    return base.filter(function (m) {
      return normalizarTexto(rotuloMunicipio(m)).indexOf(termo) !== -1;
    }).slice(0, 50);
  }

  function ehPoa(muniId) {
    var m = municipioPorId(muniId);
    return !!(m && (m.crpm_sigla || '').toUpperCase() === SIGLA_POA);
  }

  function criarComboboxMunicipio(atual) {
    var wrap = document.createElement('div');
    wrap.className = 'municipio-combo';

    var inp = document.createElement('input');
    inp.type = 'text';
    inp.className = 'municipio-combo-input';
    inp.setAttribute('data-key', 'municipio_id');
    inp.setAttribute('autocomplete', 'off');
    inp.setAttribute('spellcheck', 'false');
    inp.placeholder = 'Buscar municipio...';

    var lista = document.createElement('ul');
    lista.className = 'municipio-combo-list';
    lista.setAttribute('role', 'listbox');

    var m = municipioPorId(atual);
    if (m) {
      inp.value = rotuloMunicipio(m);
      inp.dataset.municipioId = m.id;
    } else {
      inp.dataset.municipioId = '';
    }

    function abrir() {
      renderizarLista(inp.value);
      lista.classList.add('aberta');
    }

    function fechar() {
      lista.classList.remove('aberta');
    }

    function renderizarLista(q) {
      lista.innerHTML = '';
      var itens = filtrarMunicipios(q);
      if (!itens.length) {
        var vazio = document.createElement('li');
        vazio.className = 'municipio-combo-vazio';
        vazio.textContent = 'Nenhum municipio';
        lista.appendChild(vazio);
        return;
      }
      itens.forEach(function (mi) {
        var li = document.createElement('li');
        li.className = 'municipio-combo-item';
        li.setAttribute('role', 'option');
        li.dataset.id = mi.id;
        li.textContent = rotuloMunicipio(mi);
        // mousedown antes do blur do input → garante que selecao acontece
        li.addEventListener('mousedown', function (ev) {
          ev.preventDefault();
          selecionar(mi);
        });
        lista.appendChild(li);
      });
    }

    function selecionar(mi) {
      inp.value = rotuloMunicipio(mi);
      inp.dataset.municipioId = mi.id;
      fechar();
      inp.dispatchEvent(new Event('change', { bubbles: true }));
    }

    inp.addEventListener('focus', abrir);
    inp.addEventListener('input', function () {
      // qualquer digitacao invalida a selecao anterior
      inp.dataset.municipioId = '';
      abrir();
      inp.dispatchEvent(new Event('change', { bubbles: true }));
    });
    inp.addEventListener('blur', function () {
      // pequena espera para permitir clique no item (mousedown ja previne, mas
      // defensivo caso browser trate eventos em ordem diferente)
      setTimeout(fechar, 120);
    });
    inp.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') { fechar(); return; }
      if (ev.key === 'Enter') {
        var primeiro = lista.querySelector('.municipio-combo-item');
        if (primeiro) {
          ev.preventDefault();
          var id = primeiro.dataset.id;
          var alvo = municipioPorId(id);
          if (alvo) selecionar(alvo);
        }
      }
    });

    wrap.appendChild(inp);
    wrap.appendChild(lista);
    return wrap;
  }

  function bpmPorId(id) {
    if (!id || !cacheBpms) return null;
    for (var i = 0; i < cacheBpms.length; i++) {
      if (cacheBpms[i].id === id) return cacheBpms[i];
    }
    return null;
  }

  function bpmsDoMunicipio(muniId) {
    return (cacheBpms || []).filter(function (b) {
      return !muniId || b.municipio_id === muniId;
    });
  }

  /**
   * Chip-picker multisselecao de BPMs (Fase 6.4).
   *
   * Substitui o select 1:1 por chips removiveis + input filtravel. O wrapper
   * mantem a lista atual em `wrap.bpmIds` (array de strings) — `coletarVertices`
   * le daqui. `disabled` desabilita input e botoes de remover (em_quartel ou
   * municipio fora de POA).
   */
  function criarChipPickerBpm(idsAtuais, muniId, disabled) {
    var wrap = document.createElement('div');
    wrap.className = 'bpm-chips';
    wrap.setAttribute('data-key', 'bpm_ids');
    wrap.bpmIds = (idsAtuais || []).slice();
    if (disabled) wrap.classList.add('desabilitado');

    var chipsWrap = document.createElement('div');
    chipsWrap.className = 'bpm-chips-selected';
    wrap.appendChild(chipsWrap);

    var inp = document.createElement('input');
    inp.type = 'text';
    inp.className = 'bpm-picker-input';
    inp.setAttribute('autocomplete', 'off');
    inp.setAttribute('spellcheck', 'false');
    inp.placeholder = disabled ? '' : 'Adicionar BPM...';
    inp.disabled = !!disabled;
    wrap.appendChild(inp);

    var lista = document.createElement('ul');
    lista.className = 'bpm-picker-list';
    lista.setAttribute('role', 'listbox');
    wrap.appendChild(lista);

    function renderChips() {
      chipsWrap.innerHTML = '';
      wrap.bpmIds.forEach(function (id) {
        var b = bpmPorId(id);
        if (!b) return;
        var chip = document.createElement('span');
        chip.className = 'bpm-chip';
        chip.textContent = b.codigo;
        if (!disabled) {
          var x = document.createElement('button');
          x.type = 'button';
          x.className = 'bpm-chip-remover';
          x.setAttribute('aria-label', 'Remover ' + b.codigo);
          x.textContent = '×';
          x.addEventListener('click', function () {
            wrap.bpmIds = wrap.bpmIds.filter(function (i) { return i !== id; });
            renderChips();
            wrap.dispatchEvent(new Event('change', { bubbles: true }));
          });
          chip.appendChild(x);
        }
        chipsWrap.appendChild(chip);
      });
    }

    function abrir() {
      if (disabled) return;
      renderizarOpcoes(inp.value);
      lista.classList.add('aberta');
    }

    function fechar() {
      lista.classList.remove('aberta');
    }

    function renderizarOpcoes(q) {
      lista.innerHTML = '';
      var termo = normalizarTexto(q);
      var opcoes = bpmsDoMunicipio(muniId).filter(function (b) {
        if (wrap.bpmIds.indexOf(b.id) !== -1) return false;
        if (!termo) return true;
        return normalizarTexto(b.codigo).indexOf(termo) !== -1;
      });
      if (!opcoes.length) {
        var vazio = document.createElement('li');
        vazio.className = 'bpm-picker-vazio';
        vazio.textContent = wrap.bpmIds.length
          ? 'Nenhum BPM adicional'
          : 'Nenhum BPM disponivel';
        lista.appendChild(vazio);
        return;
      }
      opcoes.forEach(function (b) {
        var li = document.createElement('li');
        li.className = 'bpm-picker-item';
        li.setAttribute('role', 'option');
        li.dataset.id = b.id;
        li.textContent = b.codigo;
        li.addEventListener('mousedown', function (ev) {
          ev.preventDefault();
          selecionar(b);
        });
        lista.appendChild(li);
      });
    }

    function selecionar(b) {
      if (wrap.bpmIds.indexOf(b.id) === -1) {
        wrap.bpmIds.push(b.id);
      }
      inp.value = '';
      renderChips();
      renderizarOpcoes('');
      wrap.dispatchEvent(new Event('change', { bubbles: true }));
    }

    inp.addEventListener('focus', abrir);
    inp.addEventListener('input', function () { abrir(); });
    inp.addEventListener('blur', function () { setTimeout(fechar, 120); });
    inp.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') { fechar(); return; }
      if (ev.key === 'Enter') {
        var primeiro = lista.querySelector('.bpm-picker-item');
        if (primeiro) {
          ev.preventDefault();
          var alvo = bpmPorId(primeiro.dataset.id);
          if (alvo) selecionar(alvo);
        }
      }
    });

    renderChips();
    return wrap;
  }

  function criarInputTexto(key, valor, placeholder) {
    var inp = document.createElement('input');
    inp.type = 'text';
    inp.setAttribute('data-key', key);
    inp.value = valor == null ? '' : valor;
    if (placeholder) inp.placeholder = placeholder;
    return inp;
  }

  var ICON_TRASH = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
    + '<path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m2 0v14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V6"/>'
    + '<path d="M10 11v6M14 11v6"/>'
    + '</svg>';
  var ICON_PLUS = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
    + '<path d="M12 5v14M5 12h14"/>'
    + '</svg>';

  function criarBotaoIcone(className, svg, titulo, onClick) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = className;
    b.title = titulo;
    b.setAttribute('aria-label', titulo);
    b.innerHTML = svg;
    if (onClick) b.addEventListener('click', onClick);
    return b;
  }

  function criarBotaoRemover(titulo, onClick) {
    return criarBotaoIcone('btn-remover', ICON_TRASH, titulo, onClick);
  }

  function criarBotaoAdicionar(titulo, onClick) {
    return criarBotaoIcone('btn-adicionar', ICON_PLUS, titulo, onClick);
  }

  function fieldWrap(labelText, extraClass) {
    var wrap = document.createElement('div');
    wrap.className = 'preview-field' + (extraClass ? ' ' + extraClass : '');
    var lbl = document.createElement('label');
    lbl.textContent = labelText;
    wrap.appendChild(lbl);
    return wrap;
  }

  function criarLinhaVertice(v, ordem, onChange, onRemove) {
    var row = document.createElement('div');
    row.className = 'missao-vertice';
    row.setAttribute('data-ordem', ordem);

    var fMissao = fieldWrap('MISSAO ' + ordem, 'preview-field-wide');
    var missaoInp = criarInputTexto(
      'missao_nome_raw', v.missao_nome_raw, 'Nome da missao'
    );
    fMissao.appendChild(missaoInp);
    row.appendChild(fMissao);

    var fMuni = fieldWrap('MUNICIPIO');
    var muniCombo = criarComboboxMunicipio(v.municipio_id);
    var muniInp = muniCombo.querySelector('input[data-key="municipio_id"]');
    fMuni.appendChild(muniCombo);
    row.appendChild(fMuni);

    var fBpm = fieldWrap('BPM');
    var idsIniciais = Array.isArray(v.bpm_ids) ? v.bpm_ids
      : (v.bpm_id ? [v.bpm_id] : []);
    var bpmPicker = criarChipPickerBpm(
      idsIniciais, v.municipio_id, !!v.em_quartel || !ehPoa(v.municipio_id)
    );
    fBpm.appendChild(bpmPicker);
    row.appendChild(fBpm);

    var fQ = fieldWrap('EM QUARTEL', 'preview-field-check');
    var chk = document.createElement('input');
    chk.type = 'checkbox';
    chk.setAttribute('data-key', 'em_quartel');
    chk.checked = !!v.em_quartel;
    fQ.appendChild(chk);
    row.appendChild(fQ);

    var btnRem = criarBotaoRemover('Remover missao ' + ordem, onRemove);
    btnRem.classList.add('missao-vertice-remover');
    row.appendChild(btnRem);

    function sincronizarMunicipio() {
      var muniId = muniInp.dataset.municipioId || null;
      // Trocar de municipio zera BPMs (podem nao pertencer ao novo muni).
      var novoPicker = criarChipPickerBpm(
        [], muniId, chk.checked || !ehPoa(muniId)
      );
      fBpm.replaceChild(novoPicker, bpmPicker);
      bpmPicker = novoPicker;
      if (onChange) onChange();
    }
    muniInp.addEventListener('change', sincronizarMunicipio);
    chk.addEventListener('change', function () {
      var muniId = muniInp.dataset.municipioId || null;
      var disabled = chk.checked || !ehPoa(muniId);
      var idsPreservados = chk.checked ? [] : (bpmPicker.bpmIds || []);
      var novoPicker = criarChipPickerBpm(idsPreservados, muniId, disabled);
      fBpm.replaceChild(novoPicker, bpmPicker);
      bpmPicker = novoPicker;
    });

    return row;
  }

  function renderizarVertices(containerEl, fracao) {
    containerEl.innerHTML = '';
    var missoes = fracao.missoes || [];
    if (!missoes.length) {
      // Backcompat: deriva 1 vertice a partir dos campos legados
      missoes = [{
        ordem: 1,
        missao_nome_raw: fracao.missao || '',
        municipio_nome_raw: fracao.municipio_nome_raw || '',
        municipio_id: fracao.municipio_id || null,
        bpm_ids: [], em_quartel: false,
      }];
      fracao.missoes = missoes;
    }

    missoes.forEach(function (v, i) {
      var row = criarLinhaVertice(
        v, i + 1,
        function () { /* onChange: sem acao extra por enquanto */ },
        function () {
          fracao.missoes.splice(i, 1);
          renderizarVertices(containerEl, fracao);
        }
      );
      containerEl.appendChild(row);
    });

    var btnAdd = criarBotaoAdicionar('Adicionar missao', function () {
      fracao.missoes.push({
        ordem: fracao.missoes.length + 1,
        missao_nome_raw: '', municipio_nome_raw: '',
        municipio_id: null, bpm_ids: [], em_quartel: false,
      });
      renderizarVertices(containerEl, fracao);
    });
    btnAdd.classList.add('missao-add');
    containerEl.appendChild(btnAdd);
  }

  function coletarVertices(containerEl) {
    var out = [];
    var rows = containerEl.querySelectorAll('.missao-vertice');
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i];
      var missaoInp = row.querySelector('input[data-key="missao_nome_raw"]');
      var muniInp = row.querySelector('input[data-key="municipio_id"]');
      var bpmPicker = row.querySelector('[data-key="bpm_ids"]');
      var chk = row.querySelector('input[data-key="em_quartel"]');
      var muniId = muniInp ? (muniInp.dataset.municipioId || null) : null;
      var muniObj = municipioPorId(muniId);
      var textoDigitado = muniInp ? muniInp.value.trim() : '';
      var emQuartel = !!(chk && chk.checked);
      var ids = (bpmPicker && Array.isArray(bpmPicker.bpmIds))
        ? bpmPicker.bpmIds.slice() : [];
      out.push({
        ordem: i + 1,
        missao_nome_raw: missaoInp ? missaoInp.value : '',
        municipio_nome_raw: muniObj ? muniObj.nome : textoDigitado,
        municipio_id: muniId,
        bpm_ids: emQuartel ? [] : ids,
        em_quartel: emQuartel,
      });
    }
    return out;
  }

  window.PreviewMissoes = {
    carregarCatalogos: carregarCatalogos,
    renderizarVertices: renderizarVertices,
    coletarVertices: coletarVertices,
    criarBotaoRemover: criarBotaoRemover,
    criarBotaoAdicionar: criarBotaoAdicionar,
  };
})();
