"""Tela de administracao de usuarios (Gestor apenas)."""
from __future__ import annotations

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import login_required
from werkzeug.wrappers.response import Response

from app.auth.decorators import role_required
from app.models.user import ROLES_VALIDOS, Role
from app.services import unidade_service, user_service
from app.services.user_service import UsuarioCreate, UsuarioFiltro, UsuarioUpdate

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _parse_filtro(args) -> UsuarioFiltro:
    filtro: UsuarioFiltro = {}
    role_raw: str = (args.get("role") or "").strip()
    if role_raw and role_raw in ROLES_VALIDOS:
        filtro["role"] = role_raw  # type: ignore[typeddict-item]
    unidade_raw: str = (args.get("unidade") or "").strip()
    if unidade_raw:
        filtro["unidade"] = unidade_raw
    ativo_raw: str = (args.get("ativo") or "").strip().lower()
    if ativo_raw in ("1", "true", "sim"):
        filtro["ativo"] = True
    elif ativo_raw in ("0", "false", "nao"):
        filtro["ativo"] = False
    return filtro


@admin_bp.route("/usuarios", methods=["GET"])
@login_required
@role_required(["gestor"])
def listar_usuarios() -> str:
    filtro = _parse_filtro(request.args)
    usuarios = user_service.listar(filtro)
    return render_template(
        "admin/usuarios.html",
        usuarios=usuarios,
        roles=sorted(ROLES_VALIDOS),
        unidades=sorted(u.nome for u in unidade_service.listar_unidades()),
        filtro=filtro,
    )


@admin_bp.route("/usuarios/criar", methods=["POST"])
@login_required
@role_required(["gestor"])
def criar_usuario() -> Response:
    role_raw: str = (request.form.get("role") or "").strip()
    if role_raw not in ROLES_VALIDOS:
        flash("Role invalido", "error")
        return redirect(url_for("admin.listar_usuarios"))

    unidade_raw: str | None = (request.form.get("unidade") or "").strip() or None
    payload: UsuarioCreate = {
        "nome": (request.form.get("nome") or "").strip(),
        "email": (request.form.get("email") or "").strip().lower(),
        "senha": request.form.get("senha") or "",
        "role": role_raw,  # type: ignore[typeddict-item]
        "unidade": unidade_raw,
    }
    try:
        user_service.create(payload)
        flash("Usuario criado", "info")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin.listar_usuarios"))


@admin_bp.route("/usuarios/<user_id>/editar", methods=["POST"])
@login_required
@role_required(["gestor"])
def editar_usuario(user_id: str) -> Response:
    payload: UsuarioUpdate = {}
    for campo in ("nome", "email", "unidade"):
        valor = request.form.get(campo)
        if valor is not None:
            payload[campo] = valor.strip() or None  # type: ignore[literal-required]
    role_raw = (request.form.get("role") or "").strip()
    if role_raw:
        if role_raw not in ROLES_VALIDOS:
            flash("Role invalido", "error")
            return redirect(url_for("admin.listar_usuarios"))
        payload["role"] = role_raw  # type: ignore[typeddict-item]

    try:
        user_service.update(user_id, payload)
        flash("Usuario atualizado", "info")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin.listar_usuarios"))


@admin_bp.route("/usuarios/<user_id>/desativar", methods=["POST"])
@login_required
@role_required(["gestor"])
def desativar_usuario(user_id: str) -> Response:
    user_service.desativar(user_id)
    flash("Usuario desativado", "info")
    return redirect(url_for("admin.listar_usuarios"))


@admin_bp.route("/usuarios/<user_id>/resetar-2fa", methods=["POST"])
@login_required
@role_required(["gestor"])
def resetar_2fa(user_id: str) -> Response:
    user_service.resetar_2fa(user_id)
    flash("2FA resetado; usuario configurara no proximo login", "info")
    return redirect(url_for("admin.listar_usuarios"))
