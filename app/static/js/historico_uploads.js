/**
 * Tela de histórico de uploads versionados (Fase 6.5.b).
 *
 * Busca GET /api/uploads?unidade=X&data=Y e renderiza uma tabela com
 * Hora | Usuário | Status | Origem | Frações | Ação. Clique em "Restaurar"
 * chama POST /api/uploads/<id>/restaurar e recarrega a tabela.
 *
 * Frontend-burro: toda validação (incluindo "já é ativo → erro amigável")
 * vem do backend. Aqui só renderiza + re-fetch.
 *
 * Contexto injetado pelo template:
 *   window.HISTORICO_CTX = { unidade, data }
 */
(function () {
  'use strict';

  var STATUS_EL = document.getElementById('historico-status');
  var TABELA_EL = document.getElementById('historico-tabela');
  var TBODY_EL = document.getElementById('historico-tbody');

  function _ctx() {
    var c = window.HISTORICO_CTX || {};
    return { unidade: c.unidade || '', data: c.data || '' };
  }

  function _formatarHora(iso) {
    if (!iso) return '—';
    var d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso);
    return String(d.getHours()).padStart(2, '0') + ':' +
           String(d.getMinutes()).padStart(2, '0');
  }

  function _statusBadge(upload) {
    var badge = document.createElement('span');
    if (upload.ativo) {
      badge.className = 'historico-badge historico-badge-ativo';
      badge.textContent = 'ATUAL';
    } else if (upload.cancelado_em) {
      badge.className = 'historico-badge historico-badge-cancelado';
      badge.textContent = 'substituído';
    } else {
      badge.className = 'historico-badge';
      badge.textContent = '—';
    }
    return badge;
  }

  function _cell(text) {
    var td = document.createElement('td');
    td.textContent = text == null ? '—' : String(text);
    return td;
  }

  function _cellNode(node) {
    var td = document.createElement('td');
    td.appendChild(node);
    return td;
  }

  function _botaoRestaurar(upload) {
    if (upload.ativo) {
      var span = document.createElement('span');
      span.className = 'historico-acao-vazia';
      span.textContent = '—';
      return span;
    }
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn-secundario historico-btn-restaurar';
    btn.textContent = 'Restaurar';
    btn.addEventListener('click', function () { confirmarRestaurar(upload); });
    return btn;
  }

  function _renderLinhas(uploads) {
    TBODY_EL.innerHTML = '';
    if (!uploads || uploads.length === 0) {
      var tr = document.createElement('tr');
      var td = document.createElement('td');
      td.setAttribute('colspan', '6');
      td.className = 'historico-vazio';
      td.textContent = 'Nenhum upload para essa (unidade, data).';
      tr.appendChild(td);
      TBODY_EL.appendChild(tr);
      return;
    }
    uploads.forEach(function (u) {
      var tr = document.createElement('tr');
      tr.className = u.ativo ? 'historico-row-ativo' : 'historico-row-cancelado';
      tr.appendChild(_cell(_formatarHora(u.criado_em)));
      tr.appendChild(_cell(u.usuario_nome || '—'));
      tr.appendChild(_cellNode(_statusBadge(u)));
      tr.appendChild(_cell(u.origem || '—'));
      tr.appendChild(_cell(u.qtde_fracoes));
      tr.appendChild(_cellNode(_botaoRestaurar(u)));
      TBODY_EL.appendChild(tr);
    });
  }

  function _setStatus(msg, erro) {
    STATUS_EL.hidden = false;
    STATUS_EL.textContent = msg;
    STATUS_EL.classList.toggle('historico-status-erro', !!erro);
  }

  function _esconderStatus() {
    STATUS_EL.hidden = true;
    STATUS_EL.textContent = '';
    STATUS_EL.classList.remove('historico-status-erro');
  }

  function carregar() {
    var ctx = _ctx();
    _setStatus('Carregando…', false);
    TABELA_EL.hidden = true;
    var url = '/api/uploads?unidade=' + encodeURIComponent(ctx.unidade) +
              '&data=' + encodeURIComponent(ctx.data);
    fetch(url, { credentials: 'same-origin' })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (d) {
        _esconderStatus();
        TABELA_EL.hidden = false;
        _renderLinhas(d.uploads || []);
      })
      .catch(function (err) {
        _setStatus('Erro ao carregar histórico: ' + err.message, true);
      });
  }

  function confirmarRestaurar(upload) {
    var hora = _formatarHora(upload.criado_em);
    var usuario = upload.usuario_nome || 'usuário desconhecido';
    var msg = 'Vai desfazer o upload atual e voltar pro de ' + hora +
              ' (' + usuario + '). Os dados atuais NÃO serão perdidos — ' +
              'poderão ser restaurados depois. Confirmar?';
    if (!window.confirm(msg)) return;
    executarRestaurar(upload.id);
  }

  function executarRestaurar(uploadId) {
    _setStatus('Restaurando…', false);
    fetch('/api/uploads/' + encodeURIComponent(uploadId) + '/restaurar', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
    })
      .then(function (r) {
        return r.json().then(function (d) { return { ok: r.ok, body: d }; });
      })
      .then(function (res) {
        if (!res.ok) {
          var msg = (res.body && res.body.erro) || 'Erro ao restaurar.';
          _setStatus(msg, true);
          return;
        }
        carregar();
      })
      .catch(function (err) {
        _setStatus('Erro de rede ao restaurar: ' + err.message, true);
      });
  }

  document.addEventListener('DOMContentLoaded', carregar);
})();
