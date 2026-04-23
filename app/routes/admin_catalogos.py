"""Admin UI para gestao de catalogos (Gestor apenas)."""
from __future__ import annotations

import math

from flask import (
    Blueprint, flash, jsonify, redirect, render_template, request, url_for,
)
from flask_login import login_required
from werkzeug.wrappers.response import Response

from app.auth.decorators import role_required
from app.services import catalogo_service, triagem_missoes
from app.services.catalogo_types import (
    MissaoCreate, MissaoUpdate, MunicipioCreate, MunicipioUpdate,
)
from app.services.triagem_missoes import (
    MAX_DESCRICAO_LEN, MAX_NOME_LEN, MAX_TEXTO_LEN,
)

admin_catalogos_bp = Blueprint(
    "admin_catalogos", __name__, url_prefix="/admin/catalogos"
)


# ---------------------------------------------------------------------------
# Missoes
# ---------------------------------------------------------------------------


@admin_catalogos_bp.route("/missoes", methods=["GET"])
@login_required
@role_required(["gestor"])
def listar_missoes_view() -> str:
    q: str = (request.args.get("q") or "").strip()[:100]
    itens = catalogo_service.listar_missoes(
        q=q or None, somente_ativas=False, limite=500,
    )
    return render_template("admin/missoes.html", missoes=itens, q=q)


@admin_catalogos_bp.route("/missoes/criar", methods=["POST"])
@login_required
@role_required(["gestor"])
def criar_missao_view() -> Response:
    payload: MissaoCreate = {
        "nome": (request.form.get("nome") or "").strip(),
        "descricao": (request.form.get("descricao") or "").strip() or None,
    }
    try:
        catalogo_service.criar_missao(payload)
        flash("Missao criada", "info")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin_catalogos.listar_missoes_view"))


@admin_catalogos_bp.route("/missoes/<missao_id>/editar", methods=["POST"])
@login_required
@role_required(["gestor"])
def editar_missao_view(missao_id: str) -> Response:
    payload: MissaoUpdate = {}
    if "nome" in request.form:
        payload["nome"] = (request.form.get("nome") or "").strip()
    if "descricao" in request.form:
        payload["descricao"] = (request.form.get("descricao") or "").strip() or None
    ativo_raw: str = (request.form.get("ativo") or "").strip().lower()
    if ativo_raw in ("1", "true", "sim"):
        payload["ativo"] = True
    elif ativo_raw in ("0", "false", "nao"):
        payload["ativo"] = False
    try:
        catalogo_service.atualizar_missao(missao_id, payload)
        flash("Missao atualizada", "info")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin_catalogos.listar_missoes_view"))


# ---------------------------------------------------------------------------
# Municipios
# ---------------------------------------------------------------------------


@admin_catalogos_bp.route("/municipios", methods=["GET"])
@login_required
@role_required(["gestor"])
def listar_municipios_view() -> str:
    q: str = (request.args.get("q") or "").strip()[:100]
    crpm_id: str = (request.args.get("crpm") or "").strip()
    itens = catalogo_service.listar_municipios(
        crpm_id=crpm_id or None, q=q or None,
        somente_ativos=False, limite=1000,
    )
    crpms = catalogo_service.listar_crpms(somente_ativos=False)
    return render_template(
        "admin/municipios.html",
        municipios=itens, crpms=crpms, q=q, crpm_sel=crpm_id,
    )


@admin_catalogos_bp.route("/municipios/criar", methods=["POST"])
@login_required
@role_required(["gestor"])
def criar_municipio_view() -> Response:
    payload: MunicipioCreate = {
        "nome": (request.form.get("nome") or "").strip(),
        "crpm_id": (request.form.get("crpm_id") or "").strip(),
    }
    try:
        catalogo_service.criar_municipio(payload)
        flash("Municipio criado", "info")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin_catalogos.listar_municipios_view"))


@admin_catalogos_bp.route("/municipios/<municipio_id>/editar", methods=["POST"])
@login_required
@role_required(["gestor"])
def editar_municipio_view(municipio_id: str) -> Response:
    payload: MunicipioUpdate = {}
    if "nome" in request.form:
        payload["nome"] = (request.form.get("nome") or "").strip()
    if "crpm_id" in request.form:
        novo_crpm = (request.form.get("crpm_id") or "").strip()
        if novo_crpm:
            payload["crpm_id"] = novo_crpm
    ativo_raw: str = (request.form.get("ativo") or "").strip().lower()
    if ativo_raw in ("1", "true", "sim"):
        payload["ativo"] = True
    elif ativo_raw in ("0", "false", "nao"):
        payload["ativo"] = False
    try:
        catalogo_service.atualizar_municipio(municipio_id, payload)
        flash("Municipio atualizado", "info")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin_catalogos.listar_municipios_view"))


# ---------------------------------------------------------------------------
# CRPMs (somente leitura via UI)
# ---------------------------------------------------------------------------


