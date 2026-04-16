import logging
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from app.services.xlsx_parser import parse_xlsx
from app.services.supabase_service import (
    save_fracoes,
    save_cabecalho,
    fetch_fracoes_by_range,
    fetch_cabecalho_by_range,
    fetch_datas_disponiveis,
    fetch_unidades_disponiveis,
    fetch_resumo_por_unidade,
    fetch_serie_temporal,
)
from app.services.analytics_cabecalho import (
    calcular_media_movel,
    calcular_tendencia,
    calcular_sazonalidade,
    calcular_indicadores,
)
from app.services.whatsapp_parser import parse_texto_whatsapp, calcular_horario_emprego
from app.services.analytics_fracoes import (
    analisar_missoes,
    analisar_fracoes_freq,
    analisar_cobertura_horaria,
    analisar_padroes_diarios,
    analisar_concentracao,
)

api_bp = Blueprint("api", __name__)
logger = logging.getLogger(__name__)


def _normalizar_data(data: str) -> str:
    """Converte yyyy-mm-dd para dd/mm/yyyy se necessario."""
    if len(data) == 10 and data[4] == "-":
        partes = data.split("-")
        return f"{partes[2]}/{partes[1]}/{partes[0]}"
    return data

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
    calcular_horario_emprego(cabecalho_serializable, fracoes_serializable)

    return jsonify({
        "sucesso": True,
        "fracoes": fracoes_serializable,
        "cabecalho": cabecalho_serializable,
        "total_fracoes": len(fracoes),
        "total_cabecalho": len(cabecalho),
        "salvo_no_banco": salvo_no_banco,
    }), 200


@api_bp.route("/parse-texto", methods=["POST"])
def parse_texto() -> tuple:
    """Fase 5 — Parseia texto WhatsApp colado pelo operador."""
    body = request.get_json(silent=True)
    if not body or not body.get("texto", "").strip():
        return jsonify({"erro": "Campo 'texto' vazio"}), 400

    texto = body["texto"]
    if len(texto) > 50_000:
        return jsonify({"erro": "Texto excede 50 000 caracteres"}), 400

    try:
        resultado = parse_texto_whatsapp(texto)
    except Exception as exc:
        logger.error("Erro ao parsear texto WhatsApp: %s", exc)
        return jsonify({"erro": "Erro ao interpretar texto"}), 422

    fracoes = [dict(f) for f in resultado["fracoes"]]
    cabecalhos = [dict(c) for c in resultado["cabecalhos"]]

    return jsonify({
        "sucesso": True,
        "fracoes": fracoes,
        "cabecalhos": cabecalhos,
        "avisos": resultado["avisos"],
        "total_fracoes": len(fracoes),
        "total_cabecalhos": len(cabecalhos),
    }), 200


@api_bp.route("/salvar-texto", methods=["POST"])
def salvar_texto() -> tuple:
    """Fase 5 — Salva fracoes/cabecalho editados do preview no Supabase."""
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"erro": "Body vazio"}), 400

    fracoes_raw = body.get("fracoes", [])
    cabecalhos_raw = body.get("cabecalhos", [])

    if not fracoes_raw:
        return jsonify({"erro": "Nenhuma fracao enviada"}), 400

    from app.validators.xlsx_validator import validate_fracoes, validate_cabecalho

    try:
        fracoes = validate_fracoes(fracoes_raw)
        cabecalho = validate_cabecalho(cabecalhos_raw)
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

    fracoes_out = [dict(f) for f in fracoes]
    cabecalho_out = [dict(c) for c in cabecalho]
    calcular_horario_emprego(cabecalho_out, fracoes_out)

    return jsonify({
        "sucesso": True,
        "fracoes": fracoes_out,
        "cabecalho": cabecalho_out,
        "total_fracoes": len(fracoes),
        "total_cabecalho": len(cabecalho),
        "salvo_no_banco": salvo_no_banco,
    }), 200


@api_bp.route("/analista/filtros", methods=["GET"])
def analista_filtros() -> tuple:
    if not current_app.config.get("SUPABASE_DB_URL"):
        return jsonify({"erro": "Banco de dados nao configurado"}), 503

    try:
        datas = fetch_datas_disponiveis()
        unidades = fetch_unidades_disponiveis()
        return jsonify({"datas": datas, "unidades": unidades}), 200
    except Exception as exc:
        logger.error("Erro ao buscar filtros: %s", exc)
        return jsonify({"erro": "Erro ao buscar filtros"}), 500


