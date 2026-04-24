from __future__ import annotations

from datetime import date

from flask import Blueprint, abort, render_template
from flask_login import login_required

from app.auth.decorators import role_required
from app.models.user import UNIDADES_VALIDAS

operador_bp = Blueprint("operador", __name__)

_DIAS_SEMANA_PT: tuple[str, ...] = (
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
)


def _contexto_hoje() -> dict[str, str]:
    """Data + dia-da-semana no padrão pt-BR — fonte única server-side."""
    hoje: date = date.today()
    return {
        "hoje_data": hoje.strftime("%d/%m/%Y"),
        "hoje_dia_semana": _DIAS_SEMANA_PT[hoje.weekday()],
    }


@operador_bp.route("/")
@login_required
def index() -> str:
    return render_template("operador/index.html", **_contexto_hoje())


@operador_bp.route("/operador")
@login_required
@role_required(["gestor", "operador_arei"])
def operador() -> str:
    return render_template("operador/index.html", **_contexto_hoje())


@operador_bp.route("/operador/historico/<unidade>/<path:data>")
@login_required
@role_required(["gestor", "operador_arei"])
def historico(unidade: str, data: str) -> str:
    """Histórico de uploads versionados de uma (unidade, data). Dados via JS.

    Valida formato no path pra evitar rotas abusivas (XSS em template).
    Unidade deve estar em UNIDADES_VALIDAS; data em dd/mm/yyyy (10 chars).
    O converter `<path:data>` aceita `/` dentro do segmento — necessario pro
    formato dd/mm/yyyy; por isso a validacao abaixo e rigida.
    """
    if unidade not in UNIDADES_VALIDAS:
        abort(404)
    if (
        len(data) != 10 or data[2] != "/" or data[5] != "/"
        or not data[0:2].isdigit() or not data[3:5].isdigit()
        or not data[6:10].isdigit()
    ):
        abort(404)
    return render_template(
        "operador/historico.html",
        unidade=unidade,
        data=data,
        **_contexto_hoje(),
    )
