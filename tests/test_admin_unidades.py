"""Testes das rotas /admin/catalogos/unidades (Fase 6.4 polish).

Cobre role-gating, happy path de criar/editar e propagacao de ValueError
do service para flash+redirect. Services mockados — sem DB.
"""
from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from app import create_app
from app.models.user import User
from app.services.catalogo_types import Municipio, Unidade


# ---------------------------------------------------------------------------
# Fixtures locais
# ---------------------------------------------------------------------------


def _user(
    *,
    user_id: str = "00000000-0000-0000-0000-000000000010",
    role: str = "gestor",
) -> User:
    return User(
        id=user_id,
        nome=f"User {role}",
        email=f"{role}@teste.local",
        role=cast("User.role", role),  # type: ignore[arg-type]
        unidade=None,
        totp_ativo=False,
        ativo=True,
    )


def _app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["DATABASE_URL"] = "postgresql://fake:fake@localhost/fake"
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SESSION_PROTECTION"] = None
    app.config["RATELIMIT_ENABLED"] = False
    return app


def _login(client, monkeypatch, user: User) -> None:
    monkeypatch.setattr(
        "app.services.user_service.get_by_id",
        lambda uid: user if uid == user.id else None,
    )
    with client.session_transaction() as sess:
        sess["_user_id"] = user.id
        sess["_fresh"] = True


def _unidade_fake(
    uid: str = "u1", nome: str = "1° BPChq", ativo: bool = True,
) -> Unidade:
    return Unidade(
        id=uid, nome=nome, nome_normalizado="1 BPCHQ",
        municipio_sede_id="sede-poa", ativo=ativo,
    )


def _municipio_fake() -> Municipio:
    return Municipio(
        id="sede-poa", nome="Porto Alegre",
        crpm_id="crpm-1", crpm_sigla="CPC", ativo=True,
    )


# ---------------------------------------------------------------------------
# GET /admin/catalogos/unidades
# ---------------------------------------------------------------------------


class TestListarUnidades:

    def test_gestor_200(self, monkeypatch) -> None:
        app = _app()
        monkeypatch.setattr(
            "app.routes.admin_catalogos.unidade_service.listar_unidades",
            lambda somente_ativas=False: [_unidade_fake()],
        )
        monkeypatch.setattr(
            "app.routes.admin_catalogos.catalogo_service.listar_municipios",
            lambda **kw: [_municipio_fake()],
        )
        with app.test_client() as c:
            _login(c, monkeypatch, _user(role="gestor"))
            resp = c.get("/admin/catalogos/unidades")
            assert resp.status_code == 200
            body = resp.data.decode("utf-8")
            assert "1° BPChq" in body
            assert "Porto Alegre" in body

    def test_arei_403(self, monkeypatch) -> None:
        app = _app()
        with app.test_client() as c:
            _login(c, monkeypatch, _user(role="operador_arei"))
            resp = c.get("/admin/catalogos/unidades")
            assert resp.status_code == 403

    def test_sem_login_redirect(self) -> None:
        app = _app()
        with app.test_client() as c:
            resp = c.get("/admin/catalogos/unidades")
            assert resp.status_code == 302
            assert "/login" in resp.headers["Location"]


# ---------------------------------------------------------------------------
# POST /admin/catalogos/unidades/criar
# ---------------------------------------------------------------------------


class TestCriarUnidade:

    def test_gestor_happy_path_redirect(self, monkeypatch) -> None:
        app = _app()
        capturado: dict = {}

        def fake_criar(payload):
            capturado.update(payload)
            return _unidade_fake(nome="7° BPChq")

        monkeypatch.setattr(
            "app.routes.admin_catalogos.unidade_service.criar_unidade",
            fake_criar,
        )
        with app.test_client() as c:
            _login(c, monkeypatch, _user(role="gestor"))
            resp = c.post(
                "/admin/catalogos/unidades/criar",
                data={"nome": "7° BPChq", "municipio_sede_id": "sede-poa"},
            )
            assert resp.status_code == 302
            assert "/admin/catalogos/unidades" in resp.headers["Location"]
        assert capturado == {
            "nome": "7° BPChq", "municipio_sede_id": "sede-poa",
        }

    def test_service_valueerror_vira_flash(self, monkeypatch) -> None:
        app = _app()

        def fake_criar(payload):
            raise ValueError("Unidade '7 BPCHQ' ja existe no catalogo")

        monkeypatch.setattr(
            "app.routes.admin_catalogos.unidade_service.criar_unidade",
            fake_criar,
        )
        with app.test_client() as c:
            _login(c, monkeypatch, _user(role="gestor"))
            resp = c.post(
                "/admin/catalogos/unidades/criar",
                data={"nome": "7° BPChq", "municipio_sede_id": "sede-poa"},
                follow_redirects=False,
            )
            assert resp.status_code == 302
            with c.session_transaction() as sess:
                flashes = sess.get("_flashes", [])
            assert any(
                cat == "error" and "ja existe" in msg
                for cat, msg in flashes
            )

    def test_arei_403(self, monkeypatch) -> None:
        app = _app()
        with app.test_client() as c:
            _login(c, monkeypatch, _user(role="operador_arei"))
            resp = c.post(
                "/admin/catalogos/unidades/criar",
                data={"nome": "7° BPChq", "municipio_sede_id": "sede-poa"},
            )
            assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /admin/catalogos/unidades/<id>/editar
