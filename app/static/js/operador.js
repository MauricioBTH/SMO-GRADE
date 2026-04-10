/**
 * Modulo principal do operador — upload, seletor de unidades, integracao.
 */
(function () {
  'use strict';

  var dadosFracoes = [];
  var dadosCabecalho = [];
  var unidadeAtiva = null;

  /** Recalcula layout ao redimensionar */
  window.addEventListener('resize', function () {
    if (unidadeAtiva) {
      renderizarCards(unidadeAtiva, dadosFracoes, dadosCabecalho);
    }
  });

  /** Upload via API */
  document.getElementById('file-input').addEventListener('change', function (e) {
    var file = e.target.files[0];
    if (!file) return;

    var statusEl = document.getElementById('upload-status');
    statusEl.className = 'upload-status loading';
    statusEl.textContent = 'Processando...';

    var formData = new FormData();
    formData.append('file', file);

    fetch('/api/upload', {
      method: 'POST',
      body: formData,
    })
      .then(function (resp) {
        return resp.json().then(function (data) {
          return { ok: resp.ok, data: data };
        });
      })
      .then(function (result) {
        if (!result.ok) {
          throw new Error(result.data.erro || 'Erro desconhecido');
        }

        dadosFracoes = result.data.fracoes;
        dadosCabecalho = result.data.cabecalho;

        if (dadosFracoes.length === 0) {
          throw new Error('Nenhum dado encontrado na aba "fracoes".');
        }

        var salvoMsg = result.data.salvo_no_banco
          ? ' | Salvo no banco'
          : ' | Modo offline';

        statusEl.className = 'upload-status success';
        statusEl.textContent = result.data.total_fracoes + ' fracoes carregadas' + salvoMsg;

        var unidades = [];
        var seen = {};
        dadosFracoes.forEach(function (f) {
          if (!seen[f.unidade]) {
            seen[f.unidade] = true;
            unidades.push(f.unidade);
          }
        });

        montarSeletorUnidades(unidades);

        document.getElementById('upload-screen').style.display = 'none';
        document.getElementById('panel-screen').style.display = 'block';

        selecionarUnidade(unidades[0]);
      })
      .catch(function (err) {
        statusEl.className = 'upload-status error';
        statusEl.textContent = 'Erro: ' + err.message;
      });
  });

  /** Monta botoes de selecao de unidade */
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

  /** Seleciona unidade e renderiza cards */
  function selecionarUnidade(unidade) {
    unidadeAtiva = unidade;

    document.querySelectorAll('.unit-btn').forEach(function (btn) {
      btn.classList.toggle('active', btn.textContent === unidade);
    });

    renderizarCards(unidade, dadosFracoes, dadosCabecalho);

    document.getElementById('btn-gerar-wrapper').style.display = 'flex';
  }

  /** Expoe gerarImagens no botao */
  document.getElementById('btn-gerar').addEventListener('click', function () {
    gerarImagens();
  });
})();
