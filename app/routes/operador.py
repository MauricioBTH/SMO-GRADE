from __future__ import annotations

from flask import Blueprint, render_template
from flask_login import login_required

from app.auth.decorators import role_required

operador_bp = Blueprint("operador", __name__)


@operador_bp.route("/")
@login_required
def index() -> str:
    return render_template("operador/index.html")


@operador_bp.route("/operador")
@login_required
@role_required(["gestor", "operador_arei", "operador_alei"])
def operador() -> str:
    return render_template("operador/index.html")
