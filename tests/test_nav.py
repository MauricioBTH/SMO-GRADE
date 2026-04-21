"""Testes de role-gate no partial _components/nav.html."""
from __future__ import annotations

from typing import cast

import pytest
from flask import Blueprint, render_template
from flask_login import login_required

from app import create_app
from app.models.user import User


def _make_user(
    *,
    user_id: str = "00000000-0000-0000-0000-000000000001",
    role: str = "gestor",
    unidade: str | None = None,
) -> User:
    return User(
        id=user_id,
        nome="Usuario Teste",
        email="user@teste.local",
        role=cast("User.role", role),  # type: ignore[arg-type]
        unidade=unidade,
        totp_ativo=False,
        ativo=True,
    )


def _app_com_endpoint_nav() -> object:
    app = create_app()
    app.config["TESTING"] = True
    app.config["DATABASE_URL"] = "postgresql://fake:fake@localhost/fake"
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SESSION_PROTECTION"] = None
    app.config["RATELIMIT_ENABLED"] = False

    bp = Blueprint("teste_nav", __name__)

    @bp.route("/_teste/nav")
    @login_required
    def _view() -> str:
        return render_template("_components/nav.html")

    app.register_blueprint(bp)
    return app


class TestNavRoleGate:

    def test_gestor_ve_todos_os_links(self, monkeypatch):
        app = _app_com_endpoint_nav()
        gestor = _make_user(role="gestor")
        monkeypatch.setattr(
            "app.services.user_service.get_by_id",
            lambda uid: gestor if uid == gestor.id else None,
        )
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["_user_id"] = gestor.id
                sess["_fresh"] = True
            resp = client.get("/_teste/nav")
            assert resp.status_code == 200
            body = resp.data.decode("utf-8")
            assert "/analista" in body
            assert "/admin/catalogos/missoes" in body
            assert "/admin/catalogos/municipios" in body
            assert "/admin/catalogos/triagem-missoes" in body
            assert "/admin/usuarios" in body

    def test_arei_nao_ve_links_admin(self, monkeypatch):
        app = _app_com_endpoint_nav()
        arei = _make_user(role="operador_arei", unidade="1 BPChq")
        monkeypatch.setattr(
            "app.services.user_service.get_by_id",
            lambda uid: arei if uid == arei.id else None,
        )
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["_user_id"] = arei.id
                sess["_fresh"] = True
            resp = client.get("/_teste/nav")
            assert resp.status_code == 200
            body = resp.data.decode("utf-8")
            assert 'href="/"' in body  # parser continua visivel
            assert "/analista" not in body
            assert "/admin/catalogos/missoes" not in body
            assert "/admin/catalogos/municipios" not in body
            assert "/admin/catalogos/triagem-missoes" not in body
            assert "/admin/usuarios" not in body
