"""Blueprint de rotas de catalogo + analytics por catalogo (Fase 6.2/6.3).

Separado de api.py para manter cada arquivo <= 500 LOC. Todas montadas sob
`/api` (registrado em app/__init__.py com `url_prefix="/api"`). Consumidores
atuais: dashboard analista (projecoes.js) e preview do operador
(preview_missoes.js).
"""
from __future__ import annotations

import logging

from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required

from app.services import bpm_service, catalogo_service
from app.services.analytics_catalogos import (
    agregar_normalizado_por_missao,
    agregar_por_missao, agregar_por_municipio,
    saude_catalogacao,
)
from app.services.db_service import fetch_vertices_by_range

api_catalogos_bp = Blueprint("api_catalogos", __name__)
logger = logging.getLogger(__name__)


def _db_configurado() -> bool:
    return bool(current_app.config.get("DATABASE_URL"))


def _normalizar_data(data: str) -> str:
    if len(data) == 10 and data[4] == "-":
        p = data.split("-")
        return f"{p[2]}/{p[1]}/{p[0]}"
    return data


def _parse_unidades_param(raw: str) -> list[str]:
    return [u.strip() for u in raw.split(",") if u.strip()] if raw else []


# ---------------------------------------------------------------------------
# Catalogos (autocomplete — leitura publica aos autenticados)
# ---------------------------------------------------------------------------


@api_catalogos_bp.route("/catalogos/missoes", methods=["GET"])
@login_required
def catalogos_missoes() -> tuple:
    q: str = (request.args.get("q") or "").strip()[:100]
    try:
        itens = catalogo_service.listar_missoes(q=q or None, limite=200)
        return jsonify({
            "missoes": [
                {"id": m.id, "nome": m.nome, "descricao": m.descricao}
                for m in itens
            ]
        }), 200
    except Exception as exc:
        logger.error("Erro ao listar missoes: %s", exc)
        return jsonify({"erro": "Erro ao listar missoes"}), 500


@api_catalogos_bp.route("/catalogos/municipios", methods=["GET"])
@login_required
def catalogos_municipios() -> tuple:
    q: str = (request.args.get("q") or "").strip()[:100]
    crpm_id: str = (request.args.get("crpm") or "").strip()
    try:
        itens = catalogo_service.listar_municipios(
            crpm_id=crpm_id or None, q=q or None, limite=2000,
        )
        return jsonify({
            "municipios": [
                {
                    "id": m.id, "nome": m.nome,
                    "crpm_id": m.crpm_id, "crpm_sigla": m.crpm_sigla,
                }
                for m in itens
            ]
        }), 200
    except Exception as exc:
        logger.error("Erro ao listar municipios: %s", exc)
        return jsonify({"erro": "Erro ao listar municipios"}), 500


@api_catalogos_bp.route("/catalogos/bpms", methods=["GET"])
@login_required
def catalogos_bpms() -> tuple:
    """Lista BPMs (6.3). Filtro opcional `municipio` restringe ao municipio."""
    municipio_id: str = (request.args.get("municipio") or "").strip()
    try:
        itens = (
            bpm_service.listar_bpms_por_municipio(municipio_id)
            if municipio_id else bpm_service.listar_bpms()
        )
        return jsonify({
            "bpms": [
                {
                    "id": b.id, "codigo": b.codigo,
                    "numero": b.numero, "municipio_id": b.municipio_id,
                }
                for b in itens
            ]
        }), 200
    except Exception as exc:
        logger.error("Erro ao listar bpms: %s", exc)
        return jsonify({"erro": "Erro ao listar bpms"}), 500


@api_catalogos_bp.route("/catalogos/crpms", methods=["GET"])
@login_required
def catalogos_crpms() -> tuple:
    try:
        itens = catalogo_service.listar_crpms()
        return jsonify({
            "crpms": [
                {
                    "id": c.id, "sigla": c.sigla, "nome": c.nome,
                    "sede": c.sede, "ordem": c.ordem,
                }
                for c in itens
            ]
        }), 200
    except Exception as exc:
        logger.error("Erro ao listar crpms: %s", exc)
        return jsonify({"erro": "Erro ao listar crpms"}), 500


# ---------------------------------------------------------------------------
# Analytics por catalogo (3 camadas da Fase 6.3)
# ---------------------------------------------------------------------------


def _args_periodo() -> tuple[str, str, list[str]] | None:
    data_inicio: str = _normalizar_data(request.args.get("data_inicio", ""))
    data_fim: str = _normalizar_data(request.args.get("data_fim", ""))
    if not data_inicio or not data_fim:
        return None
    unidades: list[str] = _parse_unidades_param(request.args.get("unidades", ""))
    return data_inicio, data_fim, unidades


@api_catalogos_bp.route("/analytics/por-missao", methods=["GET"])
@login_required
def analytics_por_missao() -> tuple:
    if not _db_configurado():
        return jsonify({"erro": "Banco de dados nao configurado"}), 503
    args = _args_periodo()
    if args is None:
        return jsonify({"erro": "Parametros data_inicio e data_fim obrigatorios"}), 400
    try:
        vertices = fetch_vertices_by_range(*args)
        return jsonify({"por_missao": agregar_por_missao(vertices)}), 200
    except Exception as exc:
        logger.error("Erro analytics por missao: %s", exc)
        return jsonify({"erro": "Erro ao agregar por missao"}), 500


@api_catalogos_bp.route("/analytics/por-municipio", methods=["GET"])
@login_required
def analytics_por_municipio() -> tuple:
    if not _db_configurado():
        return jsonify({"erro": "Banco de dados nao configurado"}), 503
    args = _args_periodo()
    if args is None:
        return jsonify({"erro": "Parametros data_inicio e data_fim obrigatorios"}), 400
    try:
        vertices = fetch_vertices_by_range(*args)
        return jsonify({"por_municipio": agregar_por_municipio(vertices)}), 200
    except Exception as exc:
        logger.error("Erro analytics por municipio: %s", exc)
        return jsonify({"erro": "Erro ao agregar por municipio"}), 500


@api_catalogos_bp.route("/analytics/normalizado", methods=["GET"])
@login_required
def analytics_normalizado() -> tuple:
    """Camada normalizada (6.3): agrupa variantes textuais de missao."""
    if not _db_configurado():
        return jsonify({"erro": "Banco de dados nao configurado"}), 503
    args = _args_periodo()
    if args is None:
        return jsonify({"erro": "Parametros data_inicio e data_fim obrigatorios"}), 400
    try:
        vertices = fetch_vertices_by_range(*args)
        return jsonify({
            "normalizado": agregar_normalizado_por_missao(vertices),
        }), 200
    except Exception as exc:
        logger.error("Erro analytics normalizado: %s", exc)
        return jsonify({"erro": "Erro ao agregar normalizado"}), 500


@api_catalogos_bp.route("/analytics/saude", methods=["GET"])
@login_required
def analytics_saude() -> tuple:
    """Saude catalogacao (6.3): % vertices com missao_id / municipio_id."""
    if not _db_configurado():
        return jsonify({"erro": "Banco de dados nao configurado"}), 503
    args = _args_periodo()
    if args is None:
        return jsonify({"erro": "Parametros data_inicio e data_fim obrigatorios"}), 400
    try:
        vertices = fetch_vertices_by_range(*args)
        return jsonify({"saude": saude_catalogacao(vertices)}), 200
    except Exception as exc:
        logger.error("Erro analytics saude: %s", exc)
        return jsonify({"erro": "Erro ao calcular saude"}), 500
