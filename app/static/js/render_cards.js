/** Aliases de fracao que devem ser ocultados no card (nome real ja esta no titulo do grupo). */
var ALIAS_FRACAO = { '3ª cia': '', '3a cia': '' };

function normalizarNomeFracao(nome) {
  var low = String(nome || '').toLowerCase().trim();
  return low in ALIAS_FRACAO ? '' : nome;
}

/**
 * Gera HTML do logo da unidade.
 * @param {string} unidade
 * @returns {string}
 */
function logoHtml(unidade) {
  var src = LOGOS[unidade] || '';
  if (src) {
    return '<img src="' + src + '" alt="" crossorigin="anonymous">';
  }
  return '<svg viewBox="0 0 24 24" fill="rgba(255,255,255,0.3)" width="28" height="28">' +
    '<path d="M12 2L2 7v10l10 5 10-5V7L12 2zm0 2.18L20 8.27v7.46L12 19.82 4 15.73V8.27L12 4.18z"/></svg>';
}

/**
 * Escapa HTML para prevenir XSS.
 * @param {string} str
 * @returns {string}
 */
function escapeHtml(str) {
  var div = document.createElement('div');
  div.appendChild(document.createTextNode(str != null ? String(str) : ''));
  return div.innerHTML;
}

/**
 * Renderiza todos os cards de uma unidade no container.
 * @param {string} unidade
 * @param {Array} dadosFracoes
 * @param {Array} dadosCabecalho
 */
function renderizarCards(unidade, dadosFracoes, dadosCabecalho) {
  var container = document.getElementById('cards-container');
  container.innerHTML = '';

  var grupos = agruparFracoes(unidade, dadosFracoes);
  var cabecalho = null;
  for (var i = 0; i < dadosCabecalho.length; i++) {
    if (dadosCabecalho[i].unidade === unidade) {
      cabecalho = dadosCabecalho[i];
      break;
    }
  }

  var dataStr = '';
  if (cabecalho) {
    dataStr = cabecalho.data;
  } else {
    for (var j = 0; j < dadosFracoes.length; j++) {
      if (dadosFracoes[j].unidade === unidade) {
        dataStr = dadosFracoes[j].data || '';
        break;
      }
    }
  }

  var totalCards = (cabecalho ? 1 : 0) + grupos.length;
  var screenW = window.innerWidth - 40;
  var cols = totalCards;
  var cardW = Math.floor(screenW / cols) - 12;
  if (cardW > 380) cardW = 380;
  if (cardW < 280) {
    cols = Math.floor(screenW / 292);
    if (cols < 1) cols = 1;
    cardW = Math.min(380, Math.floor(screenW / cols) - 12);
  }

  container.style.gridTemplateColumns = 'repeat(' + cols + ', ' + cardW + 'px)';

  if (cabecalho) {
    container.appendChild(criarCardResumo(unidade, cabecalho, dataStr, 0));
  }

  grupos.forEach(function (grupo, idx) {
    container.appendChild(criarCardFracao(unidade, grupo, dataStr, idx + 1));
  });
}

/**
 * Cria card de fracao.
 */
