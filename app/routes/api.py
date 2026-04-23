from __future__ import annotations

import logging

from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required
from werkzeug.utils import secure_filename

from app.auth.decorators import role_required
from app.services.analytics_cabecalho import (
    calcular_indicadores,
    calcular_media_movel,
    calcular_sazonalidade,
    calcular_tendencia,
)
from app.services.analytics_fracoes import (
    analisar_cobertura_horaria,
    analisar_concentracao,
    analisar_fracoes_freq,
    analisar_missoes,
    analisar_padroes_diarios,
)
from app.services.db_service import (
    fetch_cabecalho_by_range,
    fetch_datas_disponiveis,
    fetch_fracoes_by_range,
    fetch_resumo_por_unidade,
    fetch_serie_temporal,
    fetch_unidades_disponiveis,
    save_cabecalho,
    save_fracoes,
)
from app.services.whatsapp_parser import calcular_horario_emprego, parse_texto_whatsapp
from app.services import catalogo_service

api_bp = Blueprint("api", __name__)
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS: frozenset[str] = frozenset({"xlsx", "xls"})


def _normalizar_data(data: str) -> str:
    """Converte yyyy-mm-dd para dd/mm/yyyy se necessario."""
    if len(data) == 10 and data[4] == "-":
        partes: list[str] = data.split("-")
        return f"{partes[2]}/{partes[1]}/{partes[0]}"
    return data


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _db_configurado() -> bool:
    return bool(current_app.config.get("DATABASE_URL"))


@api_bp.route("/upload", methods=["POST"])
@login_required
@role_required(["gestor", "operador_arei"])
def upload_xlsx() -> tuple:
    from app.services.xlsx_parser import parse_xlsx

    if "file" not in request.files:
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"erro": "Nome do arquivo vazio"}), 400

    safe_name: str = secure_filename(file.filename)
    if not _allowed_file(safe_name):
        return jsonify({"erro": "Formato invalido. Use .xlsx"}), 400

    file_bytes: bytes = file.read()
    if len(file_bytes) == 0:
        return jsonify({"erro": "Arquivo vazio"}), 400

    try:
        fracoes, cabecalho = parse_xlsx(file_bytes)
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 422

    salvo_no_banco: bool = False
    if _db_configurado():
        try:
            save_fracoes(fracoes)
            save_cabecalho(cabecalho)
            salvo_no_banco = True
        except Exception as exc:
            logger.warning("Erro ao salvar no banco: %s", exc)

    fracoes_serializable: list[dict] = [dict(row) for row in fracoes]
    cabecalho_serializable: list[dict] = [dict(row) for row in cabecalho]
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
@login_required
@role_required(["gestor", "operador_arei"])
def parse_texto() -> tuple:
    """Fase 5 - Parseia texto WhatsApp colado pelo operador."""
    body = request.get_json(silent=True)
    if not body or not body.get("texto", "").strip():
        return jsonify({"erro": "Campo 'texto' vazio"}), 400

    texto: str = body["texto"]
    if len(texto) > 50_000:
        return jsonify({"erro": "Texto excede 50 000 caracteres"}), 400

    try:
        resultado = parse_texto_whatsapp(texto)
    except Exception as exc:
        logger.error("Erro ao parsear texto WhatsApp: %s", exc)
        return jsonify({"erro": "Erro ao interpretar texto"}), 422

    fracoes: list[dict] = [dict(f) for f in resultado["fracoes"]]
    cabecalhos: list[dict] = [dict(c) for c in resultado["cabecalhos"]]

    return jsonify({
        "sucesso": True,
        "fracoes": fracoes,
        "cabecalhos": cabecalhos,
        "avisos": resultado["avisos"],
        "total_fracoes": len(fracoes),
        "total_cabecalhos": len(cabecalhos),
    }), 200


