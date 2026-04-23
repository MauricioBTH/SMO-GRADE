"""Blueprint de uploads versionados (Fase 6.5.b).

Endpoints expostos sob `/api/uploads`:
  GET  /api/uploads?unidade=X&data=Y          — histórico do dia (qualquer user auth)
  GET  /api/uploads/existente?unidade=X&data=Y — só o upload ativo (modal de confirmacao)
  POST /api/uploads/<id>/restaurar            — operador_arei | gestor
  GET  /api/uploads/<id>/texto                — só gestor (PII)

Princípios:
  - Role decorators em todos os endpoints de mutacao/PII.
  - Queries parametrizadas; nenhuma f-string em SQL (servico faz isso).
  - Body JSON sempre; 400 se malformado.
  - Nunca loga texto_original (PII): apenas upload_id + user_id.

Separado de api.py pra manter arquivos <= 500 LOC (padrao 6.2/6.3/6.4).
"""
from __future__ import annotations

import logging

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required

from app.auth.decorators import role_required
from app.services import upload_service
from app.services.upload_service import Upload, UploadHistorico

api_uploads_bp = Blueprint("api_uploads", __name__)
logger = logging.getLogger(__name__)


def _db_configurado() -> bool:
    return bool(current_app.config.get("DATABASE_URL"))


def _serializar_upload(up: Upload) -> dict:
    """Serializa Upload para JSON — exclui `texto_original` por default (PII)."""
    return {
        "id": up.id,
        "usuario_id": up.usuario_id,
        "unidade": up.unidade,
        "data": up.data,
        "criado_em": up.criado_em.isoformat(),
        "origem": up.origem,
        "substitui_id": up.substitui_id,
        "cancelado_em": (
            up.cancelado_em.isoformat() if up.cancelado_em else None
        ),
        "cancelado_por": up.cancelado_por,
        "observacao": up.observacao,
    }


def _serializar_historico(h: UploadHistorico) -> dict:
    base = _serializar_upload(h.upload)
    base.update({
        "usuario_nome": h.usuario_nome,
        "cancelado_por_nome": h.cancelado_por_nome,
        "qtde_fracoes": h.qtde_fracoes,
        "qtde_cabecalho": h.qtde_cabecalho,
        "ativo": h.upload.cancelado_em is None,
    })
    return base


@api_uploads_bp.route("/uploads", methods=["GET"])
@login_required
def uploads_listar() -> tuple:
    """Histórico do dia (ordem desc por criado_em). Inclui cancelados."""
    if not _db_configurado():
        return jsonify({"erro": "Banco de dados nao configurado"}), 503

    unidade: str = (request.args.get("unidade") or "").strip()
    data: str = (request.args.get("data") or "").strip()
    if not unidade or not data:
        return jsonify({"erro": "Parametros 'unidade' e 'data' obrigatorios"}), 400

    try:
        historico = upload_service.listar_historico(unidade, data)
        return jsonify({
            "uploads": [_serializar_historico(h) for h in historico]
        }), 200
    except Exception as exc:
        logger.error("Erro ao listar historico de uploads: %s", exc)
        return jsonify({"erro": "Erro ao listar historico"}), 500


@api_uploads_bp.route("/uploads/existente", methods=["GET"])
@login_required
def uploads_existente() -> tuple:
    """Metadata do upload ativo — alimenta bloco "ja existe" do modal 6.5.a.

    Resposta: {existe: bool, upload: UploadHistorico | null}. Devolve `null`
    com `existe=false` quando o dia nao tem upload ativo ainda — o cliente
    tolera ambos (modal mostra bloco so se existe=true).
    """
    if not _db_configurado():
        return jsonify({"erro": "Banco de dados nao configurado"}), 503

    unidade: str = (request.args.get("unidade") or "").strip()
    data: str = (request.args.get("data") or "").strip()
    if not unidade or not data:
        return jsonify({"erro": "Parametros 'unidade' e 'data' obrigatorios"}), 400

    try:
        ativo_meta = upload_service.upload_ativo_com_metadata(unidade, data)
        if ativo_meta is None:
            return jsonify({"existe": False, "upload": None}), 200
        return jsonify({
            "existe": True,
            "upload": _serializar_historico(ativo_meta),
        }), 200
    except Exception as exc:
        logger.error("Erro ao buscar upload existente: %s", exc)
        return jsonify({"erro": "Erro ao buscar upload existente"}), 500


@api_uploads_bp.route("/uploads/<upload_id>/restaurar", methods=["POST"])
@login_required
@role_required(["gestor", "operador_arei"])
def uploads_restaurar(upload_id: str) -> tuple:
    """Cancela o upload ativo atual (se houver) e volta o alvo pra ativo."""
    if not _db_configurado():
        return jsonify({"erro": "Banco de dados nao configurado"}), 503
    if not upload_id:
        return jsonify({"erro": "upload_id vazio"}), 400

    try:
        restaurado = upload_service.restaurar_upload(upload_id, current_user.id)
    except ValueError as exc:
        # ValueError = regra de negocio (alvo ja ativo, nao encontrado).
        return jsonify({"erro": str(exc)}), 400
    except Exception as exc:
        logger.error("Erro ao restaurar upload %s: %s", upload_id, exc)
        return jsonify({"erro": "Erro ao restaurar upload"}), 500

    return jsonify({
        "sucesso": True,
        "upload": _serializar_upload(restaurado),
    }), 200


@api_uploads_bp.route("/uploads/<upload_id>/texto", methods=["GET"])
@login_required
@role_required(["gestor"])
def uploads_texto(upload_id: str) -> tuple:
    """Retorna texto_original (cru do WhatsApp) — só gestor (PII).

    Nao inclui o texto no log para nao vazar PII; apenas registra o acesso."""
    if not _db_configurado():
        return jsonify({"erro": "Banco de dados nao configurado"}), 503
    if not upload_id:
        return jsonify({"erro": "upload_id vazio"}), 400

    up = upload_service.get_upload(upload_id)
    if up is None:
        return jsonify({"erro": "Upload nao encontrado"}), 404

    # Log de acesso a PII — user_id + upload_id (sem o texto).
    logger.info(
        "acesso texto_original upload_id=%s por user_id=%s",
        upload_id, current_user.id,
    )
    return jsonify({
        "upload": _serializar_upload(up),
        "texto_original": up.texto_original,
    }), 200
