/**
 * Infere tipo da fracao pelo nome.
 * @param {string} fracao
 * @returns {string}
 */
function inferirTipo(fracao) {
  var nome = String(fracao || '').toLowerCase();
  if (nome.indexOf('patres') !== -1 || nome.indexOf('patrulhamento') !== -1) return 'patres';
  if (nome.indexOf('canil') !== -1 || nome.indexOf('faro') !== -1 || nome.indexOf('3ª cia') !== -1 || nome.indexOf('3a cia') !== -1) return 'canil';
  if (nome.indexOf('batedor') !== -1) return 'batedores';
  if (nome.indexOf('opera') !== -1) return 'operacao';
  return 'prontidao';
}

/**
 * Converte string de horario para minutos desde meia-noite.
 * @param {string} h
 * @returns {number}
 */
function parseHorario(h) {
  if (!h || h === 'Retorno' || h === '24hs') return 9999;
  if (!/\d/.test(h)) return 9999;
  const str = String(h).replace('h', ':').replace('hs', '');
  const parts = str.split(':');
  const hh = parseInt(parts[0], 10) || 0;
  const mm = parseInt(parts[1], 10) || 0;
  return hh * 60 + mm;
}

/**
 * Determina faixa horaria a partir de string de horario.
 * @param {string} horario
 * @returns {string}
 */
function faixaHoraria(horario) {
  const min = parseHorario(horario);
  if (min === 9999) return 'manha';
  const h = Math.floor(min / 60);
  if (h >= 6 && h < 12) return 'manha';
  if (h >= 12 && h < 18) return 'tarde';
  return 'noite';
}

var MAX_ITENS_POR_CARD = 5;

/**
 * Quebra um grupo em sub-cards de no maximo MAX_ITENS_POR_CARD.
 * @param {Object} grupo - { id, titulo, cor, fracoes }
 * @returns {Array} lista de grupos (1 se cabe, N se precisou quebrar)
 */
function quebrarGrupo(grupo) {
  var fracoes = grupo.fracoes;
  if (fracoes.length <= MAX_ITENS_POR_CARD) return [grupo];

  var totalParts = Math.ceil(fracoes.length / MAX_ITENS_POR_CARD);
  var subGrupos = [];

  for (var i = 0; i < totalParts; i++) {
    var inicio = i * MAX_ITENS_POR_CARD;
    var fatia = fracoes.slice(inicio, inicio + MAX_ITENS_POR_CARD);
    subGrupos.push({
      id: grupo.id + '_' + (i + 1),
      titulo: grupo.titulo + ' (' + (i + 1) + '/' + totalParts + ')',
      cor: grupo.cor,
      fracoes: fatia,
    });
  }

  return subGrupos;
}

/**
 * Agrupa fracoes de uma unidade conforme regras de negocio.
 * Cada card tem no maximo MAX_ITENS_POR_CARD fracoes.
 * @param {string} unidade
 * @param {Array} dadosFracoes
 * @returns {Array}
 */
function agruparFracoes(unidade, dadosFracoes) {
  const fracoes = dadosFracoes.filter(function (f) { return f.unidade === unidade; });
  const gruposBase = [];

  const nomeNorm = unidade.replace(/[ºª°]/g, '').replace(/\s+/g, '').toLowerCase();
  const eh1BPChq = nomeNorm.includes('1bpchq');

  if (eh1BPChq) {
    var ordemTipos = ['prontidao', 'patres', 'canil_batedores', 'operacao'];
    ordemTipos.forEach(function (tipo) {
      var items;
      if (tipo === 'canil_batedores') {
        items = fracoes.filter(function (f) {
          var nome = inferirTipo(f.fracao);
          return nome === 'canil' || nome === 'batedores';
        });
      } else {
        items = fracoes.filter(function (f) { return inferirTipo(f.fracao) === tipo; });
      }
      if (items.length === 0) return;
      if (tipo === 'canil_batedores') {
        // Canil primeiro, depois batedores; dentro de cada, por horario
        items.sort(function (a, b) {
          var ta = inferirTipo(a.fracao) === 'canil' ? 0 : 1;
          var tb = inferirTipo(b.fracao) === 'canil' ? 0 : 1;
          return ta !== tb ? ta - tb : parseHorario(a.horario_inicio) - parseHorario(b.horario_inicio);
        });
      } else if (tipo === 'prontidao') {
        // Pel Prontidao sempre primeiro
        items.sort(function (a, b) {
          var nome_a = String(a.fracao || '').toLowerCase();
          var nome_b = String(b.fracao || '').toLowerCase();
          var pa = (nome_a.indexOf('pel') !== -1 && nome_a.indexOf('pront') !== -1) ? 0 : 1;
          var pb = (nome_b.indexOf('pel') !== -1 && nome_b.indexOf('pront') !== -1) ? 0 : 1;
          return pa !== pb ? pa - pb : parseHorario(a.horario_inicio) - parseHorario(b.horario_inicio);
        });
      } else {
        items.sort(function (a, b) { return parseHorario(a.horario_inicio) - parseHorario(b.horario_inicio); });
      }
      gruposBase.push({
        id: tipo,
        titulo: tipo === 'canil_batedores' ? 'Canil e Batedores' : (LABELS_TIPO[tipo] || tipo),
        cor: tipo === 'canil_batedores' ? CORES_TIPO['batedores'] : (CORES_TIPO[tipo] || '#666'),
        fracoes: items,
      });
    });
  } else {
    var faixas = {};
    fracoes.forEach(function (f) {
      var fx = faixaHoraria(f.horario_inicio);
      if (!faixas[fx]) faixas[fx] = [];
      faixas[fx].push(f);
    });

    var ordemFaixas = ['manha', 'tarde', 'noite', 'integral'];
    ordemFaixas.forEach(function (fx) {
      if (!faixas[fx] || faixas[fx].length === 0) return;
      faixas[fx].sort(function (a, b) { return parseHorario(a.horario_inicio) - parseHorario(b.horario_inicio); });
      gruposBase.push({
        id: fx,
        titulo: LABELS_FAIXA[fx],
        cor: CORES_FAIXA[fx],
        fracoes: faixas[fx],
      });
    });
  }

  var grupos = [];
  gruposBase.forEach(function (g) {
    var quebrados = quebrarGrupo(g);
    for (var i = 0; i < quebrados.length; i++) {
      grupos.push(quebrados[i]);
    }
  });

  return grupos;
}
