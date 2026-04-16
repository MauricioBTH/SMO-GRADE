/** Cards Analiticos — Fase 3 */
(function () {
  'use strict';

  /* ---------- Cores por unidade ---------- */
  var CORES_UNIDADE = {
    '1 BPChq': '#F7B900', '1º BPChq': '#F7B900',
    '2 BPChq': '#E74C3C', '2º BPChq': '#E74C3C',
    '3 BPChq': '#3498DB', '3º BPChq': '#3498DB',
    '4 BPChq': '#2ECC71', '4º BPChq': '#2ECC71',
    '5 BPChq': '#9B59B6', '5º BPChq': '#9B59B6',
    '6 BPChq': '#E67E22', '6º BPChq': '#E67E22',
    '4 RPMon': '#1ABC9C', '4º RPMon': '#1ABC9C',
  };

  var METRICAS = [
    { chave: 'efetivo_total', label: 'Efetivo Total' },
    { chave: 'vtrs',          label: 'Viaturas' },
  ];

  /* ---------- Estado ---------- */
  var chartInstances = {};
  var dadosSerie = [];
  var dadosResumo = [];
  var metricaSelecionada = 'efetivo_total';

  /* ---------- Inicializacao (chamada pelo analista.js) ---------- */
  window.inicializarGraficos = function (serie, resumo) {
    dadosSerie = serie || [];
    dadosResumo = resumo || [];
    renderizarSeletorMetrica();
    renderizarSlideEvolucao();
    renderizarSlideComparativo();
  };

  /* ---------- Seletor de metrica ---------- */
  function renderizarSeletorMetrica() {
    var container = document.getElementById('grafico-seletor');
    if (!container) return;
    container.innerHTML = '';

    METRICAS.forEach(function (m) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'grafico-chip' + (m.chave === metricaSelecionada ? ' ativo' : '');
      btn.textContent = m.label;
      btn.addEventListener('click', function () {
        metricaSelecionada = m.chave;
        container.querySelectorAll('.grafico-chip').forEach(function (b) {
          b.classList.toggle('ativo', b.textContent === m.label);
        });
        renderizarSlideEvolucao();
        renderizarSlideComparativo();
      });
      container.appendChild(btn);
    });
  }

  /* ---------- Slide 1: Evolucao temporal (line chart) ---------- */
  function renderizarSlideEvolucao() {
    var canvas = document.getElementById('chart-evolucao');
    if (!canvas) return;

    if (chartInstances.evolucao) {
      chartInstances.evolucao.destroy();
    }

    var unidades = extrairUnidades(dadosSerie);
    var datas = extrairDatas(dadosSerie);
    var datasets = [];

    unidades.forEach(function (u) {
      var pontos = datas.map(function (d) {
        var registro = dadosSerie.find(function (r) {
          return r.unidade === u && r.data === d;
        });
        return registro ? (registro[metricaSelecionada] || 0) : 0;
      });
      datasets.push({
        label: u,
        data: pontos,
        borderColor: CORES_UNIDADE[u] || '#888',
        backgroundColor: (CORES_UNIDADE[u] || '#888') + '33',
        borderWidth: 2,
        pointRadius: datas.length > 30 ? 0 : 4,
        pointBackgroundColor: CORES_UNIDADE[u] || '#888',
        tension: 0.3,
        fill: false,
      });
    });

    var labelMetrica = METRICAS.find(function (m) {
      return m.chave === metricaSelecionada;
    });

    atualizarTitulo('slide-evolucao-titulo',
      'Evolucao — ' + (labelMetrica ? labelMetrica.label : metricaSelecionada));

    chartInstances.evolucao = new Chart(canvas, {
      type: 'line',
      data: { labels: datas, datasets: datasets },
      options: chartOpcoes('Evolucao por periodo'),
    });
  }

  /* ---------- Slide 2: Comparativo entre unidades (bar chart) ---------- */
  function renderizarSlideComparativo() {
    var canvas = document.getElementById('chart-comparativo');
    if (!canvas) return;

    if (chartInstances.comparativo) {
      chartInstances.comparativo.destroy();
    }

    if (!dadosResumo || dadosResumo.length === 0) return;

    var campoSoma = 'soma_' + metricaSelecionada;
    if (metricaSelecionada === 'efetivo_total') campoSoma = 'soma_efetivo';

    var labels = [];
    var valores = [];
    var cores = [];

    dadosResumo.forEach(function (r) {
      labels.push(r.unidade);
      valores.push(r[campoSoma] || 0);
      cores.push(CORES_UNIDADE[r.unidade] || '#888');
    });

    var labelMetrica = METRICAS.find(function (m) {
      return m.chave === metricaSelecionada;
    });

    atualizarTitulo('slide-comparativo-titulo',
      'Comparativo — ' + (labelMetrica ? labelMetrica.label : metricaSelecionada));

    chartInstances.comparativo = new Chart(canvas, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: labelMetrica ? labelMetrica.label : metricaSelecionada,
          data: valores,
          backgroundColor: cores.map(function (c) { return c + 'CC'; }),
          borderColor: cores,
          borderWidth: 1,
          borderRadius: 4,
        }],
      },
      options: chartOpcoes('Comparativo entre unidades'),
    });
  }

  /* ---------- Opcoes padrao Chart.js ---------- */
  function chartOpcoes(titulo) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            color: '#ccc',
            font: { size: 11 },
            padding: 12,
            usePointStyle: true,
          },
        },
        title: { display: false },
      },
      scales: {
        x: {
          ticks: { color: '#888', font: { size: 10 } },
          grid: { color: '#222' },
        },
        y: {
          beginAtZero: true,
          ticks: { color: '#888', font: { size: 10 } },
          grid: { color: '#222' },
        },
      },
    };
  }

  /* ---------- Exportacao PNG ---------- */
  window.exportarSlides = function () {
    var slides = document.querySelectorAll('.slide-card');
    if (slides.length === 0) return;

    var btn = document.getElementById('btn-exportar-slides');
    if (btn) btn.disabled = true;

    var idx = 0;
    function exportarProximo() {
      if (idx >= slides.length) {
        if (btn) btn.disabled = false;
        return;
      }
      var slide = slides[idx];
      html2canvas(slide, {
        scale: 3,
        backgroundColor: '#0d0d0d',
        useCORS: true,
      }).then(function (canvas) {
        var link = document.createElement('a');
        link.download = 'slide_' + (idx + 1) + '_' + metricaSelecionada + '.png';
        link.href = canvas.toDataURL('image/png');
        link.click();
        idx++;
        setTimeout(exportarProximo, 300);
      });
    }
    exportarProximo();
  };

  /* ---------- Atualiza texto do titulo sem apagar info-icon ---------- */
  function atualizarTitulo(id, texto) {
    var el = document.getElementById(id);
    if (!el) return;
    var icon = el.querySelector('.info-icon');
    el.textContent = texto + ' ';
    if (icon) el.appendChild(icon);
  }

  /* ---------- Helpers ---------- */
  function extrairUnidades(serie) {
    var set = {};
    serie.forEach(function (r) { set[r.unidade] = true; });
    return Object.keys(set).sort();
  }

  function extrairDatas(serie) {
    var set = {};
    serie.forEach(function (r) { set[r.data] = true; });
    return Object.keys(set).sort();
  }

})();
