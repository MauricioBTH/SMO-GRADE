"""Testes de autenticacao, 2FA, decoradores de role e unidade."""
from __future__ import annotations

from typing import cast

import pytest

from app import create_app
from app.extensions import limiter
from app.models.user import User


def _make_user(
    *,
    user_id: str = "00000000-0000-0000-0000-000000000001",
    email: str = "gestor@teste.local",
    role: str = "gestor",
    unidade: str | None = None,
    totp_ativo: bool = False,
    ativo: bool = True,
) -> User:
    return User(
        id=user_id,
        nome="Usuario Teste",
        email=email,
        role=cast("User.role", role),  # type: ignore[arg-type]
        unidade=unidade,
        totp_ativo=totp_ativo,
        ativo=ativo,
    )


@pytest.fixture
def app_factory():
    def _criar(testing: bool = True, limiter_on: bool = False):
        app = create_app()
        app.config["TESTING"] = testing
        app.config["DATABASE_URL"] = "postgresql://fake:fake@localhost/fake"
        app.config["WTF_CSRF_ENABLED"] = False
        app.config["SESSION_PROTECTION"] = None
        if limiter_on:
            app.config["RATELIMIT_ENABLED"] = True
            limiter.enabled = True
            limiter.reset()
        else:
            app.config["RATELIMIT_ENABLED"] = False
            limiter.enabled = False
        return app
    return _criar


# ---------- Login ----------

class TestLogin:

    def test_login_ok(self, app_factory, monkeypatch):
        app = app_factory()
        user = _make_user()
        monkeypatch.setattr(
            "app.services.user_service.verificar_senha",
            lambda e, s: user if e == user.email and s == "senha-correta-123" else None,
        )
        monkeypatch.setattr(
            "app.services.user_service.get_by_id",
            lambda uid: user if uid == user.id else None,
        )
        monkeypatch.setattr(
            "app.services.user_service.registrar_login",
            lambda uid: None,
        )
        with app.test_client() as client:
            resp = client.post(
                "/login",
                data={"email": user.email, "senha": "senha-correta-123"},
                follow_redirects=False,
            )
            assert resp.status_code == 302
            assert "/login" not in resp.headers["Location"]

    def test_login_senha_errada(self, app_factory, monkeypatch):
        app = app_factory()
        monkeypatch.setattr(
            "app.services.user_service.verificar_senha",
            lambda e, s: None,
        )
        with app.test_client() as client:
            resp = client.post(
                "/login",
                data={"email": "x@y.z", "senha": "errada"},
            )
            assert resp.status_code == 401

    def test_login_exige_campos(self, app_factory):
        app = app_factory()
        with app.test_client() as client:
            resp = client.post("/login", data={"email": "", "senha": ""})
            assert resp.status_code == 400

    def test_login_rate_limit(self, app_factory, monkeypatch):
        app = app_factory(limiter_on=True)
        monkeypatch.setattr(
            "app.services.user_service.verificar_senha",
            lambda e, s: None,
        )
        with app.test_client() as client:
            for _ in range(5):
                resp = client.post(
                    "/login",
                    data={"email": "x@y.z", "senha": "errada"},
                )
                assert resp.status_code in (400, 401)
            resp = client.post(
                "/login",
                data={"email": "x@y.z", "senha": "errada"},
            )
            assert resp.status_code == 429


# ---------- 2FA ----------

class TestDoisFatores:

    def test_totp_valido(self, app_factory, monkeypatch):
        app = app_factory()
        user = _make_user(role="gestor", totp_ativo=True)
        monkeypatch.setattr(
            "app.services.user_service.get_by_id",
            lambda uid: user if uid == user.id else None,
        )
        monkeypatch.setattr(
            "app.services.user_service.get_totp_secret",
            lambda uid: "FAKESECRET",
        )
        monkeypatch.setattr(
            "app.services.user_service.registrar_login",
            lambda uid: None,
        )
        monkeypatch.setattr(
            "app.services.totp_service.verificar_codigo",
            lambda s, c: c == "123456",
        )
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["pending_2fa_user_id"] = user.id
            resp = client.post("/login/2fa", data={"codigo": "123456"})
            assert resp.status_code == 302
            assert "/login" not in resp.headers["Location"]

    def test_totp_invalido(self, app_factory, monkeypatch):
        app = app_factory()
        user = _make_user(role="gestor", totp_ativo=True)
        monkeypatch.setattr(
            "app.services.user_service.get_by_id",
            lambda uid: user if uid == user.id else None,
        )
        monkeypatch.setattr(
            "app.services.user_service.get_totp_secret",
            lambda uid: "FAKESECRET",
        )
        monkeypatch.setattr(
            "app.services.totp_service.verificar_codigo",
            lambda s, c: False,
        )
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["pending_2fa_user_id"] = user.id
            resp = client.post("/login/2fa", data={"codigo": "000000"})
            assert resp.status_code == 401


# ---------- Decorador de role ----------

class TestDecoradorRole:

    def test_rota_gestor_nega_arei(self, app_factory, monkeypatch):
        app = app_factory()
        arei = _make_user(role="operador_arei", unidade="1 BPChq")
        monkeypatch.setattr(
            "app.services.user_service.get_by_id",
            lambda uid: arei if uid == arei.id else None,
        )
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["_user_id"] = arei.id
                sess["_fresh"] = True
            resp = client.get("/admin/usuarios")
            assert resp.status_code == 403

    def test_rota_gestor_permite_gestor(self, app_factory, monkeypatch):
        app = app_factory()
        gestor = _make_user(role="gestor")
        monkeypatch.setattr(
            "app.services.user_service.get_by_id",
            lambda uid: gestor if uid == gestor.id else None,
        )
        monkeypatch.setattr(
            "app.services.user_service.listar",
            lambda filtro=None: [],
        )
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["_user_id"] = gestor.id
                sess["_fresh"] = True
            resp = client.get("/admin/usuarios")
            assert resp.status_code == 200

    def test_rota_protegida_sem_login_redireciona(self, app_factory):
        app = app_factory()
        with app.test_client() as client:
            resp = client.get("/admin/usuarios")
            assert resp.status_code == 302
            assert "/login" in resp.headers["Location"]