@admin_catalogos_bp.route("/crpms", methods=["GET"])
@login_required
@role_required(["gestor"])
def listar_crpms_view() -> str:
    itens = catalogo_service.listar_crpms(somente_ativos=False)
    return render_template("admin/crpms.html", crpms=itens)


# ---------------------------------------------------------------------------
# Triagem de missoes (Fase 6.2.5)
# ---------------------------------------------------------------------------


_TRIAGEM_PAGE_SIZE: int = 20


def _catalogo_nome_para_id() -> dict[str, str]:
    """{nome_canonico: missao_id} das missoes ativas — usado para fuzzy."""
    return {
        m.nome: m.id
        for m in catalogo_service.listar_missoes(
            somente_ativas=True, limite=500,
        )
    }


@admin_catalogos_bp.route("/triagem-missoes", methods=["GET"])
@login_required
@role_required(["gestor"])
def listar_triagem_view() -> str:
    try:
        pagina: int = max(1, int(request.args.get("pagina", "1")))
    except ValueError:
        pagina = 1
    offset: int = (pagina - 1) * _TRIAGEM_PAGE_SIZE

    pendentes = triagem_missoes.agrupar_pendentes(
        limit=_TRIAGEM_PAGE_SIZE, offset=offset,
    )
    total: int = triagem_missoes.contar_pendentes()
    total_paginas: int = max(1, math.ceil(total / _TRIAGEM_PAGE_SIZE))

    catalogo: dict[str, str] = _catalogo_nome_para_id()
    itens: list[dict] = []
    for p in pendentes:
        candidatos = triagem_missoes.sugerir_candidatos(p.texto, catalogo)
        itens.append({
            "texto": p.texto, "freq": p.freq, "candidatos": candidatos,
        })
    return render_template(
        "admin/triagem_missoes.html",
        itens=itens, total=total,
        pagina=pagina, total_paginas=total_paginas,
        max_nome_len=MAX_NOME_LEN, max_descricao_len=MAX_DESCRICAO_LEN,
    )


@admin_catalogos_bp.route("/triagem-missoes/aplicar", methods=["POST"])
@login_required
@role_required(["gestor"])
def aplicar_triagem_view() -> Response | tuple[Response, int]:
    payload = request.get_json(silent=True) or request.form
    texto: str = str(payload.get("texto") or "").strip()[:MAX_TEXTO_LEN]
    missao_id: str = str(payload.get("missao_id") or "").strip()
    if not texto or not missao_id:
        return jsonify({"erro": "texto e missao_id obrigatorios"}), 400
    try:
        resultado = triagem_missoes.aplicar_mapeamento(texto, missao_id)
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 400
    return jsonify({
        "missao_id": resultado.missao_id,
        "missao_nome": resultado.missao_nome,
        "fracoes_atualizadas": resultado.fracoes_atualizadas,
    })


@admin_catalogos_bp.route("/triagem-missoes/nova", methods=["POST"])
@login_required
@role_required(["gestor"])
def criar_triagem_view() -> Response | tuple[Response, int]:
    payload = request.get_json(silent=True) or request.form
    texto: str = str(payload.get("texto") or "").strip()[:MAX_TEXTO_LEN]
    nome: str = str(payload.get("nome") or "").strip()[:MAX_NOME_LEN]
    descricao_raw = payload.get("descricao")
    descricao: str | None = None
    if isinstance(descricao_raw, str):
        descricao = descricao_raw.strip()[:MAX_DESCRICAO_LEN] or None
    if not texto or not nome:
        return jsonify({"erro": "texto e nome obrigatorios"}), 400
    try:
        resultado = triagem_missoes.criar_e_aplicar(nome, descricao, texto)
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 400
    return jsonify({
        "missao_id": resultado.missao_id,
        "missao_nome": resultado.missao_nome,
        "fracoes_atualizadas": resultado.fracoes_atualizadas,
    })


@admin_catalogos_bp.route("/triagem-missoes/desfazer", methods=["POST"])
@login_required
@role_required(["gestor"])
def desfazer_triagem_view() -> Response | tuple[Response, int]:
    payload = request.get_json(silent=True) or request.form
    texto: str = str(payload.get("texto") or "").strip()[:MAX_TEXTO_LEN]
    missao_id: str = str(payload.get("missao_id") or "").strip()
    remover_raw = payload.get("remover_missao", False)
    remover_missao: bool = bool(remover_raw) and str(remover_raw).lower() not in (
        "0", "false", "nao", "no",
    )
    if not texto or not missao_id:
        return jsonify({"erro": "texto e missao_id obrigatorios"}), 400
    try:
        resultado = triagem_missoes.desfazer_aplicacao(
            texto, missao_id, remover_missao=remover_missao,
        )
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 400
    return jsonify({
        "texto": resultado.texto,
        "missao_id": resultado.missao_id,
        "fracoes_revertidas": resultado.fracoes_revertidas,
        "missao_removida": resultado.missao_removida,
    })
