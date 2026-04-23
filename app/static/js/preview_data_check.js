/**
 * Card de "data detectada" no preview (Fase 6.5.a).
 *
 * Linha de defesa preventiva: antes do operador salvar, comparar a data que
 * o parser detectou no texto com a data de hoje (fonte: chip server-side).
 * Se houver divergência, colorir o card e mostrar linguagem natural:
 * "HOJE" / "ONTEM" / "AMANHÃ" / "N dias atrás" / "em N dias".
 *
 * Exposto como window.PreviewDataCheck.
 *
 * Toda lógica de comparação e classificação fica aqui (no frontend) porque
 * o chip de referência ("hoje") vem server-side via [data-hoje]; o estado
 * derivado é puro render e não exige round-trip.
 */
(function () {
  'use strict';

  var DIAS_SEMANA = [
    'domingo', 'segunda-feira', 'terça-feira', 'quarta-feira',
    'quinta-feira', 'sexta-feira', 'sábado',
  ];

  /** 'dd/mm/yyyy' -> Date (meio-dia UTC para evitar drift de DST). null se inválido. */
  function parseBR(str) {
    if (typeof str !== 'string') return null;
    var m = str.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    if (!m) return null;
    var d = parseInt(m[1], 10);
    var mo = parseInt(m[2], 10);
    var y = parseInt(m[3], 10);
    if (mo < 1 || mo > 12 || d < 1 || d > 31) return null;
    var dt = new Date(Date.UTC(y, mo - 1, d, 12, 0, 0));
    if (dt.getUTCFullYear() !== y || dt.getUTCMonth() !== mo - 1 || dt.getUTCDate() !== d) {
      return null;
    }
    return dt;
  }

  function diffDias(alvo, hoje) {
    var ms = alvo.getTime() - hoje.getTime();
    return Math.round(ms / 86400000);
  }

  /** Retorna texto em linguagem natural para um offset em dias vs hoje. */
  function rotuloRelativo(offset, alvo) {
    if (offset === 0) return 'HOJE';
    if (offset === -1) return 'ONTEM';
    if (offset === 1) return 'AMANHÃ';
    if (offset >= -6 && offset <= -2) {
      return DIAS_SEMANA[alvo.getUTCDay()] + ' (' + Math.abs(offset) + ' dias atrás)';
    }
    if (offset >= 2 && offset <= 6) {
      return DIAS_SEMANA[alvo.getUTCDay()] + ' (em ' + offset + ' dias)';
    }
    if (offset < 0) return Math.abs(offset) + ' dias atrás';
    return 'em ' + offset + ' dias';
  }

  /** Dia-da-semana para data detectada, ex: 'quarta-feira'. */
  function diaDaSemana(alvo) {
    return DIAS_SEMANA[alvo.getUTCDay()];
  }

  /** Lê hoje-data do chip server-side (fonte única). null se ausente. */
  function lerHojeChip() {
    var el = document.querySelector('.hoje-chip__data[data-hoje]');
    if (!el) return null;
    return parseBR(el.getAttribute('data-hoje'));
  }

  /**
   * Classifica uma data detectada contra hoje.
   * Retorna objeto { estado, rotulo, texto_auxiliar, data_str }.
   * estado: 'verde' | 'amarela' | 'laranja' | 'vermelha'
   */
  function classificar(dataStr) {
    var hoje = lerHojeChip();
    if (!dataStr) {
      return {
        estado: 'vermelha', rotulo: '(sem data)', data_str: '',
        texto_auxiliar: 'DATA NÃO DETECTADA — informe a data antes de salvar',
        bloqueia_salvar: true,
      };
    }
    var alvo = parseBR(dataStr);
    if (!alvo) {
      return {
        estado: 'vermelha', rotulo: '(formato inválido)', data_str: dataStr,
        texto_auxiliar: 'DATA NÃO RECONHECIDA — formato esperado dd/mm/aaaa',
        bloqueia_salvar: true,
      };
    }
    if (!hoje) {
      return {
        estado: 'amarela', rotulo: diaDaSemana(alvo), data_str: dataStr,
        texto_auxiliar: 'Referência "hoje" indisponível — confirme manualmente',
        bloqueia_salvar: false,
      };
    }
    var offset = diffDias(alvo, hoje);
    if (offset === 0) {
      return {
        estado: 'verde', rotulo: 'HOJE', data_str: dataStr,
        texto_auxiliar: diaDaSemana(alvo),
        bloqueia_salvar: false,
      };
    }
    if (offset === -1) {
      return {
        estado: 'amarela', rotulo: 'ONTEM', data_str: dataStr,
        texto_auxiliar: diaDaSemana(alvo) + ' — confirme se é retroativo',
        bloqueia_salvar: false,
      };
    }
    if (offset === 1) {
      return {
        estado: 'amarela', rotulo: 'AMANHÃ', data_str: dataStr,
        texto_auxiliar: diaDaSemana(alvo) + ' — previsão antecipada?',
        bloqueia_salvar: false,
      };
    }
    return {
      estado: 'laranja', rotulo: rotuloRelativo(offset, alvo), data_str: dataStr,
      texto_auxiliar: 'DIVERGENTE de hoje — confirme se é o dia correto',
      bloqueia_salvar: false,
    };
  }

  /** Datas representativas de um array de cabeçalhos. Retorna { unica, lista }. */
  function datasDosCabecalhos(cabecalhos) {
    var vistas = [];
    var seen = {};
    (cabecalhos || []).forEach(function (c) {
      var d = (c && c.data) ? String(c.data) : '';
      if (d && !seen[d]) {
        seen[d] = true;
        vistas.push(d);
      }
    });
    return { unica: vistas.length === 1 ? vistas[0] : null, lista: vistas };
  }

  /** Renderiza card no container. Mostra info da data detectada + estado. */
  function render(container, cabecalhos) {
    if (!container) return;
    container.innerHTML = '';
    var datas = datasDosCabecalhos(cabecalhos);
    if (datas.lista.length > 1) {
      // Caso raro: texto com múltiplas datas — render 1 card por data.
      datas.lista.forEach(function (d) {
        container.appendChild(_montarCard(classificar(d), true));
      });
      return;
    }
    container.appendChild(_montarCard(classificar(datas.unica || ''), false));
  }

  function _montarCard(info, ehMultiDatas) {
    var card = document.createElement('div');
    card.className = 'data-detectada-card data-detectada-' + info.estado;
    card.setAttribute('data-estado', info.estado);
    card.setAttribute('data-bloqueia', info.bloqueia_salvar ? '1' : '0');
    if (info.data_str) card.setAttribute('data-data', info.data_str);

    var titulo = document.createElement('div');
    titulo.className = 'data-detectada-titulo';
    titulo.textContent = ehMultiDatas
      ? 'Data detectada (texto com múltiplas datas):'
      : 'Data detectada no texto:';
    card.appendChild(titulo);

    var linha = document.createElement('div');
    linha.className = 'data-detectada-linha';
    var dataSpan = document.createElement('span');
    dataSpan.className = 'data-detectada-data';
    dataSpan.textContent = info.data_str || '—';
    var rotuloSpan = document.createElement('span');
    rotuloSpan.className = 'data-detectada-rotulo';
    rotuloSpan.textContent = info.rotulo;
    linha.appendChild(dataSpan);
    linha.appendChild(rotuloSpan);
    card.appendChild(linha);

    var aux = document.createElement('div');
    aux.className = 'data-detectada-aux';
    aux.textContent = info.texto_auxiliar;
    card.appendChild(aux);

    return card;
  }

  /** Retorna true se o preview atual tem alguma data que bloqueia salvar. */
  function bloqueiaSalvar(container) {
    if (!container) return false;
    var cards = container.querySelectorAll('[data-bloqueia="1"]');
    return cards.length > 0;
  }

  /** Retorna a data detectada para exibir no modal de confirmação.
   *  Se múltiplas, retorna null (modal lida). */
  function dataUnica(cabecalhos) {
    return datasDosCabecalhos(cabecalhos).unica;
  }

  /** Info detalhada para a data única (estado + rótulo). null se múltiplas/sem. */
  function infoDataUnica(cabecalhos) {
    var u = dataUnica(cabecalhos);
    return u ? classificar(u) : null;
  }

  window.PreviewDataCheck = {
    parseBR: parseBR,
    classificar: classificar,
    render: render,
    bloqueiaSalvar: bloqueiaSalvar,
    dataUnica: dataUnica,
    infoDataUnica: infoDataUnica,
    rotuloRelativo: rotuloRelativo,
    diaDaSemana: diaDaSemana,
  };
})();
