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
    { key: 'locais_atuacao', label: 'Locais' },
    { key: 'missoes_osv', label: 'Missoes/OSV' },
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
    div.className = 'preview-field';
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

    // Fracoes
    renderizarPreviewFracoes();
  }

  function renderizarPreviewFracoes() {
    var container = document.getElementById('preview-fracoes');
    container.innerHTML = '';

    previewFracoes.forEach(function (f, idx) {
      var form = document.createElement('div');
      form.className = 'fracao-form';
      form.setAttribute('data-fracao-idx', idx);

      var header = document.createElement('div');
      header.className = 'fracao-form-header';
      var title = document.createElement('span');
      title.className = 'fracao-form-title';
      title.textContent = 'Fracao ' + (idx + 1) + (f.fracao ? ' — ' + f.fracao : '');
      var btnRem = document.createElement('button');
      btnRem.className = 'btn-remover';
      btnRem.textContent = 'Remover';
      btnRem.addEventListener('click', function () {
        previewFracoes.splice(idx, 1);
        renderizarPreviewFracoes();
      });
      header.appendChild(title);
      header.appendChild(btnRem);
      form.appendChild(header);

      var grid = document.createElement('div');
      grid.className = 'preview-grid';
      CAMPOS_FRACAO.forEach(function (c) {
        grid.appendChild(criarCampo(c, f[c.key]));
      });
      form.appendChild(grid);
      container.appendChild(form);
    });
  }

  document.getElementById('btn-add-fracao').addEventListener('click', function () {
    var base = previewFracoes.length > 0 ? previewFracoes[0]
             : previewCabecalhos.length > 0 ? previewCabecalhos[0] : {};
    previewFracoes.push({
      unidade: base.unidade || '',
      data: base.data || '',
      turno: base.turno || '',
      fracao: '',
      comandante: '',
      telefone: '',
      equipes: 0,
      pms: 0,
      horario_inicio: '',
      horario_fim: '',
      missao: '',
    });
    renderizarPreviewFracoes();
  });

  document.getElementById('btn-voltar-texto').addEventListener('click', function () {
    mostrarTela('whatsapp-screen');
  });

  function coletarPreview() {
    // Cabecalhos
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

    // Fracoes
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

  document.getElementById('btn-confirmar').addEventListener('click', function () {
    var dados = coletarPreview();
    var statusEl = document.getElementById('preview-status');
    statusEl.className = 'upload-status loading';
    statusEl.textContent = 'Salvando...';

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

        var salvoMsg = result.data.salvo_no_banco ? ' | Salvo no banco' : ' | Modo offline';
        statusEl.className = 'upload-status success';
        statusEl.textContent = result.data.total_fracoes + ' fracoes salvas' + salvoMsg;

        setTimeout(function () { irParaPainel(); }, 600);
      })
      .catch(function (err) {
        statusEl.className = 'upload-status error';
        statusEl.textContent = 'Erro: ' + err.message;
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
