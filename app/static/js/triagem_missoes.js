"use strict";

// Frontend burro: abre/fecha modal, faz POST, mostra banner de desfazer.
// URLs vem do backend via window.SMO_TRIAGEM.

const UNDO_WINDOW_MS = 15000;

let ultimaAcao = null;   // { texto, missao_id, missao_nome, fracoes, foiNova }
let undoTimer = null;
let tickTimer = null;

function abrirModal(texto) {
  const dialog = document.getElementById("modal-nova");
  document.getElementById("modal-texto").textContent = texto;
  document.getElementById("form-nova").reset();
  document.getElementById("modal-input-texto").value = texto;
  dialog.showModal();
}

function fecharModal() {
  document.getElementById("modal-nova").close();
}

async function _post(url, payload) {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const erro = await resp.json().catch(() => ({ erro: "falha" }));
    alert("Erro: " + (erro.erro || resp.status));
    return null;
  }
  return await resp.json();
}

function _esconderBanner() {
  document.getElementById("banner-undo").classList.remove("visivel");
  if (undoTimer) { clearTimeout(undoTimer); undoTimer = null; }
  if (tickTimer) { clearInterval(tickTimer); tickTimer = null; }
}

function _mostrarBanner(acao) {
  ultimaAcao = acao;
  const banner = document.getElementById("banner-undo");
  const msg = document.getElementById("banner-msg");
  const timerEl = document.getElementById("banner-timer");
  const sufixo = acao.foiNova ? " (missao criada)" : "";
  msg.textContent = acao.missao_nome + " aplicada a " + acao.fracoes +
    " fracao(oes)" + sufixo + ".";

  banner.classList.add("visivel");
  let restante = Math.floor(UNDO_WINDOW_MS / 1000);
  timerEl.textContent = restante + "s";
  if (tickTimer) clearInterval(tickTimer);
  tickTimer = setInterval(() => {
    restante -= 1;
    timerEl.textContent = restante + "s";
    if (restante <= 0) clearInterval(tickTimer);
  }, 1000);

  if (undoTimer) clearTimeout(undoTimer);
  undoTimer = setTimeout(() => { window.location.reload(); }, UNDO_WINDOW_MS);
}

async function aplicar(texto, missaoId) {
  const resp = await _post(window.SMO_TRIAGEM.aplicarUrl, {
    texto: texto, missao_id: missaoId,
  });
  if (!resp) return;
  _mostrarBanner({
    texto: texto, missao_id: resp.missao_id,
    missao_nome: resp.missao_nome, fracoes: resp.fracoes_atualizadas,
    foiNova: false,
  });
}

async function criar(form) {
  const dados = new FormData(form);
  const resp = await _post(window.SMO_TRIAGEM.novaUrl, {
    texto: dados.get("texto"),
    nome: dados.get("nome"),
    descricao: dados.get("descricao") || null,
  });
  if (!resp) return;
  fecharModal();
  _mostrarBanner({
    texto: dados.get("texto"), missao_id: resp.missao_id,
    missao_nome: resp.missao_nome, fracoes: resp.fracoes_atualizadas,
    foiNova: true,
  });
}

async function desfazerUltima() {
  if (!ultimaAcao) return;
  _esconderBanner();
  const resp = await _post(window.SMO_TRIAGEM.desfazerUrl, {
    texto: ultimaAcao.texto,
    missao_id: ultimaAcao.missao_id,
    remover_missao: ultimaAcao.foiNova,
  });
  if (!resp) return;
  window.location.reload();
}
