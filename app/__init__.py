from __future__ import annotations

from flask import Flask, redirect, url_for
from werkzeug.wrappers.response import Response

from app.config import Config
from app.extensions import limiter, login_manager
from app.models.user import User
from app.services import user_service


@login_manager.user_loader
def _load_user(user_id: str) -> User | None:
    try:
        return user_service.get_by_id(user_id)
    except Exception:
        return None


@login_manager.unauthorized_handler
def _unauthorized() -> Response:
    return redirect(url_for("auth.login"))


def create_app() -> Flask:
    flask_app: Flask = Flask(__name__)
    flask_app.config.from_object(Config)

    login_manager.init_app(flask_app)
    login_manager.login_view = "auth.login"
    login_manager.session_protection = "strong"

    limiter.init_app(flask_app)
    if flask_app.config.get("TESTING"):
        flask_app.config["RATELIMIT_ENABLED"] = False
        limiter.enabled = False

    from app.routes.admin import admin_bp
    from app.routes.analista import analista_bp
    from app.routes.api import api_bp
    from app.routes.auth import auth_bp
    from app.routes.operador import operador_bp

    flask_app.register_blueprint(auth_bp)
    flask_app.register_blueprint(admin_bp)
    flask_app.register_blueprint(operador_bp)
    flask_app.register_blueprint(analista_bp)
    flask_app.register_blueprint(api_bp, url_prefix="/api")

    return flask_app
