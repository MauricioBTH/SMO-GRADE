"""Testes do blueprint /api/uploads (Fase 6.5.b).

Cobre:
  - Role-gating dos endpoints (restaurar e texto sao restritos).
  - Formato do payload serializado (Upload, UploadHistorico).
  - Caminhos de erro: 400 para params faltando/ValueError, 404 para
    upload inexistente, 503 quando DB nao configurado.
  - Nao vazamento do texto_original em endpoints que nao sao /texto.

upload_service e monkeypatchado — testes puros de contrato de API, sem DB.
Testes DB-integrados ficam fora desta suite (ambiente sem banco de teste).
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import cast

import pytest

from app import create_app
from app.models.user import User
from app.services.upload_service import Upload, UploadHistorico


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _user(
    *,
    user_id: str = "00000000-0000-0000-0000-000000000010",
    role: str = "gestor",
    unidade: str | None = None,
) -> User:
    return User(
        id=user_id,
        nome=f"User {role}",
        email=f"{role}@teste.local",
        role=cast("User.role", role),  # type: ignore[arg-type]
        unidade=unidade,
        totp_ativo=False,
        ativo=True,
    )


def _app(*, db_ok: bool = True):
    app = create_app()
    app.config["TESTING"] = True
    app.config["DATABASE_URL"] = (
        "postgresql://fake:fake@localhost/fake" if db_ok else ""
    )
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


def _upload_fake(
    *,
    up_id: str = "up-1",
    unidade: str = "1 BPChq",
    data: str = "23/04/2026",
    cancelado: bool = False,
    substitui: str | None = None,
    texto: str | None = None,
) -> Upload:
    return Upload(
        id=up_id,
        usuario_id="00000000-0000-0000-0000-000000000010",
        unidade=unidade,
        data=data,
        criado_em=datetime(2026, 4, 23, 14, 32, 0, tzinfo=timezone.utc),
        origem="whatsapp",
        texto_original=texto,
        substitui_id=substitui,
        cancelado_em=(
            datetime(2026, 4, 23, 14, 45, 0, tzinfo=timezone.utc)
            if cancelado else None
        ),
        cancelado_por="00000000-0000-0000-0000-000000000099" if cancelado else None,
        observacao=None,
    )


def _historico_fake(up: Upload, *, nome: str = "AREI-01") -> UploadHistorico:
    return UploadHistorico(
        upload=up,
        usuario_nome=nome,
        cancelado_por_nome=("Gestor" if up.cancelado_em else None),
        qtde_fracoes=3,
        qtde_cabecalho=1,
    )


# ---------------------------------------------------------------------------
# GET /api/uploads — listar historico
# ---------------------------------------------------------------------------


class TestUploadsListar:

    def test_lista_ok(self, monkeypatch) -> None:
        up_atual = _upload_fake(up_id="up-atual")
        up_antigo = _upload_fake(
            up_id="up-antigo", cancelado=True, substitui=None,
        )
        monkeypatch.setattr(
            "app.services.upload_service.listar_historico",
            lambda unidade, data: [
                _historico_fake(up_atual), _historico_fake(up_antigo),
            ],
        )
        app = _app()
        with app.test_client() as c:
            _login(c, monkeypatch, _user(role="gestor"))
            resp = c.get("/api/uploads?unidade=1 BPChq&data=23/04/2026")
            assert resp.status_code == 200
            body = resp.get_json()
            assert "uploads" in body
            assert len(body["uploads"]) == 2
            u0 = body["uploads"][0]
            assert u0["id"] == "up-atual"
            assert u0["ativo"] is True
            assert u0["usuario_nome"] == "AREI-01"
            assert u0["qtde_fracoes"] == 3
            # Nao vazar texto_original — endpoint nao inclui
            assert "texto_original" not in u0
            u1 = body["uploads"][1]
            assert u1["ativo"] is False

    def test_params_faltando(self, monkeypatch) -> None:
        app = _app()
        with app.test_client() as c:
            _login(c, monkeypatch, _user(role="gestor"))
            resp = c.get("/api/uploads?unidade=1 BPChq")
            assert resp.status_code == 400

    def test_db_nao_configurado(self, monkeypatch) -> None:
        app = _app(db_ok=False)
        with app.test_client() as c:
            _login(c, monkeypatch, _user(role="gestor"))
            resp = c.get("/api/uploads?unidade=1 BPChq&data=23/04/2026")
            assert resp.status_code == 503

    def test_sem_login(self) -> None:
        app = _app()
        with app.test_client() as c:
            resp = c.get(
                "/api/uploads?unidade=1 BPChq&data=23/04/2026",
                follow_redirects=False,
            )
            # Rota protegida por login_required — redirect ou 401
            assert resp.status_code in (302, 401)


# ---------------------------------------------------------------------------
# GET /api/uploads/existente
# ---------------------------------------------------------------------------


class TestUploadsExistente:

    def test_existe_true(self, monkeypatch) -> None:
        up = _upload_fake()
        monkeypatch.setattr(
            "app.services.upload_service.upload_ativo_com_metadata",
            lambda unidade, data: _historico_fake(up),
        )
        app = _app()
        with app.test_client() as c:
            _login(c, monkeypatch, _user(role="operador_arei", unidade="1 BPChq"))
            resp = c.get("/api/uploads/existente?unidade=1 BPChq&data=23/04/2026")
            assert resp.status_code == 200
            body = resp.get_json()
            assert body["existe"] is True
            assert body["upload"]["usuario_nome"] == "AREI-01"
            assert body["upload"]["qtde_fracoes"] == 3

    def test_existe_false(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "app.services.upload_service.upload_ativo_com_metadata",
            lambda unidade, data: None,
        )
        app = _app()
        with app.test_client() as c:
            _login(c, monkeypatch, _user(role="gestor"))
            resp = c.get("/api/uploads/existente?unidade=1 BPChq&data=99/99/9999")
            assert resp.status_code == 200
            body = resp.get_json()
            assert body["existe"] is False
            assert body["upload"] is None

    def test_fallback_removido(self, monkeypatch) -> None:
        """Antes havia fallback "ativo existe mas sumiu do historico" — caiu
        fora quando /existente passou a usar upload_ativo_com_metadata (1 query,
        sem chance de inconsistencia entre duas chamadas). Mantemos este teste
        como documentacao: None passa direto, sem fallback."""
        monkeypatch.setattr(
            "app.services.upload_service.upload_ativo_com_metadata",
            lambda unidade, data: None,
        )
        app = _app()
        with app.test_client() as c:
            _login(c, monkeypatch, _user(role="gestor"))
            resp = c.get("/api/uploads/existente?unidade=1 BPChq&data=23/04/2026")
            assert resp.status_code == 200
            body = resp.get_json()
            assert body["existe"] is False
            assert body["upload"] is None


# ---------------------------------------------------------------------------
# POST /api/uploads/<id>/restaurar
# ---------------------------------------------------------------------------


class TestUploadsRestaurar:

    def test_gestor_pode(self, monkeypatch) -> None:
        alvo_restaurado = replace(
            _upload_fake(up_id="up-antigo"),
            cancelado_em=None, cancelado_por=None,
        )
        monkeypatch.setattr(
            "app.services.upload_service.restaurar_upload",
            lambda upload_id, usuario_id: alvo_restaurado,
        )
        app = _app()
        with app.test_client() as c:
            _login(c, monkeypatch, _user(role="gestor"))
            resp = c.post("/api/uploads/up-antigo/restaurar")
            assert resp.status_code == 200
            body = resp.get_json()
            assert body["sucesso"] is True
            assert body["upload"]["id"] == "up-antigo"
            assert body["upload"]["cancelado_em"] is None

    def test_arei_pode(self, monkeypatch) -> None:
        alvo = replace(
            _upload_fake(up_id="up-antigo"),
            cancelado_em=None, cancelado_por=None,
        )
        monkeypatch.setattr(
            "app.services.upload_service.restaurar_upload",
            lambda upload_id, usuario_id: alvo,
        )
        app = _app()
        with app.test_client() as c:
            _login(c, monkeypatch, _user(role="operador_arei", unidade="1 BPChq"))
            resp = c.post("/api/uploads/up-antigo/restaurar")
            assert resp.status_code == 200

    def test_alei_bloqueado(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "app.services.upload_service.restaurar_upload",
            lambda upload_id, usuario_id: _upload_fake(),
        )
        app = _app()
        with app.test_client() as c:
            _login(c, monkeypatch, _user(role="operador_alei", unidade="1 BPChq"))
            resp = c.post("/api/uploads/up-antigo/restaurar")
            assert resp.status_code == 403

    def test_valueerror_vira_400(self, monkeypatch) -> None:
        def _boom(_uid, _usr):
            raise ValueError("Este upload ja e o ativo desse dia")
        monkeypatch.setattr(
            "app.services.upload_service.restaurar_upload", _boom,
        )
        app = _app()
        with app.test_client() as c:
            _login(c, monkeypatch, _user(role="gestor"))
            resp = c.post("/api/uploads/up-atual/restaurar")
            assert resp.status_code == 400
            body = resp.get_json()
            assert "ja e o ativo" in body["erro"]


# ---------------------------------------------------------------------------
# GET /api/uploads/<id>/texto
# ---------------------------------------------------------------------------


class TestUploadsTexto:

    def test_gestor_pode(self, monkeypatch) -> None:
        up = _upload_fake(texto="cru do WhatsApp aqui")
        monkeypatch.setattr(
            "app.services.upload_service.get_upload",
            lambda upload_id: up,
        )
        app = _app()
        with app.test_client() as c:
            _login(c, monkeypatch, _user(role="gestor"))
            resp = c.get("/api/uploads/up-1/texto")
            assert resp.status_code == 200
            body = resp.get_json()
            assert body["texto_original"] == "cru do WhatsApp aqui"
            assert body["upload"]["id"] == "up-1"

    def test_arei_bloqueado(self, monkeypatch) -> None:
        # Nem operador_arei tem acesso a PII do texto original.
        app = _app()
        with app.test_client() as c:
            _login(c, monkeypatch, _user(role="operador_arei", unidade="1 BPChq"))
            resp = c.get("/api/uploads/up-1/texto")
            assert resp.status_code == 403

    def test_alei_bloqueado(self, monkeypatch) -> None:
        app = _app()
        with app.test_client() as c:
            _login(c, monkeypatch, _user(role="operador_alei", unidade="1 BPChq"))
            resp = c.get("/api/uploads/up-1/texto")
            assert resp.status_code == 403

    def test_upload_inexistente(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "app.services.upload_service.get_upload",
            lambda upload_id: None,
        )
        app = _app()
        with app.test_client() as c:
            _login(c, monkeypatch, _user(role="gestor"))
            resp = c.get("/api/uploads/nao-existe/texto")
            assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Upload (dataclass)
# ---------------------------------------------------------------------------


class TestUploadDataclass:

    def test_frozen(self) -> None:
        up = _upload_fake()
        with pytest.raises(Exception):
            up.unidade = "2 BPChq"  # type: ignore[misc]

    def test_origem_invalida_em_row_to_upload(self) -> None:
        from app.services.upload_service import _row_to_upload

        row = {
            "id": "x", "usuario_id": "u", "unidade": "1 BPChq",
            "data": "23/04/2026", "criado_em": datetime.now(tz=timezone.utc),
            "origem": "FONTE-INVALIDA", "texto_original": None,
            "substitui_id": None, "cancelado_em": None, "cancelado_por": None,
            "observacao": None,
        }
        with pytest.raises(ValueError, match="Origem invalida"):
            _row_to_upload(row)


# ---------------------------------------------------------------------------
# Pagina /operador/historico/<unidade>/<data>
# ---------------------------------------------------------------------------


class TestPaginaHistorico:

    def test_renderiza_ok(self, monkeypatch) -> None:
        app = _app()
        with app.test_client() as c:
            _login(c, monkeypatch, _user(role="operador_arei", unidade="1 BPChq"))
            resp = c.get("/operador/historico/1 BPChq/23/04/2026")
            assert resp.status_code == 200
            body = resp.data.decode("utf-8")
            assert "Histórico de uploads" in body
            assert "1 BPChq" in body
            assert "23/04/2026" in body

    def test_unidade_invalida(self, monkeypatch) -> None:
        app = _app()
        with app.test_client() as c:
            _login(c, monkeypatch, _user(role="gestor"))
            resp = c.get("/operador/historico/UNIDADE-FALSA/23/04/2026")
            assert resp.status_code == 404

    def test_data_malformada(self, monkeypatch) -> None:
        app = _app()
        with app.test_client() as c:
            _login(c, monkeypatch, _user(role="gestor"))
            resp = c.get("/operador/historico/1 BPChq/23-04-2026")
            assert resp.status_code == 404