@api_bp.route("/salvar-texto", methods=["POST"])
@login_required
@role_required(["gestor", "operador_arei"])
def salvar_texto() -> tuple:
    """Fase 5 - Salva fracoes/cabecalho editados do preview no banco."""
    from app.validators.xlsx_validator import (
        validar_vertices_n_n, validate_cabecalho, validate_fracoes,
    )

    body = request.get_json(silent=True)
    if not body:
        return jsonify({"erro": "Body vazio"}), 400

    fracoes_raw = body.get("fracoes", [])
    cabecalhos_raw = body.get("cabecalhos", [])

    if not fracoes_raw:
        return jsonify({"erro": "Nenhuma fracao enviada"}), 400

    try:
        fracoes = validate_fracoes(fracoes_raw)
        cabecalho = validate_cabecalho(cabecalhos_raw)
        # Indice municipio_id -> crpm_sigla para aferir POA no validador N:N.
        muni_index: dict[str, str] = {}
        if _db_configurado():
            try:
                for m in catalogo_service.listar_municipios(limite=2000):
                    muni_index[m.id] = m.crpm_sigla
            except Exception as exc:
                logger.warning("Indice municipios/crpm indisponivel: %s", exc)
        validar_vertices_n_n(fracoes, municipios_index=muni_index)
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 422

    salvo_no_banco: bool = False
    if _db_configurado():
        try:
            save_fracoes(fracoes)
            save_cabecalho(cabecalho)
            salvo_no_banco = True
        except Exception as exc:
            logger.warning("Erro ao salvar no banco: %s", exc)

    fracoes_out: list[dict] = [dict(f) for f in fracoes]
    cabecalho_out: list[dict] = [dict(c) for c in cabecalho]
    calcular_horario_emprego(cabecalho_out, fracoes_out)
    _hidratar_bpm_codigos(fracoes_out)

    return jsonify({
        "sucesso": True,
        "fracoes": fracoes_out,
        "cabecalho": cabecalho_out,
        "total_fracoes": len(fracoes),
        "total_cabecalho": len(cabecalho),
        "salvo_no_banco": salvo_no_banco,
    }), 200


def _hidratar_bpm_codigos(fracoes: list[dict]) -> None:
    """Preenche `missao.bpm_codigos` (plural, Fase 6.4) a partir de `bpm_ids`.

    O preview envia so os UUIDs; o painel do analista precisa dos codigos pra
    renderizar chips/labels. Ignora ids nao resolvidos no cache silenciosamente
    — hidratacao e best-effort (defense in depth para rollouts parciais).
    """
    if not _db_configurado():
        return
    try:
        from app.services import bpm_service
        bpms = {b.id: b.codigo for b in bpm_service.listar_bpms()}
    except Exception as exc:
        logger.warning("Nao foi possivel hidratar BPMs: %s", exc)
        return
    for fr in fracoes:
        for m in fr.get("missoes") or []:
            if m.get("bpm_codigos"):
                continue
            ids: list[str] = list(m.get("bpm_ids") or [])
            codigos: list[str] = [bpms[i] for i in ids if i in bpms]
            m["bpm_codigos"] = codigos


@api_bp.route("/analista/filtros", methods=["GET"])
@login_required
def analista_filtros() -> tuple:
    if not _db_configurado():
        return jsonify({"erro": "Banco de dados nao configurado"}), 503

    try:
        datas: list[str] = fetch_datas_disponiveis()
        unidades: list[str] = fetch_unidades_disponiveis()
        return jsonify({"datas": datas, "unidades": unidades}), 200
    except Exception as exc:
        logger.error("Erro ao buscar filtros: %s", exc)
        return jsonify({"erro": "Erro ao buscar filtros"}), 500


