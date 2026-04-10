/** Painel do Analista — Fase 2 */
(function () {
  'use strict';

  /* ---------- Elementos ---------- */
  const elDataInicio    = document.getElementById('data-inicio');
  const elDataFim       = document.getElementById('data-fim');
  const elUnidadesBox   = document.getElementById('unidades-box');
  const elBtnConsultar  = document.getElementById('btn-consultar');
  const elStatus        = document.getElementById('status-msg');
  const elConteudo      = document.getElementById('analista-conteudo');
  const elResumoCards   = document.getElementById('resumo-cards');
  const elTabelaFracoes = document.getElementById('tabela-fracoes-body');
  const elTabelaCab     = document.getElementById('tabela-cab-body');
  const elTabelaFracoesFoot = document.getElementById('tabela-fracoes-foot');
  const elTabelaCabFoot = document.getElementById('tabela-cab-foot');
  const elTotalFracoes  = document.getElementById('total-fracoes');
  const elTotalCab      = document.getElementById('total-cab');

  /* ---------- Estado ---------- */
  let unidadesSelecionadas = new Set();

  /* ---------- Inicializacao ---------- */
  carregarFiltros();

  elBtnConsultar.addEventListener('click', consultarDados);

  document.querySelectorAll('.tab-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      trocarTab(btn.dataset.tab);
    });
  });

  /* ---------- Filtros ---------- */
  function carregarFiltros() {
    fetch('/api/analista/filtros')
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data.erro) {
          mostrarStatus('Banco de dados nao configurado. Funcionalidade offline indisponivel.', 'erro');
          elBtnConsultar.disabled = true;
          return;
        }
        renderizarUnidades(data.unidades);
        preencherDatasDefault(data.datas);
      })
      .catch(function () {
        mostrarStatus('Banco de dados nao configurado. Conecte o Supabase para usar o painel.', 'erro');
        elBtnConsultar.disabled = true;
      });
  }

  function renderizarUnidades(unidades) {
    elUnidadesBox.innerHTML = '';
    unidades.forEach(function (u) {
      var chip = document.createElement('label');
      chip.className = 'unidade-chip';
      chip.textContent = u;

      var cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.value = u;

      chip.prepend(cb);
      chip.addEventListener('click', function (ev) {
        ev.preventDefault();
        if (unidadesSelecionadas.has(u)) {
          unidadesSelecionadas.delete(u);
          chip.classList.remove('ativo');
        } else {
          unidadesSelecionadas.add(u);
          chip.classList.add('ativo');
        }
      });

      elUnidadesBox.appendChild(chip);
    });
  }

  function preencherDatasDefault(datas) {
    if (!datas || datas.length === 0) {
      mostrarStatus('Nenhum dado encontrado no banco. Faca upload na aba Operador primeiro.', 'erro');
      return;
    }
    /* Converte dd/mm/yyyy para yyyy-mm-dd se necessario */
    var datasISO = datas.map(converterParaISO).filter(Boolean).sort();
    if (datasISO.length > 0) {
      elDataInicio.value = datasISO[0];
      elDataFim.value = datasISO[datasISO.length - 1];
    }
  }

  function converterParaISO(data) {
    if (!data) return '';
    /* Ja esta em yyyy-mm-dd */
    if (/^\d{4}-\d{2}-\d{2}$/.test(data)) return data;
    /* dd/mm/yyyy */
    var partes = data.split('/');
    if (partes.length === 3) {
      return partes[2] + '-' + partes[1] + '-' + partes[0];
    }
    return data;
  }

  /* ---------- Consulta ---------- */
  function consultarDados() {
    var di = elDataInicio.value;
    var df = elDataFim.value;
    if (!di || !df) {
      mostrarStatus('Selecione o periodo (data inicio e data fim).', 'erro');
      return;
    }

    var unidades = Array.from(unidadesSelecionadas).join(',');
    var url = '/api/analista/dados?data_inicio=' + encodeURIComponent(di)
            + '&data_fim=' + encodeURIComponent(df);
    if (unidades) {
      url += '&unidades=' + encodeURIComponent(unidades);
    }

    mostrarStatus('Consultando dados...', 'carregando');
    elBtnConsultar.disabled = true;

    fetch(url)
      .then(function (res) { return res.json(); })
      .then(function (data) {
        elBtnConsultar.disabled = false;
        if (data.erro) {
          mostrarStatus(data.erro, 'erro');
          return;
        }
        if (data.total_fracoes === 0 && data.total_cabecalho === 0) {
          mostrarStatus('Nenhum registro encontrado para o periodo selecionado.', '');
          esconderConteudo();
          return;
        }
        esconderStatus();
        mostrarConteudo();
        renderizarResumo(data.resumo);
        renderizarTabelaFracoes(data.fracoes);
        renderizarTabelaCabecalho(data.cabecalho);
        elTotalFracoes.textContent = data.total_fracoes;
        elTotalCab.textContent = data.total_cabecalho;
        carregarGraficos(di, df, unidades, data.resumo);
        if (typeof carregarProjecoes === 'function') {
          carregarProjecoes(di, df, unidades);
        }
        if (typeof carregarFracoesAnalytics === 'function') {
          carregarFracoesAnalytics(di, df, unidades);
        }
      })
      .catch(function () {
        elBtnConsultar.disabled = false;
        mostrarStatus('Erro de conexao ao buscar dados.', 'erro');
      });
  }

  /* ---------- Resumo por unidade ---------- */
  function renderizarResumo(resumo) {
    elResumoCards.innerHTML = '';
    if (!resumo || resumo.length === 0) return;

    resumo.forEach(function (r) {
      var logoSrc = LOGOS[r.unidade] || '';
      var logoHtml = logoSrc
        ? '<img src="' + escapeAttr(logoSrc) + '" alt="">'
        : '';

      var card = document.createElement('div');
      card.className = 'resumo-card';
      card.innerHTML =
        '<div class="resumo-card-header">' +
          logoHtml +
          '<span class="unidade-nome">' + escapeHtml(r.unidade) + '</span>' +
          '<span class="dias-badge">' + r.total_dias + ' dia(s)</span>' +
        '</div>' +
        '<div class="resumo-card-body">' +
          itemResumo('Efetivo Total', r.soma_efetivo) +
          itemResumo('Oficiais', r.soma_oficiais) +
          itemResumo('Sargentos', r.soma_sargentos) +
          itemResumo('Soldados', r.soma_soldados) +
          itemResumo('Viaturas', r.soma_vtrs) +
          itemResumo('Motos', r.soma_motos) +
          itemResumo('Armas ACE', r.soma_armas_ace) +
          itemResumo('Armas Port.', r.soma_armas_portateis) +
          itemResumo('Armas Longas', r.soma_armas_longas) +
          itemResumo('Animais', r.soma_animais) +
        '</div>';
      elResumoCards.appendChild(card);
    });
  }

  function itemResumo(label, valor) {
    return '<div class="resumo-item">' +
      '<span class="item-label">' + label + '</span>' +
      '<span class="item-valor">' + (valor || 0) + '</span>' +
    '</div>';
  }

  /* ---------- Tabela fracoes ---------- */
  function renderizarTabelaFracoes(fracoes) {
    elTabelaFracoes.innerHTML = '';
    elTabelaFracoesFoot.innerHTML = '';

    var totalPMs = 0;
    var totalEquipes = 0;

    fracoes.forEach(function (f) {
      totalPMs += f.pms || 0;
      totalEquipes += f.equipes || 0;

      var tr = document.createElement('tr');
      tr.innerHTML =
        '<td>' + escapeHtml(f.data) + '</td>' +
        '<td>' + escapeHtml(f.unidade) + '</td>' +
        '<td>' + escapeHtml(f.fracao) + '</td>' +
        '<td>' + escapeHtml(f.comandante) + '</td>' +
        '<td>' + (f.equipes || 0) + '</td>' +
        '<td>' + (f.pms || 0) + '</td>' +
        '<td>' + escapeHtml(f.horario_inicio || '') + ' - ' + escapeHtml(f.horario_fim || '') + '</td>' +
        '<td>' + escapeHtml(f.missao || '') + '</td>';
      elTabelaFracoes.appendChild(tr);
    });

    var trFoot = document.createElement('tr');
    trFoot.innerHTML =
      '<td colspan="4">TOTAL</td>' +
      '<td>' + totalEquipes + '</td>' +
      '<td>' + totalPMs + '</td>' +
      '<td colspan="2"></td>';
    elTabelaFracoesFoot.appendChild(trFoot);
  }

  /* ---------- Tabela cabecalho ---------- */
  function renderizarTabelaCabecalho(cabecalho) {
    elTabelaCab.innerHTML = '';
    elTabelaCabFoot.innerHTML = '';

    var totais = {
      efetivo: 0, oficiais: 0, sargentos: 0, soldados: 0,
      vtrs: 0, motos: 0, armas_ace: 0, armas_port: 0, armas_longas: 0
    };

    cabecalho.forEach(function (c) {
      totais.efetivo += c.efetivo_total || 0;
      totais.oficiais += c.oficiais || 0;
      totais.sargentos += c.sargentos || 0;
      totais.soldados += c.soldados || 0;
      totais.vtrs += c.vtrs || 0;
      totais.motos += c.motos || 0;
      totais.armas_ace += c.armas_ace || 0;
      totais.armas_port += c.armas_portateis || 0;
      totais.armas_longas += c.armas_longas || 0;

      var tr = document.createElement('tr');
      tr.innerHTML =
        '<td>' + escapeHtml(c.data) + '</td>' +
        '<td>' + escapeHtml(c.unidade) + '</td>' +
        '<td>' + (c.efetivo_total || 0) + '</td>' +
        '<td>' + (c.oficiais || 0) + '</td>' +
        '<td>' + (c.sargentos || 0) + '</td>' +
        '<td>' + (c.soldados || 0) + '</td>' +
        '<td>' + (c.vtrs || 0) + '</td>' +
        '<td>' + (c.motos || 0) + '</td>' +
        '<td>' + (c.armas_ace || 0) + '</td>' +
        '<td>' + (c.armas_portateis || 0) + '</td>' +
        '<td>' + (c.armas_longas || 0) + '</td>' +
        '<td>' + escapeHtml(c.oficial_superior || '') + '</td>';
      elTabelaCab.appendChild(tr);
    });

    var trFoot = document.createElement('tr');
    trFoot.innerHTML =
      '<td colspan="2">TOTAL</td>' +
      '<td>' + totais.efetivo + '</td>' +
      '<td>' + totais.oficiais + '</td>' +
      '<td>' + totais.sargentos + '</td>' +
      '<td>' + totais.soldados + '</td>' +
      '<td>' + totais.vtrs + '</td>' +
      '<td>' + totais.motos + '</td>' +
      '<td>' + totais.armas_ace + '</td>' +
      '<td>' + totais.armas_port + '</td>' +
      '<td>' + totais.armas_longas + '</td>' +
      '<td></td>';
    elTabelaCabFoot.appendChild(trFoot);
  }

  /* ---------- Graficos (Fase 3) ---------- */
  function carregarGraficos(di, df, unidades, resumo) {
    var url = '/api/analista/serie?data_inicio=' + encodeURIComponent(di)
            + '&data_fim=' + encodeURIComponent(df);
    if (unidades) {
      url += '&unidades=' + encodeURIComponent(unidades);
    }

    var elPeriodoEvo = document.getElementById('slide-evolucao-periodo');
    var elPeriodoComp = document.getElementById('slide-comparativo-periodo');
    var periodo = di + ' a ' + df;
    if (elPeriodoEvo) elPeriodoEvo.textContent = periodo;
    if (elPeriodoComp) elPeriodoComp.textContent = periodo;

    fetch(url)
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data.erro) return;
        if (typeof inicializarGraficos === 'function') {
          inicializarGraficos(data.serie, resumo);
        }
      })
      .catch(function () {});
  }

  /* ---------- Tabs ---------- */
  function trocarTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(function (b) {
      b.classList.toggle('ativo', b.dataset.tab === tabId);
    });
    document.querySelectorAll('.tab-content').forEach(function (c) {
      c.classList.toggle('ativo', c.id === tabId);
    });
  }

  /* ---------- UI helpers ---------- */
  function mostrarStatus(msg, tipo) {
    elStatus.textContent = msg;
    elStatus.className = 'status-msg' + (tipo ? ' ' + tipo : '');
    elStatus.style.display = 'block';
  }

  function esconderStatus() {
    elStatus.style.display = 'none';
  }

  function mostrarConteudo() {
    elConteudo.style.display = 'block';
  }

  function esconderConteudo() {
    elConteudo.style.display = 'none';
  }

  function escapeHtml(str) {
    if (!str) return '';
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(String(str)));
    return div.innerHTML;
  }

  function escapeAttr(str) {
    return String(str).replace(/&/g, '&amp;').replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

})();
