"""Testes da rota /trocar-senha e da politica de senha."""
from __future__ import annotations

from typing import cast

import pytest

from app import create_app
from app.extensions import limiter
from app.models.user import User
from app.services.user_service import _validar_senha


def _make_user(
    *,
    user_id: str = "00000000-0000-0000-0000-000000000001",
    email: str = "gestor@teste.local",
    role: str = "gestor",
    unidade: str | None = None,
) -> User:
    return User(
        id=user_id,
        nome="Usuario Teste",
        email=email,
        role=cast("User.role", role),  # type: ignore[arg-type]
        unidade=unidade,
        totp_ativo=False,
        ativo=True,
    )


@pytest.fixture
def app_autenticado(monkeypatch):
    user = _make_user()
    app = create_app()
    app.config["TESTING"] = True
    app.config["DATABASE_URL"] = "postgresql://fake:fake@localhost/fake"
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SESSION_PROTECTION"] = None
    app.config["RATELIMIT_ENABLED"] = False
    limiter.enabled = False

    monkeypatch.setattr(
        "app.services.user_service.get_by_id",
        lambda uid: user if uid == user.id else None,
    )
    return app, user


class TestTrocarSenha:

    def test_get_sem_login_redireciona(self):
        app = create_app()
        app.config["TESTING"] = True
        app.config["DATABASE_URL"] = "postgresql://fake:fake@localhost/fake"
        app.config["WTF_CSRF_ENABLED"] = False
        app.config["SESSION_PROTECTION"] = None
        with app.test_client() as client:
            resp = client.get("/trocar-senha")
            assert resp.status_code == 302
            assert "/login" in resp.headers["Location"]

    def test_post_senha_atual_errada(self, app_autenticado, monkeypatch):
        app, user = app_autenticado
        chamadas: list[tuple[str, str]] = []
        monkeypatch.setattr(
            "app.services.user_service.verificar_senha",
            lambda e, s: None,
        )
        monkeypatch.setattr(
            "app.services.user_service.alterar_senha",
            lambda uid, nova: chamadas.append((uid, nova)),
        )
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["_user_id"] = user.id
                sess["_fresh"] = True
            resp = client.post(
                "/trocar-senha",
                data={
                    "senha_atual": "errada",
                    "senha_nova": "nova-senha-123",
                    "senha_conf": "nova-senha-123",
                },
            )
            assert resp.status_code == 401
            assert chamadas == []

    def test_post_nova_diferente_da_confirmacao(self, app_autenticado, monkeypatch):
        app, user = app_autenticado
        chamadas: list[tuple[str, str]] = []
        monkeypatch.setattr(
            "app.services.user_service.verificar_senha",
            lambda e, s: user,
        )
        monkeypatch.setattr(
            "app.services.user_service.alterar_senha",
            lambda uid, nova: chamadas.append((uid, nova)),
        )
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["_user_id"] = user.id
                sess["_fresh"] = True
            resp = client.post(
                "/trocar-senha",
                data={
                    "senha_atual": "atual-123456",
                    "senha_nova": "nova-senha-123",
                    "senha_conf": "nova-senha-999",
                },
            )
            assert resp.status_code == 400
            assert chamadas == []

    def test_post_ok_atualiza_e_redireciona(self, app_autenticado, monkeypatch):
        app, user = app_autenticado
        chamadas: list[tuple[str, str]] = []
        monkeypatch.setattr(
            "app.services.user_service.verificar_senha",
            lambda e, s: user,
        )
        monkeypatch.setattr(
            "app.services.user_service.alterar_senha",
            lambda uid, nova: chamadas.append((uid, nova)),
        )
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["_user_id"] = user.id
                sess["_fresh"] = True
            resp = client.post(
                "/trocar-senha",
                data={
                    "senha_atual": "atual-123456",
                    "senha_nova": "nova-senha-123",
                    "senha_conf": "nova-senha-123",
                },
                follow_redirects=False,
            )
            assert resp.status_code == 302
            assert "/login" not in resp.headers["Location"]
            assert chamadas == [(user.id, "nova-senha-123")]


class TestPoliticaSenha:

    def test_rejeita_curta(self):
        with pytest.raises(ValueError, match="pelo menos 8"):
            _validar_senha("Ab!1")

    def test_rejeita_sem_maiuscula(self):
        with pytest.raises(ValueError, match="maiuscula"):
            _validar_senha("minuscula!1")

    def test_rejeita_sem_especial(self):
        with pytest.raises(ValueError, match="especial"):
            _validar_senha("SemEspecial1")

    def test_aceita_senha_valida(self):
        _validar_senha("Valida!23")
