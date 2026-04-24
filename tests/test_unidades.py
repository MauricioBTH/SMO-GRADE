"""Testes da Fase 6.4.1 — catalogo de unidades + fallback municipio-sede."""
from __future__ import annotations

from typing import Any

import psycopg2.errors
import pytest

from app.services import unidade_service
from app.services.catalogo_types import Unidade
from app.services.unidade_service import (
    atualizar_unidade, criar_unidade, normalizar_codigo_unidade,
)


# ---------------------------------------------------------------------------
# Fake DB infra (espelha padrao de test_triagem_missoes)
# ---------------------------------------------------------------------------


class _FakeCursor:
    def __init__(
        self,
        respostas: list[list[dict]],
        raises: dict[int, Exception] | None = None,
    ) -> None:
        self._respostas = list(respostas)
        self._raises = raises or {}
        self._idx = 0
        self.queries: list[tuple[str, tuple]] = []
        self._ultima: list[dict] = []

    def execute(self, sql: str, params: tuple = ()) -> None:
        self.queries.append((sql, tuple(params) if params else ()))
        if self._idx in self._raises:
            exc = self._raises[self._idx]
            self._idx += 1
            raise exc
        self._ultima = (
            self._respostas[self._idx] if self._idx < len(self._respostas) else []
        )
        self._idx += 1

    def fetchall(self) -> list[dict]:
        return list(self._ultima)

    def fetchone(self) -> dict | None:
        return self._ultima[0] if self._ultima else None

    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, *_: Any) -> None:
        return None


class _FakeConn:
    def __init__(self, cur: _FakeCursor) -> None:
        self._cur = cur
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self) -> _FakeCursor:
        return self._cur

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


def _instalar_conn(monkeypatch: pytest.MonkeyPatch, conn: _FakeConn) -> None:
    monkeypatch.setattr(
        "app.services.unidade_service.get_connection", lambda: conn,
    )


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


# ---------------------------------------------------------------------------
# B2 — mutacoes (criar/atualizar unidade) via Admin UI
# ---------------------------------------------------------------------------


_UUID_NEW = "00000000-0000-0000-0000-000000000777"
_UUID_SEDE = "00000000-0000-0000-0000-000000000abc"


def _row_nova(nome: str, normalizado: str) -> dict:
    return {
        "id": _UUID_NEW, "nome": nome, "nome_normalizado": normalizado,
        "municipio_sede_id": _UUID_SEDE, "ativo": True,
    }


