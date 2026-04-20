from __future__ import annotations

from flask import Blueprint, render_template
from flask_login import login_required

analista_bp = Blueprint("analista", __name__)


@analista_bp.route("/analista")
@login_required
def analista() -> str:
    return render_template("analista/index.html")
