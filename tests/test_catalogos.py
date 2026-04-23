"""Testes dos catalogos SMO — normalizacao, tipos, autocomplete API."""
from __future__ import annotations

import pytest

from app.services.catalogo_types import (
    Crpm, Missao, Municipio, normalizar,
)


class TestNormalizar:
    """Normalizacao e o contrato de lookup dos catalogos."""

    def test_uppercase(self) -> None:
        assert normalizar("porto alegre") == "PORTO ALEGRE"

    def test_remove_acentos(self) -> None:
        assert normalizar("São Leopoldo") == "SAO LEOPOLDO"
        assert normalizar("Viamão") == "VIAMAO"
        assert normalizar("gravataí") == "GRAVATAI"

    def test_trim_e_colapso_espacos(self) -> None:
        assert normalizar("  porto   alegre  ") == "PORTO ALEGRE"

    def test_vazio_ou_whitespace(self) -> None:
        assert normalizar("") == ""
        assert normalizar("   ") == ""

    def test_idempotente(self) -> None:
        assert normalizar(normalizar("São Leopoldo")) == normalizar("São Leopoldo")

    def test_preserva_numeros(self) -> None:
        assert normalizar("sao paulo 123") == "SAO PAULO 123"


class TestTiposDataclass:
    """Dataclasses sao frozen e tipos corretos."""

    def test_crpm_frozen(self) -> None:
        c = Crpm(id="x", sigla="RM", nome="n", sede=None, ordem=1, ativo=True)
        with pytest.raises(Exception):
            c.sigla = "OUTRO"  # type: ignore[misc]

    def test_missao_frozen(self) -> None:
        m = Missao(id="x", nome="ESCOLTA", descricao=None, ativo=True)
        with pytest.raises(Exception):
            m.nome = "OUTRA"  # type: ignore[misc]

    def test_municipio_frozen(self) -> None:
        mu = Municipio(
            id="x", nome="Viamao", crpm_id="y", crpm_sigla="RM", ativo=True,
        )
        with pytest.raises(Exception):
            mu.nome = "Outra"  # type: ignore[misc]


class TestCatalogosApi:
    """Endpoints /api/catalogos/* retornam 200 com estrutura esperada.

    DB e mockado via monkeypatch do catalogo_service. Testa contrato/contrato JSON.
    """

    def test_missoes_sem_q(self, app_client, monkeypatch) -> None:
        missoes = [
            Missao(id="1", nome="ESCOLTA", descricao="x", ativo=True),
            Missao(id="2", nome="PATRULHAMENTO OSTENSIVO", descricao=None, ativo=True),
        ]
        monkeypatch.setattr(
            "app.services.catalogo_service.listar_missoes",
            lambda q=None, somente_ativas=True, limite=500: missoes,
        )
        resp = app_client.get("/api/catalogos/missoes")
        assert resp.status_code == 200
        body = resp.get_json()
        assert "missoes" in body
        assert len(body["missoes"]) == 2
        assert body["missoes"][0]["nome"] == "ESCOLTA"

    def test_missoes_com_q_filtra_service(self, app_client, monkeypatch) -> None:
        capturados: dict = {}

        def _fake(q=None, somente_ativas=True, limite=500):
            capturados["q"] = q
            capturados["limite"] = limite
            return []

        monkeypatch.setattr(
            "app.services.catalogo_service.listar_missoes", _fake
        )
        resp = app_client.get("/api/catalogos/missoes?q=escol")
        assert resp.status_code == 200
        assert capturados["q"] == "escol"
        assert capturados["limite"] == 200

    def test_municipios_filtra_por_crpm(self, app_client, monkeypatch) -> None:
        capturados: dict = {}

        def _fake(crpm_id=None, q=None, somente_ativos=True, limite=500):
            capturados["crpm_id"] = crpm_id
            capturados["q"] = q
            return [Municipio(
                id="mx", nome="Viamao", crpm_id="rm-id",
                crpm_sigla="RM", ativo=True,
            )]

        monkeypatch.setattr(
            "app.services.catalogo_service.listar_municipios", _fake
        )
        resp = app_client.get("/api/catalogos/municipios?crpm=rm-id&q=Via")
        assert resp.status_code == 200
        body = resp.get_json()
        assert capturados["crpm_id"] == "rm-id"
        assert capturados["q"] == "Via"
        assert body["municipios"][0]["crpm_sigla"] == "RM"

    def test_crpms_retorna_ordem(self, app_client, monkeypatch) -> None:
        crpms = [
            Crpm(id="1", sigla="RM", nome="I", sede="POA", ordem=1, ativo=True),
            Crpm(id="2", sigla="VRS", nome="III", sede="NH", ordem=3, ativo=True),
        ]
        monkeypatch.setattr(
            "app.services.catalogo_service.listar_crpms",
            lambda somente_ativos=True: crpms,
        )
        resp = app_client.get("/api/catalogos/crpms")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["crpms"][0]["ordem"] == 1
        assert body["crpms"][1]["sigla"] == "VRS"

    def test_api_requer_autenticacao(self, monkeypatch) -> None:
        """Sem login retorna 302 (redirect) ou 401."""
        from app import create_app

        app = create_app()
        app.config["TESTING"] = True
        app.config["DATABASE_URL"] = ""
        with app.test_client() as client:
            resp = client.get("/api/catalogos/missoes")
            assert resp.status_code in (302, 401)
