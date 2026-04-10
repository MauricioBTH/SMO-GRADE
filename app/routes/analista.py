from flask import Blueprint, render_template

analista_bp = Blueprint("analista", __name__)


@analista_bp.route("/analista")
def analista() -> str:
    return render_template("analista/index.html")