function criarCardFracao(unidade, grupo, data, idx) {
  var card = document.createElement('div');
  card.className = 'card';
  card.setAttribute('data-card-index', idx);
  card.setAttribute('data-card-id', grupo.id);
  card.setAttribute('data-card-title', grupo.titulo);
  card.setAttribute('data-card-unidade', unidade);

  var totalPMs = 0;
  var totalEquipes = 0;
  grupo.fracoes.forEach(function (f) {
    totalPMs += parseInt(f.pms, 10) || 0;
    totalEquipes += parseInt(f.equipes, 10) || 0;
  });

  var turno = grupo.fracoes[0] ? grupo.fracoes[0].turno : '';

  var html = '<div class="card-header">' +
    '<div class="card-header-logo">' + logoHtml(unidade) + '</div>' +
    '<div class="card-header-text">' +
    '<div class="card-header-org">BRIGADA MILITAR - CPChq</div>' +
    '<div class="card-header-title">' + escapeHtml(unidade) + ' — ' + escapeHtml(grupo.titulo) + '</div>' +
    '<div class="card-header-date">' + escapeHtml(data) + '</div>' +
    '</div></div><div class="card-body">';

  grupo.fracoes.forEach(function (f) {
    var cor = CORES_TIPO[inferirTipo(f.fracao)] || grupo.cor || '#888';
    var horarioTexto = '';
    if (f.horario_inicio && f.horario_fim) {
      horarioTexto = escapeHtml(f.horario_inicio) + ' – ' + escapeHtml(f.horario_fim);
    } else {
      horarioTexto = escapeHtml(f.horario_inicio || '');
    }

    var tel = String(f.telefone || '').replace(/\s/g, '');

    html += '<div class="fracao-item">' +
      '<div class="fracao-stripe" style="background:' + cor + '"></div>' +
      '<div class="fracao-content">' +
      '<div class="fracao-sublabel">' + escapeHtml(normalizarNomeFracao(f.fracao)) + '</div>' +
      '<div class="fracao-comandante">' + escapeHtml(f.comandante) + '</div>' +
      '<div class="fracao-telefone"><a href="tel:' + escapeHtml(tel) + '">' + escapeHtml(f.telefone) + '</a></div>' +
      '<div class="fracao-badges">';

    if (f.equipes) {
      html += '<span class="badge"><svg viewBox="0 0 24 24"><path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5z"/></svg>' + escapeHtml(f.equipes) + ' Eq</span>';
    }

    html += '<span class="badge"><svg viewBox="0 0 24 24"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>' + escapeHtml(f.pms) + ' PMs</span>' +
      '<span class="badge badge-horario"><svg viewBox="0 0 24 24"><path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/></svg>' + horarioTexto + '</span>' +
      '</div>';

    var listaMissoes = (f.missoes && f.missoes.length)
      ? f.missoes
      : (f.missao ? [{ missao_nome_raw: f.missao,
                       municipio_nome_raw: f.municipio_nome_raw || '',
                       bpm_codigos: [], em_quartel: false }] : []);
    listaMissoes.forEach(function (m) {
      var nome = escapeHtml(m.missao_nome_raw || '');
      var sufixo = '';
      // em_quartel nao renderiza sufixo — nome da missao (Prontidao) ja basta.
      if (!m.em_quartel && m.municipio_nome_raw) {
        var mun = escapeHtml(m.municipio_nome_raw);
        // Fase 6.4: BPMs agora sao lista. Compat: cai em bpm_codigo/bpm_raw
        // legado se o payload ainda for singular.
        var codigos = Array.isArray(m.bpm_codigos) ? m.bpm_codigos : [];
        var bpmTexto = codigos.length
          ? codigos.map(escapeHtml).join(', ')
          : escapeHtml(m.bpm_codigo || m.bpm_raw || '');
        var meta = bpmTexto ? mun + ' / ' + bpmTexto : mun;
        sufixo = ' <span class="fracao-missao-meta">— ' + meta + '</span>';
      }
      html += '<div class="fracao-missao">' + nome + sufixo + '</div>';
    });

    html += '</div></div>';
  });

  html += '</div>';
  html += '<div class="card-footer"><div class="card-footer-stats">' +
    '<div class="card-footer-stat"><div class="stat-value">' + totalPMs + '</div><div class="stat-label">PMs</div></div>' +
    '<div class="card-footer-stat"><div class="stat-value">' + totalEquipes + '</div><div class="stat-label">Equipes</div></div>' +
    '</div></div>';

  card.innerHTML = html;
  return card;
}

/**
 * Cria card de resumo da jornada.
 */
