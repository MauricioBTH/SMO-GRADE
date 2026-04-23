/**
 * Modal de confirmação final antes de gravar (Fase 6.5.a).
 *
 * Mostra ao operador — uma última vez, antes do DB — unidade(s), data, e
 * contagens (frações / missões). O botão afirmativo carrega a data no label
 * ("Confirmar 23/04") para reduzir piloto-automático.
 *
 * Na Fase 6.5.b, se já existe upload ativo para a (unidade, data), o modal
 * consulta /api/uploads/existente e insere um bloco "será substituído —
 * poderá ser restaurado no histórico". Hoje (6.5.a pura) consulta tolerante:
 * se o endpoint não existir (6.5.b ainda não aplicada), apenas omite o bloco.
 *
 * Exposto como window.ModalConfirmarSalvar.abrir({ ... }).
 */
(function () {
  'use strict';

  var overlayEl = null;

  function contarMissoes(fracoes) {
    var total = 0;
    (fracoes || []).forEach(function (f) {
      total += (f.missoes || []).length;
    });
    return total;
  }

  /** Mapa { unidade: {fracoes:N, missoes:N} } a partir do preview. */
  function agrupar(cabecalhos, fracoes) {
    var mapa = {};
    (cabecalhos || []).forEach(function (c) {
      var u = c.unidade || '—';
      if (!mapa[u]) mapa[u] = { fracoes: 0, missoes: 0, data: c.data || '' };
    });
    (fracoes || []).forEach(function (f) {
      var u = f.unidade || '—';
      if (!mapa[u]) mapa[u] = { fracoes: 0, missoes: 0, data: f.data || '' };
      mapa[u].fracoes += 1;
      mapa[u].missoes += (f.missoes || []).length;
    });
    return mapa;
  }

  /** Formata "23/04/2026" -> "23/04" pra encurtar label do botão. */
  function abreviarData(dataStr) {
    if (!dataStr) return '';
    var m = String(dataStr).match(/^(\d{2})\/(\d{2})\/\d{4}$/);
    return m ? (m[1] + '/' + m[2]) : dataStr;
  }

  /** Cria overlay + box, retorna elementos. */
  function montarDom() {
    var ov = document.createElement('div');
    ov.className = 'modal-overlay modal-confirmar-overlay';
    ov.setAttribute('role', 'dialog');
    ov.setAttribute('aria-modal', 'true');

    var box = document.createElement('div');
    box.className = 'modal-box modal-confirmar-box';

    var h = document.createElement('div');
    h.className = 'modal-title';
    h.textContent = 'Confirmar gravação';
    box.appendChild(h);

    var lista = document.createElement('div');
    lista.className = 'modal-confirmar-lista';
    box.appendChild(lista);

    var existente = document.createElement('div');
    existente.className = 'modal-confirmar-existente';
    existente.style.display = 'none';
    box.appendChild(existente);

    var actions = document.createElement('div');
    actions.className = 'modal-actions';
    var btnCancel = document.createElement('button');
    btnCancel.type = 'button';
    btnCancel.className = 'btn-secundario';
    btnCancel.textContent = 'Cancelar';
    var btnOk = document.createElement('button');
    btnOk.type = 'button';
    btnOk.className = 'btn-primario';
    btnOk.textContent = 'Confirmar';
    actions.appendChild(btnCancel);
    actions.appendChild(btnOk);
    box.appendChild(actions);

    ov.appendChild(box);
    document.body.appendChild(ov);

    return { overlay: ov, lista: lista, existente: existente, btnOk: btnOk, btnCancel: btnCancel };
  }

  /**
   * Monta uma linha "Unidade: valor" no resumo.
   */
  function linha(label, valor, extraClass) {
    var row = document.createElement('div');
    row.className = 'modal-confirmar-row' + (extraClass ? (' ' + extraClass) : '');
    var lab = document.createElement('span');
    lab.className = 'modal-confirmar-label';
    lab.textContent = label;
    var val = document.createElement('span');
    val.className = 'modal-confirmar-valor';
    if (typeof valor === 'string' || typeof valor === 'number') {
      val.textContent = valor;
    } else {
      val.appendChild(valor);
    }
    row.appendChild(lab);
    row.appendChild(val);
    return row;
  }

  /** Preenche a #modal-confirmar-lista com unidade/data/contagens. */
  function preencherLista(listaEl, opts) {
    listaEl.innerHTML = '';
    var agrup = agrupar(opts.cabecalhos, opts.fracoes);
    var unidades = Object.keys(agrup);

    if (unidades.length === 1) {
      var u = unidades[0];
      var info = agrup[u];
      listaEl.appendChild(linha('Unidade', u));
      listaEl.appendChild(linha('Data', _celulaData(info.data, opts.dataCheck)));
      listaEl.appendChild(
        linha('Frações', info.fracoes + ' frações, ' + info.missoes + ' missões')
      );
    } else {
      listaEl.appendChild(linha('Unidades', unidades.length + ' unidades'));
      if (opts.dataCheck && opts.dataCheck.data_str) {
        listaEl.appendChild(linha('Data', _celulaData(opts.dataCheck.data_str, opts.dataCheck)));
      }
      unidades.forEach(function (u) {
        var info = agrup[u];
        listaEl.appendChild(
          linha(u, info.fracoes + ' frações, ' + info.missoes + ' missões', 'modal-confirmar-row-sub')
        );
      });
    }
  }

  function _celulaData(dataStr, info) {
    var wrap = document.createElement('span');
    wrap.className = 'modal-confirmar-data';
    var strong = document.createElement('strong');
    strong.textContent = dataStr || '—';
    wrap.appendChild(strong);
    if (info && info.rotulo && info.estado) {
      var badge = document.createElement('span');
      badge.className = 'modal-confirmar-badge modal-confirmar-badge-' + info.estado;
      badge.textContent = info.rotulo;
      wrap.appendChild(badge);
    }
    return wrap;
  }

  /** Consulta endpoint de upload existente (6.5.b); tolera 404 silenciosamente. */
  function consultarExistente(unidade, data) {
    if (!unidade || !data) return Promise.resolve(null);
    var url = '/api/uploads/existente?unidade=' + encodeURIComponent(unidade) +
              '&data=' + encodeURIComponent(data);
    return fetch(url, { credentials: 'same-origin' }).then(function (r) {
      if (!r.ok) return null;
      return r.json().then(function (d) { return d && d.existe ? d : null; });
    }).catch(function () { return null; });
  }

  /** Preenche o bloco "já existe upload" caso retorne algo. */
  function preencherExistente(el, opts) {
    el.style.display = 'none';
    el.innerHTML = '';
    var agrup = agrupar(opts.cabecalhos, opts.fracoes);
    var unidades = Object.keys(agrup);
    if (unidades.length !== 1) return Promise.resolve();
    var u = unidades[0];
    var info = agrup[u];
    if (!info.data) return Promise.resolve();

    // Se o caller (operador.js) já pré-buscou, usa direto — evita o delay
    // visível de 1s entre abrir o modal e renderizar o bloco. O fetch aqui
    // continua como fallback (permite abrir o modal sem prefetch em testes
    // ou chamadas futuras).
    var fonte = (opts.existenteData !== undefined)
      ? Promise.resolve(opts.existenteData)
      : consultarExistente(u, info.data);

    return fonte.then(function (data) {
      if (!data || !data.upload) return;
      var upload = data.upload;
      el.style.display = 'block';
      var titulo = document.createElement('div');
      titulo.className = 'modal-confirmar-existente-titulo';
      titulo.textContent = 'Já existe dado salvo para essa data:';
      el.appendChild(titulo);
      var linhaTxt = document.createElement('div');
      linhaTxt.className = 'modal-confirmar-existente-linha';
      var criadoEm = _formatarHoraISO(upload.criado_em);
      var usuarioNome = upload.usuario_nome || 'usuário desconhecido';
      var qtdeTxt = (typeof upload.qtde_fracoes === 'number')
        ? ' (' + upload.qtde_fracoes + ' frações)'
        : '';
      linhaTxt.textContent = 'Upload de ' + criadoEm + ' por ' + usuarioNome + qtdeTxt;
      el.appendChild(linhaTxt);
      var nota = document.createElement('div');
      nota.className = 'modal-confirmar-existente-nota';
      nota.textContent = 'Será substituído; poderá ser restaurado no histórico.';
      el.appendChild(nota);

      var link = document.createElement('a');
      link.className = 'modal-confirmar-existente-link';
      link.href = '/operador/historico/' + encodeURIComponent(u) +
                  '/' + encodeURIComponent(info.data);
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = 'Ver histórico →';
      el.appendChild(link);
    });
  }

  /** Formata ISO timestamp para "HH:MM hoje"/"HH:MM de dd/mm". */
  function _formatarHoraISO(iso) {
    if (!iso) return '';
    var d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso);
    var hh = String(d.getHours()).padStart(2, '0');
    var mm = String(d.getMinutes()).padStart(2, '0');
    var hoje = new Date();
    var mesmo = (
      d.getFullYear() === hoje.getFullYear() &&
      d.getMonth() === hoje.getMonth() &&
      d.getDate() === hoje.getDate()
    );
    if (mesmo) return hh + ':' + mm + ' hoje';
    var dd = String(d.getDate()).padStart(2, '0');
    var mo = String(d.getMonth() + 1).padStart(2, '0');
    return hh + ':' + mm + ' de ' + dd + '/' + mo;
  }

  function fechar() {
    if (overlayEl) overlayEl.classList.remove('active');
  }

  /** Foco inicial no botão de cancelar (reduz clique acidental). */
  function foco(el) {
    setTimeout(function () {
      try { el.focus(); } catch (_) { /* noop */ }
    }, 30);
  }

  /**
   * Abre o modal.
   * @param {Object} opts
   *   @prop cabecalhos {Array}
   *   @prop fracoes {Array}
   *   @prop dataCheck {Object|null} resultado de PreviewDataCheck.infoDataUnica
   *   @prop onConfirmar {Function} callback síncrono/assíncrono para gravar
   *   @prop onCancelar {Function|undefined}
   */
  function abrir(opts) {
    if (!overlayEl) {
      var refs = montarDom();
      overlayEl = refs.overlay;
      overlayEl._refs = refs;
      refs.btnCancel.addEventListener('click', function () {
        fechar();
        if (typeof overlayEl._currentOnCancel === 'function') {
          overlayEl._currentOnCancel();
        }
      });
      refs.overlay.addEventListener('click', function (e) {
        if (e.target === refs.overlay) {
          fechar();
          if (typeof overlayEl._currentOnCancel === 'function') {
            overlayEl._currentOnCancel();
          }
        }
      });
      refs.btnOk.addEventListener('click', function () {
        if (typeof overlayEl._currentOnConfirm === 'function') {
          var cb = overlayEl._currentOnConfirm;
          fechar();
          cb();
        }
      });
      document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && overlayEl.classList.contains('active')) {
          fechar();
          if (typeof overlayEl._currentOnCancel === 'function') {
            overlayEl._currentOnCancel();
          }
        }
      });
    }

    var refs2 = overlayEl._refs;
    preencherLista(refs2.lista, opts);
    var dataAbrev = abreviarData(opts.dataCheck && opts.dataCheck.data_str);
    refs2.btnOk.textContent = dataAbrev ? ('Confirmar ' + dataAbrev) : 'Confirmar';
    overlayEl._currentOnConfirm = opts.onConfirmar;
    overlayEl._currentOnCancel = opts.onCancelar;

    // Aplica tag de estado no box pra destacar visualmente ontem/divergente.
    refs2.overlay.firstChild.className = 'modal-box modal-confirmar-box';
    if (opts.dataCheck && opts.dataCheck.estado) {
      refs2.overlay.firstChild.classList.add('modal-confirmar-box-' + opts.dataCheck.estado);
    }

    overlayEl.classList.add('active');
    foco(refs2.btnCancel);

    // Bloco "já existe" (6.5.b) — sempre best-effort.
    preencherExistente(refs2.existente, opts);
  }

  window.ModalConfirmarSalvar = { abrir: abrir, fechar: fechar };
})();
