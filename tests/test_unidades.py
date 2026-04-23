"""Testes da Fase 6.4.1 — catalogo de unidades + fallback municipio-sede."""
from __future__ import annotations

import pytest

from app.services.catalogo_types import Unidade
from app.services.unidade_service import normalizar_codigo_unidade


class TestNormalizarCodigoUnidade:
    """Normalizacao tolera variantes de ordinais e espacos (Fase 6.4.1)."""

    @pytest.mark.parametrize("entrada, esperado", [
        ("1° BPChq", "1 BPCHQ"),
        ("1º BPChq", "1 BPCHQ"),
        ("1°BPChq", "1 BPCHQ"),
        ("1ºBPChq", "1 BPCHQ"),
        ("1 BPChq", "1 BPCHQ"),
        ("1BPChq", "1 BPCHQ"),
        ("6° BPChq", "6 BPCHQ"),
        ("4° RPMon", "4 RPMON"),
        ("4ºRPMon", "4 RPMON"),
        ("  4° RPMon  ", "4 RPMON"),
        ("4° rpmon", "4 RPMON"),
    ])
    def test_variantes(self, entrada: str, esperado: str) -> None:
        assert normalizar_codigo_unidade(entrada) == esperado

    def test_vazio_ou_sem_digito(self) -> None:
        assert normalizar_codigo_unidade("") == ""
        assert normalizar_codigo_unidade("BPChq") == ""
        assert normalizar_codigo_unidade("   ") == ""


class TestUnidadeDataclass:
    def test_frozen(self) -> None:
        u = Unidade(
            id="x", nome="1° BPChq", nome_normalizado="1 BPCHQ",
            municipio_sede_id="y", ativo=True,
        )
        with pytest.raises(Exception):
            u.nome = "Outro"  # type: ignore[misc]


class TestResolverUnidadeSedeFallback:
    """_resolver_vertice usa municipio_sede_id quando em_quartel=True e
    municipio_nome_raw vazio (Fase 6.4.1)."""

    def _rodar_resolver(
        self,
        vertice: dict,
        unidade_raw: str,
        cache_uni: dict,
        cache_muni_por_id: dict,
    ) -> list[str]:
        from app.services.whatsapp_catalogo import _resolver_vertice

        class _FakeCatalogoService:
            @staticmethod
            def lookup_missao_por_nome(_: str) -> None:
                return None

        class _FakeUnidadeService:
            @staticmethod
            def normalizar_codigo_unidade(raw: str) -> str:
                return normalizar_codigo_unidade(raw)

        avisos: list[str] = []
        _resolver_vertice(
            vertice,  # type: ignore[arg-type]
            titulo_fracao="PELOTAO ALFA",
            unidade_raw=unidade_raw,
            cache_muni={},
            cache_muni_por_id=cache_muni_por_id,
            cache_bpm={},
            cache_uni=cache_uni,
            avisos=avisos,
            catalogo_service=_FakeCatalogoService(),
            unidade_service=_FakeUnidadeService(),
        )
        return avisos

    def test_em_quartel_sem_muni_deriva_da_sede(self) -> None:
        sede_id: str = "sede-uuid-123"
        uni = Unidade(
            id="u1", nome="1° BPChq", nome_normalizado="1 BPCHQ",
            municipio_sede_id=sede_id, ativo=True,
        )

        class _MuniFake:
            def __init__(self, mid: str, nome: str) -> None:
                self.id = mid
                self.nome = nome
                self.crpm_sigla = "CPC"

        muni_sede = _MuniFake(sede_id, "Porto Alegre")
        vertice: dict = {
            "missao_nome_raw": "Prontidao",
            "municipio_nome_raw": "",
            "em_quartel": True,
            "bpm_raws": [],
        }
        avisos = self._rodar_resolver(
            vertice,
            unidade_raw="1° BPChq",
            cache_uni={"1 BPCHQ": uni},
            cache_muni_por_id={sede_id: muni_sede},
        )
        assert vertice["municipio_id"] == sede_id
        assert vertice["municipio_nome_raw"] == "Porto Alegre"
        assert vertice["bpm_ids"] == []
        # Em quartel em POA nao exige BPM — nao deve avisar.
        assert not any("exige BPM" in a for a in avisos)

    def test_em_quartel_com_muni_explicito_nao_sobrescreve(self) -> None:
        """Se operador digitou municipio, o texto ganha — sede nao substitui."""

        class _MuniFake:
            def __init__(self, mid: str, nome: str) -> None:
                self.id = mid
                self.nome = nome
                self.crpm_sigla = "CPC"

        muni_obj = _MuniFake("muni-explicit", "Gravatai")
        uni = Unidade(
            id="u1", nome="1° BPChq", nome_normalizado="1 BPCHQ",
            municipio_sede_id="sede-poa", ativo=True,
        )
        vertice: dict = {
            "missao_nome_raw": "Prontidao",
            "municipio_nome_raw": "Gravatai",
            "em_quartel": True,
            "bpm_raws": [],
        }

        from app.services.whatsapp_catalogo import _resolver_vertice
        from app.services.catalogo_types import normalizar

        class _FakeCatalogoService:
            @staticmethod
            def lookup_missao_por_nome(_: str) -> None:
                return None

        class _FakeUnidadeService:
            @staticmethod
            def normalizar_codigo_unidade(raw: str) -> str:
                return normalizar_codigo_unidade(raw)

        avisos: list[str] = []
        _resolver_vertice(
            vertice,  # type: ignore[arg-type]
            titulo_fracao="PELOTAO ALFA",
            unidade_raw="1° BPChq",
            cache_muni={normalizar("Gravatai"): muni_obj},
            cache_muni_por_id={"muni-explicit": muni_obj},
            cache_bpm={},
            cache_uni={"1 BPCHQ": uni},
            avisos=avisos,
            catalogo_service=_FakeCatalogoService(),
            unidade_service=_FakeUnidadeService(),
        )
        assert vertice["municipio_id"] == "muni-explicit"

    def test_em_quartel_sem_unidade_no_cache_avisa(self) -> None:
        vertice: dict = {
            "missao_nome_raw": "Prontidao",
            "municipio_nome_raw": "",
            "em_quartel": True,
            "bpm_raws": [],
        }
        avisos = self._rodar_resolver(
            vertice,
            unidade_raw="9° BPChq",  # nao existe no cache
            cache_uni={},
            cache_muni_por_id={},
        )
        assert vertice["municipio_id"] is None
        assert any("sem municipio-sede cadastrado" in a for a in avisos)

    def test_nao_em_quartel_nao_usa_sede(self) -> None:
        """Quando em_quartel=False, fallback por unidade e desligado — o
        operador ja deveria ter municipio no texto."""
        sede_id: str = "sede-uuid-999"
        uni = Unidade(
            id="u1", nome="1° BPChq", nome_normalizado="1 BPCHQ",
            municipio_sede_id=sede_id, ativo=True,
        )
        vertice: dict = {
            "missao_nome_raw": "PATRULHAMENTO",
            "municipio_nome_raw": "",
            "em_quartel": False,
            "bpm_raws": [],
        }
        self._rodar_resolver(
            vertice,
            unidade_raw="1° BPChq",
            cache_uni={"1 BPCHQ": uni},
            cache_muni_por_id={},
        )
        assert vertice["municipio_id"] is None