class TestCriarUnidade:

    def test_happy_path_retorna_unidade_e_invalida_cache(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cur = _FakeCursor([[_row_nova("7° BPChq", "7 BPCHQ")]])
        conn = _FakeConn(cur)
        _instalar_conn(monkeypatch, conn)
        chamadas: list[None] = []
        monkeypatch.setattr(
            unidade_service, "invalidar_cache_nomes",
            lambda: chamadas.append(None),
        )

        nova = criar_unidade(
            {"nome": "  7° BPChq  ", "municipio_sede_id": _UUID_SEDE}
        )

        assert nova.id == _UUID_NEW
        assert nova.nome == "7° BPChq"
        assert nova.nome_normalizado == "7 BPCHQ"
        assert conn.committed is True
        sql, params = cur.queries[0]
        assert "INSERT INTO smo.unidades" in sql
        assert params == ("7° BPChq", "7 BPCHQ", _UUID_SEDE)
        assert len(chamadas) == 1

    def test_nome_vazio_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _instalar_conn(monkeypatch, _FakeConn(_FakeCursor([])))
        with pytest.raises(ValueError, match="Nome obrigatorio"):
            criar_unidade({"nome": "   ", "municipio_sede_id": _UUID_SEDE})

    def test_nome_excede_60_chars_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _instalar_conn(monkeypatch, _FakeConn(_FakeCursor([])))
        with pytest.raises(ValueError, match="excede"):
            criar_unidade(
                {"nome": "1 " + "X" * 100, "municipio_sede_id": _UUID_SEDE}
            )

    def test_sede_obrigatoria(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _instalar_conn(monkeypatch, _FakeConn(_FakeCursor([])))
        with pytest.raises(ValueError, match="Municipio sede obrigatorio"):
            criar_unidade({"nome": "7° BPChq", "municipio_sede_id": ""})

    def test_nome_sem_digito_sigla_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _instalar_conn(monkeypatch, _FakeConn(_FakeCursor([])))
        with pytest.raises(ValueError, match="<numero> <sigla>"):
            criar_unidade(
                {"nome": "SemDigito", "municipio_sede_id": _UUID_SEDE}
            )

    def test_unique_violation_vira_valueerror(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cur = _FakeCursor(
            [[]], raises={0: psycopg2.errors.UniqueViolation("dup")},
        )
        conn = _FakeConn(cur)
        _instalar_conn(monkeypatch, conn)
        with pytest.raises(ValueError, match="ja existe"):
            criar_unidade(
                {"nome": "1° BPChq", "municipio_sede_id": _UUID_SEDE}
            )
        assert conn.rolled_back is True
        assert conn.committed is False

    def test_foreign_key_violation_vira_valueerror(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cur = _FakeCursor(
            [[]], raises={0: psycopg2.errors.ForeignKeyViolation("fk")},
        )
        conn = _FakeConn(cur)
        _instalar_conn(monkeypatch, conn)
        with pytest.raises(ValueError, match="Municipio sede invalido"):
            criar_unidade(
                {"nome": "7° BPChq", "municipio_sede_id": "uuid-inexistente"}
            )
        assert conn.rolled_back is True


class TestAtualizarUnidade:

    def test_happy_path_renome(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cur = _FakeCursor([[_row_nova("2° BPChq", "2 BPCHQ")]])
        conn = _FakeConn(cur)
        _instalar_conn(monkeypatch, conn)
        chamadas: list[None] = []
        monkeypatch.setattr(
            unidade_service, "invalidar_cache_nomes",
            lambda: chamadas.append(None),
        )

        atualizada = atualizar_unidade(
            "uuid-u1", {"nome": "2° BPChq"},
        )

        assert atualizada.nome == "2° BPChq"
        assert conn.committed is True
        sql, params = cur.queries[0]
        assert "UPDATE smo.unidades" in sql
        assert "nome = %s" in sql
        assert "nome_normalizado = %s" in sql
        assert params == ("2° BPChq", "2 BPCHQ", "uuid-u1")
        assert len(chamadas) == 1

    def test_desativar(self, monkeypatch: pytest.MonkeyPatch) -> None:
        row = dict(_row_nova("1° BPChq", "1 BPCHQ"))
        row["ativo"] = False
        cur = _FakeCursor([[row]])
        _instalar_conn(monkeypatch, _FakeConn(cur))

        atualizada = atualizar_unidade("uuid-u1", {"ativo": False})
        assert atualizada.ativo is False
        _, params = cur.queries[0]
        assert params == (False, "uuid-u1")

    def test_nada_pra_atualizar_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _instalar_conn(monkeypatch, _FakeConn(_FakeCursor([])))
        with pytest.raises(ValueError, match="Nada para atualizar"):
            atualizar_unidade("uuid-u1", {})

    def test_nome_vazio_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _instalar_conn(monkeypatch, _FakeConn(_FakeCursor([])))
        with pytest.raises(ValueError, match="nao pode ser vazio"):
            atualizar_unidade("uuid-u1", {"nome": "   "})

    def test_unidade_inexistente_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cur = _FakeCursor([[]])
        _instalar_conn(monkeypatch, _FakeConn(cur))
        with pytest.raises(ValueError, match="nao encontrada"):
            atualizar_unidade("uuid-inexistente", {"ativo": False})

    def test_unique_violation_vira_valueerror(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cur = _FakeCursor(
            [[]], raises={0: psycopg2.errors.UniqueViolation("dup")},
        )
        conn = _FakeConn(cur)
        _instalar_conn(monkeypatch, conn)
        with pytest.raises(ValueError, match="outra unidade com esse nome"):
            atualizar_unidade("uuid-u1", {"nome": "1° BPChq"})
        assert conn.rolled_back is True