@api_bp.route("/analista/dados", methods=["GET"])
def analista_dados() -> tuple:
    if not current_app.config.get("SUPABASE_DB_URL"):
        return jsonify({"erro": "Banco de dados nao configurado"}), 503

    data_inicio = _normalizar_data(request.args.get("data_inicio", ""))
    data_fim = _normalizar_data(request.args.get("data_fim", ""))
    unidades_param = request.args.get("unidades", "")

    if not data_inicio or not data_fim:
        return jsonify({"erro": "Parametros data_inicio e data_fim obrigatorios"}), 400

    unidades = [u.strip() for u in unidades_param.split(",") if u.strip()] if unidades_param else []

    try:
        fracoes = fetch_fracoes_by_range(data_inicio, data_fim, unidades)
        cabecalho = fetch_cabecalho_by_range(data_inicio, data_fim, unidades)
        resumo = fetch_resumo_por_unidade(data_inicio, data_fim, unidades)
        return jsonify({
            "fracoes": fracoes,
            "cabecalho": cabecalho,
            "resumo": resumo,
            "total_fracoes": len(fracoes),
            "total_cabecalho": len(cabecalho),
        }), 200
    except Exception as exc:
        logger.error("Erro ao buscar dados analista: %s", exc)
        return jsonify({"erro": "Erro ao buscar dados"}), 500


@api_bp.route("/analista/serie", methods=["GET"])
def analista_serie() -> tuple:
    if not current_app.config.get("SUPABASE_DB_URL"):
        return jsonify({"erro": "Banco de dados nao configurado"}), 503

    data_inicio = _normalizar_data(request.args.get("data_inicio", ""))
    data_fim = _normalizar_data(request.args.get("data_fim", ""))
    unidades_param = request.args.get("unidades", "")

    if not data_inicio or not data_fim:
        return jsonify({"erro": "Parametros data_inicio e data_fim obrigatorios"}), 400

    unidades = [u.strip() for u in unidades_param.split(",") if u.strip()] if unidades_param else []

    try:
        serie = fetch_serie_temporal(data_inicio, data_fim, unidades)
        return jsonify({"serie": serie}), 200
    except Exception as exc:
        logger.error("Erro ao buscar serie temporal: %s", exc)
        return jsonify({"erro": "Erro ao buscar serie temporal"}), 500


@api_bp.route("/analista/projecoes", methods=["GET"])
def analista_projecoes() -> tuple:
    """Fase 4 — Projecoes e indicadores de cabecalho (pandas/numpy)."""
    if not current_app.config.get("SUPABASE_DB_URL"):
        return jsonify({"erro": "Banco de dados nao configurado"}), 503

    data_inicio = _normalizar_data(request.args.get("data_inicio", ""))
    data_fim = _normalizar_data(request.args.get("data_fim", ""))
    unidades_param = request.args.get("unidades", "")
    janela = request.args.get("janela", "7")

    if not data_inicio or not data_fim:
        return jsonify({"erro": "Parametros data_inicio e data_fim obrigatorios"}), 400

    try:
        janela_int = max(2, min(int(janela), 30))
    except (ValueError, TypeError):
        janela_int = 7

    unidades = [u.strip() for u in unidades_param.split(",") if u.strip()] if unidades_param else []

    try:
        cabecalho = fetch_cabecalho_by_range(data_inicio, data_fim, unidades)
        return jsonify({
            "media_movel": calcular_media_movel(cabecalho, janela_int),
            "tendencia": calcular_tendencia(cabecalho),
            "sazonalidade": calcular_sazonalidade(cabecalho),
            "indicadores": calcular_indicadores(cabecalho),
        }), 200
    except Exception as exc:
        logger.error("Erro ao calcular projecoes: %s", exc)
        return jsonify({"erro": "Erro ao calcular projecoes"}), 500


@api_bp.route("/analista/fracoes-analytics", methods=["GET"])
def analista_fracoes_analytics() -> tuple:
    """Fase 4 — Analytics de fracoes (missoes, cobertura, padroes)."""
    if not current_app.config.get("SUPABASE_DB_URL"):
        return jsonify({"erro": "Banco de dados nao configurado"}), 503

    data_inicio = _normalizar_data(request.args.get("data_inicio", ""))
    data_fim = _normalizar_data(request.args.get("data_fim", ""))
    unidades_param = request.args.get("unidades", "")

    if not data_inicio or not data_fim:
        return jsonify({"erro": "Parametros data_inicio e data_fim obrigatorios"}), 400

    unidades = [u.strip() for u in unidades_param.split(",") if u.strip()] if unidades_param else []

    try:
        fracoes = fetch_fracoes_by_range(data_inicio, data_fim, unidades)
        return jsonify({
            "missoes": analisar_missoes(fracoes),
            "fracoes_freq": analisar_fracoes_freq(fracoes),
            "cobertura_horaria": analisar_cobertura_horaria(fracoes),
            "padroes_diarios": analisar_padroes_diarios(fracoes),
            "concentracao": analisar_concentracao(fracoes),
        }), 200
    except Exception as exc:
        logger.error("Erro ao calcular analytics fracoes: %s", exc)
        return jsonify({"erro": "Erro ao calcular analytics de fracoes"}), 500
