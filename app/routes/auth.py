"""Rotas de autenticacao: login, 2FA, setup 2FA, logout."""
from __future__ import annotations

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.wrappers.response import Response

from app.extensions import limiter
from app.services import totp_service, user_service
from app.services.user_service import SENHA_MIN_LEN  # noqa: F401  (exposto em testes)

auth_bp = Blueprint("auth", __name__)

_LIMITE_LOGIN: str = "5 per minute"

_SESSION_PENDING_USER: str = "pending_2fa_user_id"


def _post_login(user_id: str) -> Response:
    user = user_service.get_by_id(user_id)
    if user is None or not user.ativo:
        flash("Usuario indisponivel", "error")
        return redirect(url_for("auth.login"))
    session.permanent = True
    login_user(user)
    user_service.registrar_login(user.id)
    return redirect(url_for("operador.index"))


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit(_LIMITE_LOGIN, methods=["POST"])
def login() -> Response | str:
    if current_user.is_authenticated:
        return redirect(url_for("operador.index"))

    if request.method == "POST":
        email: str = (request.form.get("email") or "").strip()
        senha: str = request.form.get("senha") or ""
        if not email or not senha:
            flash("Informe email e senha", "error")
            return render_template("auth/login.html"), 400

        try:
            user = user_service.verificar_senha(email, senha)
        except Exception as exc:  # banco fora do ar, etc.
            current_app.logger.error("Erro em login: %s", exc)
            flash("Erro interno. Tente novamente.", "error")
            return render_template("auth/login.html"), 500

        if user is None:
            flash("Credenciais invalidas", "error")
            return render_template("auth/login.html"), 401

        # 2FA obrigatorio para gestor/arei; configurar no primeiro acesso.
        if user.requer_2fa() and not user.totp_ativo:
            session[_SESSION_PENDING_USER] = user.id
            return redirect(url_for("auth.setup_2fa"))

        # 2FA ativo (qualquer role): pede codigo.
        if user.totp_ativo:
            session[_SESSION_PENDING_USER] = user.id
            return redirect(url_for("auth.login_2fa"))

        # ALEI sem 2FA: entra direto.
        return _post_login(user.id)

    return render_template("auth/login.html")


@auth_bp.route("/login/2fa", methods=["GET", "POST"])
@limiter.limit(_LIMITE_LOGIN, methods=["POST"])
def login_2fa() -> Response | str:
    user_id: str | None = session.get(_SESSION_PENDING_USER)
    if not user_id:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        codigo: str = request.form.get("codigo") or ""
        secret = user_service.get_totp_secret(user_id)
        if secret is None:
            session.pop(_SESSION_PENDING_USER, None)
            flash("Configuracao 2FA invalida", "error")
            return redirect(url_for("auth.login"))

        if not totp_service.verificar_codigo(secret, codigo):
            flash("Codigo invalido", "error")
            return render_template("auth/login_2fa.html"), 401

        session.pop(_SESSION_PENDING_USER, None)
        return _post_login(user_id)

    return render_template("auth/login_2fa.html")


@auth_bp.route("/setup-2fa", methods=["GET", "POST"])
def setup_2fa() -> Response | str:
    user_id: str | None = session.get(_SESSION_PENDING_USER)
    if not user_id:
        return redirect(url_for("auth.login"))

    user = user_service.get_by_id(user_id)
    if user is None:
        session.pop(_SESSION_PENDING_USER, None)
        return redirect(url_for("auth.login"))

    secret: str | None = user_service.get_totp_secret(user.id)
    if secret is None:
        secret = totp_service.gerar_secret()
        user_service.set_totp_secret(user.id, secret, ativar=False)

    if request.method == "POST":
        codigo: str = request.form.get("codigo") or ""
        if not totp_service.verificar_codigo(secret, codigo):
            uri = totp_service.uri_provisionamento(secret, user.email)
            return render_template(
                "auth/setup_2fa.html",
                qr_data=totp_service.qr_png_base64(uri),
                secret_manual=secret,
                erro="Codigo invalido, tente novamente",
            ), 401

        user_service.set_totp_secret(user.id, secret, ativar=True)
        session.pop(_SESSION_PENDING_USER, None)
        return _post_login(user.id)

    uri = totp_service.uri_provisionamento(secret, user.email)
    return render_template(
        "auth/setup_2fa.html",
        qr_data=totp_service.qr_png_base64(uri),
        secret_manual=secret,
        erro=None,
    )


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout() -> Response:
    logout_user()
    session.clear()
    flash("Sessao encerrada", "info")
    return redirect(url_for("auth.login"))
