/**
 * Modulo principal do operador — upload, WhatsApp texto, preview, seletor de unidades.
 */
(function () {
  'use strict';

  var dadosFracoes = [];
  var dadosCabecalho = [];
  var unidadeAtiva = null;

  // Estado do preview
  var previewCabecalhos = [];
  var previewFracoes = [];

  /** Recalcula layout ao redimensionar */
  window.addEventListener('resize', function () {
    if (unidadeAtiva) {
      renderizarCards(unidadeAtiva, dadosFracoes, dadosCabecalho);
    }
  });

  // ---------- TELAS ----------

  function mostrarTela(id) {
    ['upload-screen', 'whatsapp-screen', 'preview-screen', 'panel-screen'].forEach(function (s) {
      var el = document.getElementById(s);
      if (el) el.style.display = s === id ? (s === 'panel-screen' ? 'block' : 'flex') : 'none';
    });
    document.getElementById('btn-gerar-wrapper').style.display =
      id === 'panel-screen' && unidadeAtiva ? 'flex' : 'none';
  }

  // ---------- UPLOAD XLSX ----------

  document.getElementById('file-input').addEventListener('change', function (e) {
    var file = e.target.files[0];
    if (!file) return;
    e.target.value = '';

    var statusEl = document.getElementById('upload-status');
    statusEl.className = 'upload-status loading';
    statusEl.textContent = 'Processando...';

    var formData = new FormData();
    formData.append('file', file);

    fetch('/api/upload', { method: 'POST', body: formData })
      .then(function (resp) {
        return resp.json().then(function (data) { return { ok: resp.ok, data: data }; });
      })
      .then(function (result) {
        if (!result.ok) throw new Error(result.data.erro || 'Erro desconhecido');

        dadosFracoes = result.data.fracoes;
        dadosCabecalho = result.data.cabecalho;

        if (dadosFracoes.length === 0) throw new Error('Nenhum dado encontrado na aba "fracoes".');

        var salvoMsg = result.data.salvo_no_banco ? ' | Salvo no banco' : ' | Modo offline';
        statusEl.className = 'upload-status success';
        statusEl.textContent = result.data.total_fracoes + ' fracoes carregadas' + salvoMsg;

        irParaPainel();
      })
      .catch(function (err) {
        statusEl.className = 'upload-status error';
        statusEl.textContent = 'Erro: ' + err.message;
      });
  });

  // ---------- WHATSAPP TEXTO ----------

  document.getElementById('btn-whatsapp').addEventListener('click', function () {
    mostrarTela('whatsapp-screen');
    document.getElementById('whatsapp-texto').value = '';
    document.getElementById('whatsapp-status').className = 'upload-status';
    document.getElementById('whatsapp-status').textContent = '';
  });

  document.getElementById('btn-voltar-upload').addEventListener('click', function () {
    mostrarTela('upload-screen');
  });

  document.getElementById('btn-interpretar').addEventListener('click', function () {
    var texto = document.getElementById('whatsapp-texto').value.trim();
    if (!texto) return;

    var statusEl = document.getElementById('whatsapp-status');
    statusEl.className = 'upload-status loading';
    statusEl.textContent = 'Interpretando...';

    fetch('/api/parse-texto', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ texto: texto }),
    })
      .then(function (resp) {
        return resp.json().then(function (data) { return { ok: resp.ok, data: data }; });
      })
      .then(function (result) {
        if (!result.ok) throw new Error(result.data.erro || 'Erro desconhecido');

        if (result.data.total_fracoes === 0) {
          throw new Error('Nenhuma fracao identificada no texto.');
        }

        previewCabecalhos = result.data.cabecalhos;
        previewFracoes = result.data.fracoes;

        statusEl.className = 'upload-status success';
        var cabMsg = result.data.total_cabecalhos > 1
          ? result.data.total_cabecalhos + ' unidades, ' : '';
        statusEl.textContent = cabMsg + result.data.total_fracoes + ' fracoes identificadas';

        montarPreview(result.data.avisos);
        mostrarTela('preview-screen');
      })
      .catch(function (err) {
        statusEl.className = 'upload-status error';
        statusEl.textContent = 'Erro: ' + err.message;
      });
  });

  // ---------- PREVIEW EDITAVEL ----------

  var CAMPOS_CABECALHO = [
    { key: 'unidade', label: 'Unidade' },
    { key: 'data', label: 'Data' },
    { key: 'horario_emprego', label: 'Horario Emprego' },
    { key: 'turno', label: 'Turno' },
    { key: 'oficial_superior', label: 'Of. Superior' },
    { key: 'tel_oficial', label: 'Tel Of.' },
    { key: 'tel_copom', label: 'Tel COPOM' },
    { key: 'efetivo_total', label: 'Ef. Total', tipo: 'number' },
    { key: 'oficiais', label: 'Oficiais', tipo: 'number' },
    { key: 'sargentos', label: 'Sargentos', tipo: 'number' },
    { key: 'soldados', label: 'Soldados', tipo: 'number' },
    { key: 'vtrs', label: 'VTRs', tipo: 'number' },
    { key: 'motos', label: 'Motos', tipo: 'number' },
    { key: 'ef_motorizado', label: 'Ef. Motorizado', tipo: 'number' },
    { key: 'armas_ace', label: 'ACE', tipo: 'number' },
    { key: 'armas_portateis', label: 'Portateis', tipo: 'number' },
    { key: 'armas_longas', label: 'Longas', tipo: 'number' },
    { key: 'animais', label: 'Animais', tipo: 'number' },
    { key: 'animais_tipo', label: 'Tipo Animal' },
    { key: 'locais_atuacao', label: 'Locais', wide: true },
    { key: 'missoes_osv', label: 'Missoes/OSV', wide: true },
  ];

  var CAMPOS_FRACAO = [
    { key: 'fracao', label: 'Fracao' },
    { key: 'comandante', label: 'Comandante' },
    { key: 'telefone', label: 'Telefone' },
    { key: 'equipes', label: 'Equipes', tipo: 'number' },
    { key: 'pms', label: 'PMs', tipo: 'number' },
    { key: 'horario_inicio', label: 'Inicio' },
    { key: 'horario_fim', label: 'Fim' },
    { key: 'missao', label: 'Missao' },
  ];

  function criarCampo(campo, valor) {
    var div = document.createElement('div');
    div.className = 'preview-field' + (campo.wide ? ' preview-field-wide' : '');
    var lbl = document.createElement('label');
    lbl.textContent = campo.label;
    var inp = document.createElement('input');
    inp.type = campo.tipo || 'text';
    inp.value = valor != null ? valor : '';
    inp.setAttribute('data-key', campo.key);
    div.appendChild(lbl);
    div.appendChild(inp);
    return div;
  }

  var previewTabAtiva = 0;

  function montarPreview(avisos) {
    // Avisos
    var avisosEl = document.getElementById('preview-avisos');
    avisosEl.innerHTML = '';
    if (avisos && avisos.length) {
      avisos.forEach(function (a) {
        var d = document.createElement('div');
        d.className = 'aviso-item';
        d.textContent = a;
        avisosEl.appendChild(d);
      });
    }

    // Tabs
    var tabsEl = document.getElementById('preview-tabs');
    tabsEl.innerHTML = '';
    previewCabecalhos.forEach(function (cab, idx) {
      var btn = document.createElement('button');
      btn.className = 'unit-btn';
      btn.textContent = cab.unidade || ('Unidade ' + (idx + 1));
      btn.addEventListener('click', function () { selecionarPreviewTab(idx); });
      tabsEl.appendChild(btn);
    });

    previewTabAtiva = 0;
    renderizarPreviewTab(0);
  }

  function salvarTabAtual() {
    var container = document.getElementById('preview-tab-content');
    if (!container.children.length) return;

    var wrapper = container.querySelector('.cabecalho-unidade');
    if (wrapper) {
      var cabIdx = parseInt(wrapper.getAttribute('data-cab-idx'), 10);
      var cab = previewCabecalhos[cabIdx];
      if (cab) {
        wrapper.querySelectorAll('input').forEach(function (inp) {
          var key = inp.getAttribute('data-key');
          cab[key] = inp.type === 'number' ? parseInt(inp.value, 10) || 0 : inp.value;
        });
      }
    }

    container.querySelectorAll('.fracao-form').forEach(function (form) {
      var fIdx = parseInt(form.getAttribute('data-fracao-idx'), 10);
      var f = previewFracoes[fIdx];
      if (f) {
        form.querySelectorAll('input').forEach(function (inp) {
          var key = inp.getAttribute('data-key');
          f[key] = inp.type === 'number' ? parseInt(inp.value, 10) || 0 : inp.value;
        });
      }
    });
  }

  function selecionarPreviewTab(idx) {
    salvarTabAtual();
    previewTabAtiva = idx;
    renderizarPreviewTab(idx);
  }

  function renderizarPreviewTab(idx) {
    // Atualizar botoes
    var btns = document.querySelectorAll('#preview-tabs .unit-btn');
    btns.forEach(function (b, i) { b.classList.toggle('active', i === idx); });

    var container = document.getElementById('preview-tab-content');
    container.innerHTML = '';

    var cab = previewCabecalhos[idx];
    if (!cab) return;
    var unidade = cab.unidade || '';

    // Cabecalho
    var secCab = document.createElement('div');
    secCab.className = 'preview-section';
    var hCab = document.createElement('h3');
    hCab.textContent = 'Cabecalho';
    secCab.appendChild(hCab);

    var wrapper = document.createElement('div');
    wrapper.className = 'cabecalho-unidade';
    wrapper.setAttribute('data-cab-idx', idx);
    var grid = document.createElement('div');
    grid.className = 'preview-grid';
    CAMPOS_CABECALHO.forEach(function (c) {
      grid.appendChild(criarCampo(c, cab[c.key]));
    });
    wrapper.appendChild(grid);
    secCab.appendChild(wrapper);
    container.appendChild(secCab);

    // Fracoes da unidade
    var secFrac = document.createElement('div');
    secFrac.className = 'preview-section';
    var hFrac = document.createElement('h3');
    hFrac.textContent = 'Fracoes ';
    var btnAdd = document.createElement('button');
    btnAdd.className = 'btn-mini';
    btnAdd.textContent = '+ Adicionar';
    btnAdd.addEventListener('click', function () {
      previewFracoes.push({
        unidade: unidade, data: cab.data || '', turno: cab.turno || '',
        fracao: '', comandante: '', telefone: '',
        equipes: 0, pms: 0, horario_inicio: '', horario_fim: '', missao: '',
      });
      renderizarPreviewTab(previewTabAtiva);
    });
    hFrac.appendChild(btnAdd);
    secFrac.appendChild(hFrac);

    var numFrac = 0;
    previewFracoes.forEach(function (f, fIdx) {
      if (f.unidade !== unidade) return;
      numFrac++;

      var form = document.createElement('div');
      form.className = 'fracao-form';
      form.setAttribute('data-fracao-idx', fIdx);

      var header = document.createElement('div');
      header.className = 'fracao-form-header';
      var title = document.createElement('span');
      title.className = 'fracao-form-title';
      title.textContent = 'Fracao ' + numFrac + (f.fracao ? ' — ' + f.fracao : '');
      var btnRem = document.createElement('button');
      btnRem.className = 'btn-remover';
      btnRem.textContent = 'Remover';
      (function (removeIdx) {
        btnRem.addEventListener('click', function () {
          previewFracoes.splice(removeIdx, 1);
          renderizarPreviewTab(previewTabAtiva);
        });
      })(fIdx);
      header.appendChild(title);
      header.appendChild(btnRem);
      form.appendChild(header);

      var fGrid = document.createElement('div');
      fGrid.className = 'preview-grid';
      CAMPOS_FRACAO.forEach(function (c) {
        fGrid.appendChild(criarCampo(c, f[c.key]));
      });
      form.appendChild(fGrid);
      secFrac.appendChild(form);
    });

    container.appendChild(secFrac);
  }

  document.getElementById('btn-voltar-texto').addEventListener('click', function () {
    mostrarTela('whatsapp-screen');
  });

  function coletarPreview() {
    salvarTabAtual();

    var cabecalhos = previewCabecalhos.map(function (cab) {
      var c = {};
      CAMPOS_CABECALHO.forEach(function (campo) { c[campo.key] = cab[campo.key]; });
      c.operador_diurno = cab.operador_diurno || '';
      c.tel_op_diurno = cab.tel_op_diurno || '';
      c.horario_op_diurno = cab.horario_op_diurno || '';
      c.operador_noturno = cab.operador_noturno || '';
      c.tel_op_noturno = cab.tel_op_noturno || '';
      c.horario_op_noturno = cab.horario_op_noturno || '';
      return c;
    });

    var fracoes = previewFracoes.map(function (f) {
      var out = { unidade: f.unidade || '', data: f.data || '', turno: f.turno || '' };
      CAMPOS_FRACAO.forEach(function (campo) { out[campo.key] = f[campo.key]; });
      return out;
    });

    return { cabecalhos: cabecalhos, fracoes: fracoes };
  }

  var btnConfirmar = document.getElementById('btn-confirmar');
  var btnConfirmarTexto = btnConfirmar.textContent;
  var modalOverlay = document.getElementById('modal-overlay');
  var modalBtnOk = document.getElementById('modal-confirmar');
  var modalBtnCancel = document.getElementById('modal-cancelar');

  function fecharModal() { modalOverlay.classList.remove('active'); }

  btnConfirmar.addEventListener('click', function () {
    modalOverlay.classList.add('active');
  });

  modalBtnCancel.addEventListener('click', fecharModal);
  modalOverlay.addEventListener('click', function (e) {
    if (e.target === modalOverlay) fecharModal();
  });

  modalBtnOk.addEventListener('click', function () {
    fecharModal();
    var dados = coletarPreview();

    btnConfirmar.disabled = true;
    btnConfirmar.textContent = 'Salvando...';
    btnConfirmar.classList.add('btn-loading');

    fetch('/api/salvar-texto', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(dados),
    })
      .then(function (resp) {
        return resp.json().then(function (data) { return { ok: resp.ok, data: data }; });
      })
      .then(function (result) {
        if (!result.ok) throw new Error(result.data.erro || 'Erro desconhecido');

        dadosFracoes = result.data.fracoes;
        dadosCabecalho = result.data.cabecalho;

        btnConfirmar.textContent = 'Salvo!';
        btnConfirmar.classList.remove('btn-loading');
        btnConfirmar.classList.add('btn-success');

        setTimeout(function () { irParaPainel(); }, 600);
      })
      .catch(function (err) {
        btnConfirmar.textContent = btnConfirmarTexto;
        btnConfirmar.disabled = false;
        btnConfirmar.classList.remove('btn-loading');
        btnConfirmar.classList.add('btn-error');
        setTimeout(function () { btnConfirmar.classList.remove('btn-error'); }, 2000);
      });
  });

  // ---------- PAINEL ----------

  function irParaPainel() {
    var unidades = [];
    var seen = {};
    dadosFracoes.forEach(function (f) {
      if (!seen[f.unidade]) {
        seen[f.unidade] = true;
        unidades.push(f.unidade);
      }
    });

    montarSeletorUnidades(unidades);
    mostrarTela('panel-screen');
    selecionarUnidade(unidades[0]);
  }

  function montarSeletorUnidades(unidades) {
    var container = document.getElementById('unit-selector');
    container.innerHTML = '';
    unidades.forEach(function (u) {
      var btn = document.createElement('button');
      btn.className = 'unit-btn';
      btn.textContent = u;
      btn.addEventListener('click', function () { selecionarUnidade(u); });
      container.appendChild(btn);
    });
  }

  function selecionarUnidade(unidade) {
    unidadeAtiva = unidade;

    document.querySelectorAll('.unit-btn').forEach(function (btn) {
      btn.classList.toggle('active', btn.textContent === unidade);
    });

    renderizarCards(unidade, dadosFracoes, dadosCabecalho);
    document.getElementById('btn-gerar-wrapper').style.display = 'flex';
  }

  document.getElementById('btn-gerar').addEventListener('click', function () {
    gerarImagens();
  });
})();
