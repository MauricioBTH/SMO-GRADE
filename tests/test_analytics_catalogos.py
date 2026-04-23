"""Testes das agregacoes por missao/municipio (Fase 6.2)."""
from __future__ import annotations

from app.services.analytics_catalogos import (
    agregar_por_missao, agregar_por_municipio,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fr(
    unidade: str,
    missao_id: str | None = None,
    missao_nome: str = "",
    missao: str = "",
    municipio_id: str | None = None,
    municipio_nome: str = "",
    municipio_nome_raw: str = "",
    crpm_sigla: str = "",
    equipes: int = 1,
    pms: int = 10,
) -> dict:
    return {
        "unidade": unidade,
        "missao_id": missao_id,
        "missao_nome": missao_nome,
        "missao": missao,
        "municipio_id": municipio_id,
        "municipio_nome": municipio_nome,
        "municipio_nome_raw": municipio_nome_raw,
        "crpm_sigla": crpm_sigla,
        "equipes": equipes,
        "pms": pms,
    }


# ---------------------------------------------------------------------------
# Por missao
# ---------------------------------------------------------------------------


class TestAgregarPorMissao:
    def test_soma_por_missao_id(self) -> None:
        fracoes = [
            _fr("1 BPChq", missao_id="m1", missao_nome="ESCOLTA", pms=10, equipes=2),
            _fr("2 BPChq", missao_id="m1", missao_nome="ESCOLTA", pms=20, equipes=3),
            _fr("1 BPChq", missao_id="m2", missao_nome="CANIL", pms=5, equipes=1),
        ]
        resultado = agregar_por_missao(fracoes)
        assert len(resultado) == 2

        escolta = next(r for r in resultado if r["missao_id"] == "m1")
        assert escolta["total_fracoes"] == 2
        assert escolta["total_pms"] == 30
        assert escolta["total_equipes"] == 5
        assert set(escolta["unidades"]) == {"1 BPChq", "2 BPChq"}

    def test_ordena_por_pms_desc(self) -> None:
        fracoes = [
            _fr("1 BPChq", missao_id="m1", missao_nome="A", pms=5),
            _fr("1 BPChq", missao_id="m2", missao_nome="B", pms=30),
            _fr("1 BPChq", missao_id="m3", missao_nome="C", pms=15),
        ]
        resultado = agregar_por_missao(fracoes)
        assert [r["missao_nome"] for r in resultado] == ["B", "C", "A"]

    def test_sem_catalogo_bucket(self) -> None:
        fracoes = [
            _fr("1 BPChq", missao="", pms=5),
            _fr("1 BPChq", missao="   ", pms=8),
        ]
        resultado = agregar_por_missao(fracoes)
        assert len(resultado) == 1
        assert resultado[0]["missao_id"] is None
        assert resultado[0]["missao_nome"] == "SEM CATALOGO"
        assert resultado[0]["total_pms"] == 13

    def test_agrupa_texto_cru_caixa_alta(self) -> None:
        """Sem missao_id agrupa por texto uppercase com prefixo 'SEM CATALOGO:'.

        Fase 6.3: o rotulo explicita no painel que o vertice nao foi
        catalogado; camada deterministica diferencia visualmente das linhas
        catalogadas.
        """
        fracoes = [
            _fr("1 BPChq", missao="escolta", pms=10),
            _fr("1 BPChq", missao="ESCOLTA", pms=15),
            _fr("2 BPChq", missao="Escolta", pms=7),
        ]
        resultado = agregar_por_missao(fracoes)
        assert len(resultado) == 1
        assert resultado[0]["missao_nome"] == "SEM CATALOGO: ESCOLTA"
        assert resultado[0]["total_pms"] == 32


# ---------------------------------------------------------------------------
# Por municipio
# ---------------------------------------------------------------------------


class TestAgregarPorMunicipio:
    def test_soma_por_municipio_id_com_crpm(self) -> None:
        fracoes = [
            _fr("1 BPChq", municipio_id="mu1", municipio_nome="Porto Alegre",
                crpm_sigla="RM", pms=10, equipes=2),
            _fr("2 BPChq", municipio_id="mu1", municipio_nome="Porto Alegre",
                crpm_sigla="RM", pms=20, equipes=3),
            _fr("1 BPChq", municipio_id="mu2", municipio_nome="Canoas",
                crpm_sigla="RM", pms=5, equipes=1),
        ]
        resultado = agregar_por_municipio(fracoes)
        poa = next(r for r in resultado if r["municipio_nome"] == "Porto Alegre")
        assert poa["total_fracoes"] == 2
        assert poa["total_pms"] == 30
        assert poa["total_equipes"] == 5
        assert poa["crpm_sigla"] == "RM"

    def test_sem_catalogo(self) -> None:
        fracoes = [
            _fr("1 BPChq", municipio_nome_raw="", pms=3),
        ]
        resultado = agregar_por_municipio(fracoes)
        assert resultado[0]["municipio_nome"] == "SEM CATALOGO"
        assert resultado[0]["municipio_id"] is None
        assert resultado[0]["crpm_sigla"] == ""

    def test_ordena_por_pms(self) -> None:
        fracoes = [
            _fr("1 BPChq", municipio_id="a", municipio_nome="A", pms=5),
            _fr("1 BPChq", municipio_id="b", municipio_nome="B", pms=50),
            _fr("1 BPChq", municipio_id="c", municipio_nome="C", pms=20),
        ]
        resultado = agregar_por_municipio(fracoes)
        assert [r["municipio_nome"] for r in resultado] == ["B", "C", "A"]

    def test_equipes_pms_conversao_segura(self) -> None:
        """Valores None/strings em equipes/pms viram 0."""
        fracoes = [
            _fr("1 BPChq", municipio_id="a", municipio_nome="A", pms=0, equipes=0),
        ]
        fracoes[0]["pms"] = None  # simula NULL do banco
        fracoes[0]["equipes"] = "abc"
        resultado = agregar_por_municipio(fracoes)
        assert resultado[0]["total_pms"] == 0
        assert resultado[0]["total_equipes"] == 0


# ---------------------------------------------------------------------------
# Endpoints /api/analytics/por-*
# ---------------------------------------------------------------------------


class TestAnalyticsEndpoints:
    def test_por_missao_retorna_agregado(
        self, app_client_com_db, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            "app.routes.api_catalogos.fetch_vertices_by_range",
            lambda di, df, u: [
                {"unidade": "1 BPChq", "missao_id": "m1",
                 "missao_nome": "ESCOLTA", "missao": "escolta",
                 "equipes": 2, "pms": 10,
                 "municipio_id": None, "municipio_nome_raw": "",
                 "crpm_sigla": ""},
            ],
        )
        resp = app_client_com_db.get(
            "/api/analytics/por-missao?data_inicio=01/03/2026&data_fim=31/03/2026"
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["por_missao"][0]["missao_nome"] == "ESCOLTA"
        assert body["por_missao"][0]["total_pms"] == 10

    def test_por_municipio_retorna_agregado(
        self, app_client_com_db, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            "app.routes.api_catalogos.fetch_vertices_by_range",
            lambda di, df, u: [
                {"unidade": "1 BPChq", "missao_id": None,
                 "missao_nome": "", "missao": "",
                 "municipio_id": "mu1", "municipio_nome": "Canoas",
                 "municipio_nome_raw": "canoas",
                 "crpm_sigla": "RM", "equipes": 1, "pms": 5},
            ],
        )
        resp = app_client_com_db.get(
            "/api/analytics/por-municipio?data_inicio=01/03/2026&data_fim=31/03/2026"
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["por_municipio"][0]["municipio_nome"] == "Canoas"
        assert body["por_municipio"][0]["crpm_sigla"] == "RM"

    def test_por_missao_sem_datas_400(self, app_client_com_db) -> None:
        resp = app_client_com_db.get("/api/analytics/por-missao")
        assert resp.status_code == 400