function criarCardResumo(unidade, cab, data, cardIndex) {
  var card = document.createElement('div');
  card.className = 'card';
  card.setAttribute('data-card-index', cardIndex);
  card.setAttribute('data-card-id', 'resumo');
  card.setAttribute('data-card-title', 'Resumo da Jornada');
  card.setAttribute('data-card-unidade', unidade);

  var gridItems = [
    { valor: cab.efetivo_total, label: 'Efetivo Total' },
    { valor: cab.oficiais, label: 'Oficiais' },
    { valor: cab.sargentos, label: 'Sargentos' },
    { valor: cab.soldados, label: 'Soldados' },
    { valor: cab.ef_motorizado, label: 'Ef. Motorizado' },
    { valor: cab.vtrs, label: 'VTRs' },
    { valor: cab.motos, label: 'Motos' },
    { valor: cab.armas_ace, label: 'ACE' },
    { valor: cab.armas_portateis, label: 'Portateis' },
    { valor: cab.armas_longas, label: 'Longas' },
    { valor: cab.animais, label: 'Animais' },
  ];

  var missoes = String(cab.missoes_osv || '').split(/[,;]+/).map(function (s) { return s.trim(); }).filter(Boolean);
  var locais = String(cab.locais_atuacao || '').split(/[\/,;]+/).map(function (s) { return s.trim(); }).filter(Boolean);

  var html = '<div class="card-header">' +
    '<div class="card-header-logo">' + logoHtml(unidade) + '</div>' +
    '<div class="card-header-text">' +
    '<div class="card-header-org">BRIGADA MILITAR - CPChq</div>' +
    '<div class="card-header-title">' + escapeHtml(unidade) + ' — Resumo da Jornada</div>' +
    '<div class="card-header-date">' + escapeHtml(data) +
    (cab.horario_emprego ? ' | ' + escapeHtml(cab.horario_emprego) : '') +
    '</div>' +
    '</div></div><div class="card-body"><div class="resumo-grid">';

  gridItems.forEach(function (item) {
    var v = (item.valor != null && item.valor !== '') ? item.valor : '0';
    html += '<div class="resumo-item"><div class="resumo-value">' + escapeHtml(v) + '</div>' +
      '<div class="resumo-label">' + escapeHtml(item.label) + '</div></div>';
  });

  html += '</div><div class="resumo-section"><div class="resumo-section-title">Missoes / OSV</div><div class="resumo-tags">';
  missoes.forEach(function (m) {
    html += '<span class="resumo-tag tag-missao">' + escapeHtml(m) + '</span>';
  });
  html += '</div></div><div class="resumo-section"><div class="resumo-section-title">Locais de Atuacao</div><div class="resumo-tags">';
  locais.forEach(function (l) {
    html += '<span class="resumo-tag tag-local">' + escapeHtml(l) + '</span>';
  });
  html += '</div></div>';

  if (cab.oficial_superior) {
    html += '<div class="resumo-info-row"><span class="resumo-info-label">Of. Superior</span>' +
      '<span class="resumo-info-value">' + escapeHtml(cab.oficial_superior) +
      ' <span class="resumo-info-sub">' + escapeHtml(cab.tel_oficial) + '</span></span></div>';
  }
  if (cab.tel_copom) {
    html += '<div class="resumo-info-row"><span class="resumo-info-label">COPOM</span>' +
      '<span class="resumo-info-value">' + escapeHtml(cab.tel_copom) + '</span></div>';
  }
  if (cab.operador_diurno) {
    html += '<div class="resumo-info-row"><span class="resumo-info-label">Op. Diurno</span>' +
      '<span class="resumo-info-value">' + escapeHtml(cab.operador_diurno) +
      (cab.tel_op_diurno ? ' <span class="resumo-info-sub">' + escapeHtml(cab.tel_op_diurno) + '</span>' : '') +
      ' <span class="resumo-info-sub">' + escapeHtml(cab.horario_op_diurno) + '</span></span></div>';
  }
  if (cab.operador_noturno) {
    html += '<div class="resumo-info-row"><span class="resumo-info-label">Op. Noturno</span>' +
      '<span class="resumo-info-value">' + escapeHtml(cab.operador_noturno) +
      (cab.tel_op_noturno ? ' <span class="resumo-info-sub">' + escapeHtml(cab.tel_op_noturno) + '</span>' : '') +
      ' <span class="resumo-info-sub">' + escapeHtml(cab.horario_op_noturno) + '</span></span></div>';
  }

  html += '<div style="height:8px"></div></div>';
  html += '<div class="card-footer"><div class="card-footer-stats">' +
    '<div class="card-footer-stat"><div class="stat-value">' + escapeHtml(cab.efetivo_total) + '</div><div class="stat-label">Efetivo</div></div>' +
    '<div class="card-footer-stat"><div class="stat-value">' + escapeHtml(cab.vtrs) + '</div><div class="stat-label">VTRs</div></div>' +
    '</div></div>';

  card.innerHTML = html;
  return card;
}
