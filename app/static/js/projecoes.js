/** Fase 4 — Projecoes e Analytics de Fracoes */
(function () {
  'use strict';

  var CORES_UNIDADE = {
    '1 BPChq': '#F7B900', '1\u00ba BPChq': '#F7B900',
    '2 BPChq': '#E74C3C', '2\u00ba BPChq': '#E74C3C',
    '3 BPChq': '#3498DB', '3\u00ba BPChq': '#3498DB',
    '4 BPChq': '#2ECC71', '4\u00ba BPChq': '#2ECC71',
    '5 BPChq': '#9B59B6', '5\u00ba BPChq': '#9B59B6',
    '6 BPChq': '#E67E22', '6\u00ba BPChq': '#E67E22',
    '4 RPMon': '#1ABC9C', '4\u00ba RPMon': '#1ABC9C',
  };

  var chartInstances = {};

  /* ============================
     PROJECOES (cabecalho)
     ============================ */

  window.carregarProjecoes = function (di, df, unidades) {
    var url = '/api/analista/projecoes?data_inicio=' + encodeURIComponent(di)
            + '&data_fim=' + encodeURIComponent(df);
    if (unidades) url += '&unidades=' + encodeURIComponent(unidades);

    var periodo = di + ' a ' + df;
    setTexto('slide-mm-periodo', periodo);

    fetch(url)
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data.erro) return;
        renderizarIndicadores(data.indicadores, data.tendencia);
        renderizarMediaMovel(data.media_movel);
        renderizarTendenciaGrid(data.tendencia);
      })
      .catch(function () {});
  };

  /* ============================
     FRACOES ANALYTICS
     ============================ */

  window.carregarFracoesAnalytics = function (di, df, unidades) {
    var url = '/api/analista/fracoes-analytics?data_inicio=' + encodeURIComponent(di)
            + '&data_fim=' + encodeURIComponent(df);
    if (unidades) url += '&unidades=' + encodeURIComponent(unidades);

    var periodo = di + ' a ' + df;
    setTexto('slide-cob-periodo', periodo);
    setTexto('slide-dia-periodo', periodo);

    fetch(url)
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data.erro) return;
        renderizarTabelaMissoes(data.missoes);
        renderizarCobertura(data.cobertura_horaria);
        renderizarDiaSemana(data.padroes_diarios);
        renderizarTabelaFracoesFreq(data.fracoes_freq);
      })
      .catch(function () {});
  };

  /* ---------- Indicadores ---------- */
  function renderizarIndicadores(indicadores, tendencia) {
    var container = document.getElementById('indicadores-grid');
    if (!container) return;
    container.innerHTML = '';

    var unidades = Object.keys(indicadores).sort();
    unidades.forEach(function (unidade) {
      var ind = indicadores[unidade];
      var tend = tendencia[unidade] || {};
      var card = document.createElement('div');
      card.className = 'indicador-card';

      var headerHtml = '<div class="indicador-header">' +
        '<span class="indicador-unidade">' + escapeHtml(unidade) + '</span>' +
        '</div>';

      var bodyHtml = '<div class="indicador-body">';
      var campos = ['efetivo_total', 'vtrs'];
      var labels = { efetivo_total: 'Efetivo', vtrs: 'Vtrs' };

      campos.forEach(function (campo) {
        var dados = ind[campo];
        var t = tend[campo];
        if (!dados) return;

        var seta = '';
        var corSeta = '#888';
        if (t) {
          if (t.direcao === 'crescente') { seta = '\u25B2'; corSeta = '#2ECC71'; }
          else if (t.direcao === 'decrescente') { seta = '\u25BC'; corSeta = '#E74C3C'; }
          else { seta = '\u25AC'; corSeta = '#888'; }
        }

        var varClass = dados.variacao_pct > 0 ? 'positivo' : (dados.variacao_pct < 0 ? 'negativo' : '');

        bodyHtml +=
          '<div class="indicador-row">' +
            '<span class="ind-label">' + labels[campo] + '</span>' +
            '<span class="ind-valor">' + dados.ultimo + '</span>' +
            '<span class="ind-media">med ' + dados.media + '</span>' +
            '<span class="ind-variacao ' + varClass + '">' +
              (dados.variacao_pct > 0 ? '+' : '') + dados.variacao_pct + '%' +
            '</span>' +
            '<span class="ind-seta" style="color:' + corSeta + '">' + seta + '</span>' +
          '</div>';
      });

      bodyHtml += '</div>';
      card.innerHTML = headerHtml + bodyHtml;
      container.appendChild(card);
    });
  }

  /* ---------- Media Movel ---------- */
  function renderizarMediaMovel(mediaMovel) {
    var canvas = document.getElementById('chart-media-movel');
    if (!canvas) return;
    destroyChart('mediaMovel');

    var unidades = Object.keys(mediaMovel).sort();
    if (unidades.length === 0) return;

    var todasDatas = [];
    unidades.forEach(function (u) {
      mediaMovel[u].forEach(function (r) {
        if (todasDatas.indexOf(r.data) === -1) todasDatas.push(r.data);
      });
    });
    todasDatas.sort();

    var datasets = [];
    unidades.forEach(function (u) {
      var pontos = todasDatas.map(function (d) {
        var reg = mediaMovel[u].find(function (r) { return r.data === d; });
        return reg ? reg.efetivo_total_mm : null;
      });
      datasets.push({
        label: u + ' (MM)',
        data: pontos,
        borderColor: CORES_UNIDADE[u] || '#888',
        backgroundColor: (CORES_UNIDADE[u] || '#888') + '33',
        borderWidth: 2,
        pointRadius: todasDatas.length > 30 ? 0 : 3,
        tension: 0.4,
        fill: false,
        spanGaps: true,
      });
    });

    chartInstances.mediaMovel = new Chart(canvas, {
      type: 'line',
      data: { labels: todasDatas, datasets: datasets },
      options: chartOpcoes(),
    });
  }

  /* ---------- Tendencia Grid ---------- */
  function renderizarTendenciaGrid(tendencia) {
    var container = document.getElementById('tendencia-grid');
    if (!container) return;
    container.innerHTML = '';

    var unidades = Object.keys(tendencia).sort();
    var campos = ['efetivo_total', 'vtrs'];
    var labels = { efetivo_total: 'Efetivo', vtrs: 'Vtrs' };

    unidades.forEach(function (unidade) {
      var tend = tendencia[unidade];
      if (!tend || Object.keys(tend).length === 0) return;

      var card = document.createElement('div');
      card.className = 'tendencia-card';
      var html = '<div class="tendencia-header">' + escapeHtml(unidade) + '</div>';
      html += '<div class="tendencia-body">';

      campos.forEach(function (campo) {
        var t = tend[campo];
        if (!t) return;
        var cor = t.direcao === 'crescente' ? '#2ECC71' : (t.direcao === 'decrescente' ? '#E74C3C' : '#888');
        var seta = t.direcao === 'crescente' ? '\u25B2' : (t.direcao === 'decrescente' ? '\u25BC' : '\u25AC');
        html += '<div class="tend-row">' +
          '<span class="tend-label">' + labels[campo] + '</span>' +
          '<span class="tend-seta" style="color:' + cor + '">' + seta + ' ' + t.coef + '/dia</span>' +
          '</div>';
      });

      html += '</div>';
      card.innerHTML = html;
      container.appendChild(card);
    });
  }

  /* ---------- Tabela Missoes ---------- */
  function renderizarTabelaMissoes(missoes) {
    var tbody = document.getElementById('tabela-missoes-body');
    if (!tbody) return;
    tbody.innerHTML = '';

    var ranking = missoes.ranking || [];
    ranking.forEach(function (r, i) {
      var tr = document.createElement('tr');
      tr.innerHTML =
        '<td>' + (i + 1) + '</td>' +
        '<td>' + escapeHtml(r.missao) + '</td>' +
        '<td>' + r.total + '</td>' +
        '<td>' + r.pms_total + '</td>' +
        '<td>' + r.equipes_total + '</td>';
      tbody.appendChild(tr);
    });
  }

  /* ---------- Cobertura Horaria ---------- */
  function renderizarCobertura(cobertura) {
    var canvas = document.getElementById('chart-cobertura');
    if (!canvas) return;
    destroyChart('cobertura');

    var horas = cobertura.horas_cobertura || [];
    if (horas.length === 0) return;

    var labels = horas.map(function (h) { return h.hora + 'h'; });
    var valores = horas.map(function (h) { return h.pms_medio; });

    var cores = valores.map(function (v) {
      if (v < 5) return '#E74C3C99';
      if (v < 15) return '#F7B90099';
      return '#2ECC7199';
    });

    chartInstances.cobertura = new Chart(canvas, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'PMs medio',
          data: valores,
          backgroundColor: cores,
          borderColor: cores.map(function (c) { return c.replace('99', 'FF'); }),
          borderWidth: 1,
          borderRadius: 3,
        }],
      },
      options: chartOpcoes(),
    });
  }

  /* ---------- Padroes por Dia da Semana ---------- */
  function renderizarDiaSemana(padroes) {
    var canvas = document.getElementById('chart-dia-semana');
    if (!canvas) return;
    destroyChart('diaSemana');

    var dias = padroes.por_dia_semana || [];
    if (dias.length === 0) return;

    var labels = dias.map(function (d) { return d.dia_label; });
    var pmsMedio = dias.map(function (d) { return d.pms_medio; });
    var fracoesMedio = dias.map(function (d) { return d.fracoes_media; });

    chartInstances.diaSemana = new Chart(canvas, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'PMs medio',
            data: pmsMedio,
            backgroundColor: '#F7B90099',
            borderColor: '#F7B900',
            borderWidth: 1,
            borderRadius: 4,
          },
          {
            label: 'Fracoes media',
            data: fracoesMedio,
            backgroundColor: '#3498DB99',
            borderColor: '#3498DB',
            borderWidth: 1,
            borderRadius: 4,
          },
        ],
      },
      options: chartOpcoes(),
    });
  }

  /* ---------- Tabela Fracoes Freq ---------- */
  function renderizarTabelaFracoesFreq(fracoesFreq) {
    var tbody = document.getElementById('tabela-fracoes-freq-body');
    if (!tbody) return;
    tbody.innerHTML = '';

    var geral = fracoesFreq.geral || [];
    geral.forEach(function (r, i) {
      var tr = document.createElement('tr');
      tr.innerHTML =
        '<td>' + (i + 1) + '</td>' +
        '<td>' + escapeHtml(r.fracao) + '</td>' +
        '<td>' + r.total + '</td>' +
        '<td>' + r.pms_total + '</td>';
      tbody.appendChild(tr);
    });
  }

  /* ---------- Helpers ---------- */
  function chartOpcoes() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
          labels: { color: '#ccc', font: { size: 11 }, padding: 12, usePointStyle: true },
        },
      },
      scales: {
        x: { ticks: { color: '#888', font: { size: 10 } }, grid: { color: '#222' } },
        y: { beginAtZero: true, ticks: { color: '#888', font: { size: 10 } }, grid: { color: '#222' } },
      },
    };
  }

  function destroyChart(key) {
    if (chartInstances[key]) {
      chartInstances[key].destroy();
      chartInstances[key] = null;
    }
  }

  function setTexto(id, texto) {
    var el = document.getElementById(id);
    if (el) el.textContent = texto;
  }

  function escapeHtml(str) {
    if (!str) return '';
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(String(str)));
    return div.innerHTML;
  }

})();
