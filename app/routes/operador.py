from flask import Blueprint, render_template

operador_bp = Blueprint("operador", __name__)


@operador_bp.route("/")
def index() -> str:
    return render_template("operador/index.html")


@operador_bp.route("/operador")
def operador() -> str:
    return render_template("operador/index.html")