# ---------------------------------------------------------------------------


class TestEditarUnidade:

    def test_desativar(self, monkeypatch) -> None:
        app = _app()
        capturado: dict = {}

        def fake_atualizar(uid, payload):
            capturado["uid"] = uid
            capturado["payload"] = dict(payload)
            return replace(_unidade_fake(uid=uid), ativo=False)

        monkeypatch.setattr(
            "app.routes.admin_catalogos.unidade_service.atualizar_unidade",
            fake_atualizar,
        )
        with app.test_client() as c:
            _login(c, monkeypatch, _user(role="gestor"))
            resp = c.post(
                "/admin/catalogos/unidades/u-alvo/editar",
                data={"ativo": "0"},
            )
            assert resp.status_code == 302
        assert capturado["uid"] == "u-alvo"
        assert capturado["payload"] == {"ativo": False}

    def test_reativar(self, monkeypatch) -> None:
        app = _app()
        capturado: dict = {}

        def fake_atualizar(uid, payload):
            capturado["payload"] = dict(payload)
            return _unidade_fake(uid=uid)

        monkeypatch.setattr(
            "app.routes.admin_catalogos.unidade_service.atualizar_unidade",
            fake_atualizar,
        )
        with app.test_client() as c:
            _login(c, monkeypatch, _user(role="gestor"))
            resp = c.post(
                "/admin/catalogos/unidades/u-alvo/editar",
                data={"ativo": "1"},
            )
            assert resp.status_code == 302
        assert capturado["payload"] == {"ativo": True}

    def test_editar_nome_e_sede(self, monkeypatch) -> None:
        app = _app()
        capturado: dict = {}

        def fake_atualizar(uid, payload):
            capturado["payload"] = dict(payload)
            return _unidade_fake(uid=uid, nome="2° BPChq")

        monkeypatch.setattr(
            "app.routes.admin_catalogos.unidade_service.atualizar_unidade",
            fake_atualizar,
        )
        with app.test_client() as c:
            _login(c, monkeypatch, _user(role="gestor"))
            resp = c.post(
                "/admin/catalogos/unidades/u-alvo/editar",
                data={
                    "nome": "2° BPChq",
                    "municipio_sede_id": "sede-nova",
                },
            )
            assert resp.status_code == 302
        assert capturado["payload"] == {
            "nome": "2° BPChq", "municipio_sede_id": "sede-nova",
        }

    def test_service_valueerror_vira_flash(self, monkeypatch) -> None:
        app = _app()

        def fake_atualizar(uid, payload):
            raise ValueError("Unidade nao encontrada")

        monkeypatch.setattr(
            "app.routes.admin_catalogos.unidade_service.atualizar_unidade",
            fake_atualizar,
        )
        with app.test_client() as c:
            _login(c, monkeypatch, _user(role="gestor"))
            resp = c.post(
                "/admin/catalogos/unidades/inexistente/editar",
                data={"ativo": "0"},
            )
            assert resp.status_code == 302
            with c.session_transaction() as sess:
                flashes = sess.get("_flashes", [])
            assert any(
                cat == "error" and "nao encontrada" in msg
                for cat, msg in flashes
            )

    def test_arei_403(self, monkeypatch) -> None:
        app = _app()
        with app.test_client() as c:
            _login(c, monkeypatch, _user(role="operador_arei"))
            resp = c.post(
                "/admin/catalogos/unidades/u1/editar",
                data={"ativo": "0"},
            )
            assert resp.status_code == 403
