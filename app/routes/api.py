import logging
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from app.services.xlsx_parser import parse_xlsx
from app.services.supabase_service import save_fracoes, save_cabecalho

api_bp = Blueprint("api", __name__)
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = frozenset({"xlsx", "xls"})


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@api_bp.route("/upload", methods=["POST"])
def upload_xlsx() -> tuple:
    if "file" not in request.files:
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"erro": "Nome do arquivo vazio"}), 400

    safe_name = secure_filename(file.filename)
    if not _allowed_file(safe_name):
        return jsonify({"erro": "Formato invalido. Use .xlsx"}), 400

    file_bytes = file.read()
    if len(file_bytes) == 0:
        return jsonify({"erro": "Arquivo vazio"}), 400

    try:
        fracoes, cabecalho = parse_xlsx(file_bytes)
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 422

    db_disponivel = bool(current_app.config.get("SUPABASE_DB_URL"))
    salvo_no_banco = False

    if db_disponivel:
        try:
            save_fracoes(fracoes)
            save_cabecalho(cabecalho)
            salvo_no_banco = True
        except Exception as exc:
            logger.warning("Erro ao salvar no Supabase: %s", exc)

    fracoes_serializable = [dict(row) for row in fracoes]
    cabecalho_serializable = [dict(row) for row in cabecalho]

    return jsonify({
        "sucesso": True,
        "fracoes": fracoes_serializable,
        "cabecalho": cabecalho_serializable,
        "total_fracoes": len(fracoes),
        "total_cabecalho": len(cabecalho),
        "salvo_no_banco": salvo_no_banco,
    }), 200