@api_bp.route("/analista/dados", methods=["GET"])
@login_required
def analista_dados() -> tuple:
    if not _db_configurado():
        return jsonify({"erro": "Banco de dados nao configurado"}), 503

    data_inicio: str = _normalizar_data(request.args.get("data_inicio", ""))
    data_fim: str = _normalizar_data(request.args.get("data_fim", ""))
    unidades_param: str = request.args.get("unidades", "")

    if not data_inicio or not data_fim:
        return jsonify({"erro": "Parametros data_inicio e data_fim obrigatorios"}), 400

    unidades: list[str] = (
        [u.strip() for u in unidades_param.split(",") if u.strip()]
        if unidades_param else []
    )

    try:
        fracoes: list[dict] = fetch_fracoes_by_range(data_inicio, data_fim, unidades)
        cabecalho: list[dict] = fetch_cabecalho_by_range(data_inicio, data_fim, unidades)
        resumo: list[dict] = fetch_resumo_por_unidade(data_inicio, data_fim, unidades)
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
@login_required
def analista_serie() -> tuple:
    if not _db_configurado():
        return jsonify({"erro": "Banco de dados nao configurado"}), 503

    data_inicio: str = _normalizar_data(request.args.get("data_inicio", ""))
    data_fim: str = _normalizar_data(request.args.get("data_fim", ""))
    unidades_param: str = request.args.get("unidades", "")

    if not data_inicio or not data_fim:
        return jsonify({"erro": "Parametros data_inicio e data_fim obrigatorios"}), 400

    unidades: list[str] = (
        [u.strip() for u in unidades_param.split(",") if u.strip()]
        if unidades_param else []
    )

    try:
        serie: list[dict] = fetch_serie_temporal(data_inicio, data_fim, unidades)
        return jsonify({"serie": serie}), 200
    except Exception as exc:
        logger.error("Erro ao buscar serie temporal: %s", exc)
        return jsonify({"erro": "Erro ao buscar serie temporal"}), 500


@api_bp.route("/analista/projecoes", methods=["GET"])
@login_required
def analista_projecoes() -> tuple:
    """Fase 4 - Projecoes e indicadores de cabecalho (pandas/numpy)."""
    if not _db_configurado():
        return jsonify({"erro": "Banco de dados nao configurado"}), 503

    data_inicio: str = _normalizar_data(request.args.get("data_inicio", ""))
    data_fim: str = _normalizar_data(request.args.get("data_fim", ""))
    unidades_param: str = request.args.get("unidades", "")
    janela: str = request.args.get("janela", "7")

    if not data_inicio or not data_fim:
        return jsonify({"erro": "Parametros data_inicio e data_fim obrigatorios"}), 400

    try:
        janela_int: int = max(2, min(int(janela), 30))
    except (ValueError, TypeError):
        janela_int = 7

    unidades: list[str] = (
        [u.strip() for u in unidades_param.split(",") if u.strip()]
        if unidades_param else []
    )

    try:
        cabecalho: list[dict] = fetch_cabecalho_by_range(data_inicio, data_fim, unidades)
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
@login_required
def analista_fracoes_analytics() -> tuple:
    """Fase 4 - Analytics de fracoes (missoes, cobertura, padroes)."""
    if not _db_configurado():
        return jsonify({"erro": "Banco de dados nao configurado"}), 503

    data_inicio: str = _normalizar_data(request.args.get("data_inicio", ""))
    data_fim: str = _normalizar_data(request.args.get("data_fim", ""))
    unidades_param: str = request.args.get("unidades", "")

    if not data_inicio or not data_fim:
        return jsonify({"erro": "Parametros data_inicio e data_fim obrigatorios"}), 400

    unidades: list[str] = (
        [u.strip() for u in unidades_param.split(",") if u.strip()]
        if unidades_param else []
    )

    try:
        fracoes: list[dict] = fetch_fracoes_by_range(data_inicio, data_fim, unidades)
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


# Catalogos + analytics 6.2/6.3 extraidos para app/routes/api_catalogos.py
# (mantem este arquivo <= 500 LOC). Blueprint registrado em app/__init__.py.
