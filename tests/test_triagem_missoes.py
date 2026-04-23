"""Testes da triagem humana de missoes pendentes (Fase 6.2.5).

Mocka `get_connection` via monkeypatch. Um unico FakeConn basta para isolar
contratos SQL + comportamento do service sem subir Postgres.
"""
from __future__ import annotations

from typing import Any

import pytest

from app.services import triagem_missoes
from app.services.triagem_missoes import (
    Candidato, TextoPendente, sugerir_candidatos,
)


# ---------------------------------------------------------------------------
# Fake DB infra
# ---------------------------------------------------------------------------


class FakeCursor:
    """Cursor minimal que registra calls e devolve rows pre-programados.

    `respostas` e uma fila: cada execute consome o proximo conjunto de rows.
    Tambem levanta excecoes se `raises` estiver setado para o execute N.
    """

    def __init__(self, respostas: list[list[dict]], raises: dict[int, Exception] | None = None) -> None:
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
        self._ultima = self._respostas[self._idx] if self._idx < len(self._respostas) else []
        self._idx += 1

    def fetchall(self) -> list[dict]:
        return list(self._ultima)

    def fetchone(self) -> dict | None:
        return self._ultima[0] if self._ultima else None

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *_: Any) -> None:
        return None


class FakeConn:
    def __init__(self, cur: FakeCursor) -> None:
        self._cur = cur
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self) -> FakeCursor:
        return self._cur

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


def _instalar_conn(monkeypatch: pytest.MonkeyPatch, conn: FakeConn) -> None:
    monkeypatch.setattr(
        "app.services.triagem_missoes.get_connection", lambda: conn,
    )


# ---------------------------------------------------------------------------
# 1 + 2. agrupar_pendentes — ordenacao + paginacao
# ---------------------------------------------------------------------------


class TestAgruparPendentes:

    def test_ordena_por_freq_desc_tiebreak_por_texto_asc(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rows = [
            {"texto": "PRONTIDAO LONGA", "freq": 120},
            {"texto": "ESCOLTA EVENTO", "freq": 50},
            {"texto": "ABORDAGEM X", "freq": 12},
        ]
        cur = FakeCursor([rows])
        _instalar_conn(monkeypatch, FakeConn(cur))

        resultado = triagem_missoes.agrupar_pendentes(limit=20, offset=0)

        assert [p.texto for p in resultado] == [
            "PRONTIDAO LONGA", "ESCOLTA EVENTO", "ABORDAGEM X",
        ]
        assert resultado[0].freq == 120
        sql, _ = cur.queries[0]
        assert "ORDER BY freq DESC, texto ASC" in sql
        assert "missao_id IS NULL" in sql
        # Fase 6.3: fonte e smo.fracao_missoes.missao_nome_raw
        assert "missao_nome_raw <> ''" in sql
        assert "smo.fracao_missoes" in sql

    def test_respeita_limit_e_offset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cur = FakeCursor([[]])
        _instalar_conn(monkeypatch, FakeConn(cur))
        triagem_missoes.agrupar_pendentes(limit=7, offset=14)
        _, params = cur.queries[0]
        assert params == (7, 14)


# ---------------------------------------------------------------------------
# 3 + 4 + 5. sugerir_candidatos — pura, sem DB
# ---------------------------------------------------------------------------


class TestSugerirCandidatos:

    def test_top_n_desc_acima_do_score_min(self) -> None:
        catalogo = {
            "PATRULHAMENTO OSTENSIVO": "p1",
            "PATRULHAMENTO COMUNITARIO": "p2",
            "CANIL": "c1",
        }
        resultado = sugerir_candidatos(
            "PATRULHAMENTO OSTENSIVO GERAL", catalogo, n=3, score_min=50,
        )
        assert len(resultado) >= 1
        assert resultado[0].score >= resultado[-1].score
        assert resultado[0].missao_id == "p1"

    def test_catalogo_vazio(self) -> None:
        assert sugerir_candidatos("qualquer texto", {}) == []

    def test_token_set_ratio_casa_nome_curto_em_texto_longo(self) -> None:
        """token_sort_ratio colapsaria pra ~25; token_set_ratio segura acima de 50.

        Este e o contrato que diferencia a 6.2.5 do backfill fuzzy da 6.2.
        """
        catalogo = {"PRONTIDAO": "p1"}
        texto = (
            "Prontidao, Reserva de OCD, Instrucao Centralizada "
            "e Combate aos CVLIs - Area do 21o BPM"
        )
        resultado = sugerir_candidatos(texto, catalogo, score_min=50)
        assert len(resultado) == 1
        assert resultado[0].missao_id == "p1"
        assert resultado[0].score >= 50


# ---------------------------------------------------------------------------
# 6. aplicar_mapeamento — so afeta missao_id IS NULL
# ---------------------------------------------------------------------------


class TestAplicarMapeamento:

    def test_update_filtra_por_missao_id_null(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 1o execute: SELECT nome da missao — retorna nome
        # 2o execute: UPDATE ... RETURNING id — retorna 3 rows
        rows_select = [{"nome": "ESCOLTA"}]
        rows_update = [{"id": "f1"}, {"id": "f2"}, {"id": "f3"}]
        cur = FakeCursor([rows_select, rows_update])
        conn = FakeConn(cur)
        _instalar_conn(monkeypatch, conn)

        resultado = triagem_missoes.aplicar_mapeamento(
            texto="Missao X legada", missao_id="mid-1",
        )

        assert resultado.fracoes_atualizadas == 3
        assert resultado.missao_nome == "ESCOLTA"
        assert conn.committed is True

        sql_update, params_update = cur.queries[1]
        # Fase 6.3: alvo e smo.fracao_missoes (coluna missao_nome_raw).
        assert "UPDATE smo.fracao_missoes" in sql_update
        assert "missao_id IS NULL" in sql_update
        assert "SET missao_id" in sql_update
        assert params_update[0] == "mid-1"
        assert params_update[1] == "Missao X legada"


# ---------------------------------------------------------------------------
# 7. criar_e_aplicar — rollback quando UPDATE falha
# ---------------------------------------------------------------------------


class TestCriarEAplicar:

    def test_rollback_quando_update_falha(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rows_insert = [{"id": "new-id", "nome": "NOVA MISSAO"}]
        cur = FakeCursor(
            [rows_insert, []],
            raises={1: RuntimeError("falha simulada no UPDATE")},
        )
        conn = FakeConn(cur)
        _instalar_conn(monkeypatch, conn)

        with pytest.raises(RuntimeError, match="falha simulada"):
            triagem_missoes.criar_e_aplicar(
                nome="Nova Missao", descricao=None, texto="texto legado",
            )

        assert conn.rolled_back is True
        assert conn.committed is False

    def test_nome_vazio_rejeitado(self) -> None:
        with pytest.raises(ValueError, match="nome"):
            triagem_missoes.criar_e_aplicar(
                nome="   ", descricao=None, texto="texto legado",
            )


# ---------------------------------------------------------------------------
# 8. Rota GET sem role gestor -> 403
# ---------------------------------------------------------------------------


class TestRotasSeguranca:

    def test_get_sem_login_redireciona(self) -> None:
        from app import create_app

        app = create_app()
        app.config["TESTING"] = True
        app.config["DATABASE_URL"] = ""
        with app.test_client() as client:
            resp = client.get("/admin/catalogos/triagem-missoes")
            assert resp.status_code in (302, 401)

    def test_get_com_role_operador_retorna_403(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app import create_app
        from app.models.user import User

        app = create_app()
        app.config["TESTING"] = True
        app.config["DATABASE_URL"] = ""
        app.config["WTF_CSRF_ENABLED"] = False
        app.config["SESSION_PROTECTION"] = None

        op = User(
            id="00000000-0000-0000-0000-000000000099",
            nome="Op ALEI", email="op@teste.local",
            role="operador_alei", unidade="1 BPChq",
            totp_ativo=False, ativo=True,
        )
        monkeypatch.setattr(
            "app.services.user_service.get_by_id",
            lambda uid: op if uid == op.id else None,
        )

        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["_user_id"] = op.id
                sess["_fresh"] = True
            resp = client.get("/admin/catalogos/triagem-missoes")
            assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Sanity — dataclasses frozen
# ---------------------------------------------------------------------------


class TestDataclassesFrozen:

    def test_texto_pendente_frozen(self) -> None:
        t = TextoPendente(texto="x", freq=3)
        with pytest.raises(Exception):
            t.freq = 99  # type: ignore[misc]

    def test_candidato_frozen(self) -> None:
        c = Candidato(missao_id="1", nome="X", score=80)
        with pytest.raises(Exception):
            c.score = 10  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Desfazer
# ---------------------------------------------------------------------------


class _FakeRowcountCursor(FakeCursor):
    """Variante que expõe rowcount — necessario para DELETE."""

    def __init__(
        self,
        respostas: list[list[dict]],
        rowcounts: list[int] | None = None,
    ) -> None:
        super().__init__(respostas)
        self._rowcounts = list(rowcounts) if rowcounts else []
        self.rowcount = 0

    def execute(self, sql: str, params: tuple = ()) -> None:
        super().execute(sql, params)
        if self._idx - 1 < len(self._rowcounts):
            self.rowcount = self._rowcounts[self._idx - 1]


class TestDesfazer:

    def test_zera_apenas_onde_texto_e_missao_id_batem(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rows_update = [{"id": "f1"}, {"id": "f2"}]
        cur = _FakeRowcountCursor([rows_update])
        conn = FakeConn(cur)
        _instalar_conn(monkeypatch, conn)

        resultado = triagem_missoes.desfazer_aplicacao(
            texto="texto legado", missao_id="mid-1", remover_missao=False,
        )

        assert resultado.fracoes_revertidas == 2
        assert resultado.missao_removida is False
        assert conn.committed is True

        sql_update, params = cur.queries[0]
        # Fase 6.3: desfaz no vertice (smo.fracao_missoes.missao_nome_raw).
        assert "UPDATE smo.fracao_missoes" in sql_update
        assert "SET missao_id = NULL" in sql_update
        assert "WHERE missao_nome_raw = %s AND missao_id = %s" in sql_update
        assert params == ("texto legado", "mid-1")
        assert len(cur.queries) == 1  # nao deve chamar DELETE quando remover_missao=False

    def test_remover_missao_deleta_se_sem_outras_refs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cur = _FakeRowcountCursor(
            [[{"id": "f1"}], []],
            rowcounts=[1, 1],  # UPDATE: 1 rev, DELETE: 1 removida
        )
        conn = FakeConn(cur)
        _instalar_conn(monkeypatch, conn)

        resultado = triagem_missoes.desfazer_aplicacao(
            texto="texto x", missao_id="mid-2", remover_missao=True,
        )

        assert resultado.missao_removida is True
        sql_delete, _ = cur.queries[1]
        assert "DELETE FROM smo.missoes" in sql_delete
        assert "NOT EXISTS" in sql_delete

    def test_remover_missao_nao_deleta_se_houver_outras_refs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cur = _FakeRowcountCursor(
            [[{"id": "f1"}], []],
            rowcounts=[1, 0],  # DELETE guard retorna 0 linhas
        )
        conn = FakeConn(cur)
        _instalar_conn(monkeypatch, conn)

        resultado = triagem_missoes.desfazer_aplicacao(
            texto="texto y", missao_id="mid-3", remover_missao=True,
        )

        assert resultado.fracoes_revertidas == 1
        assert resultado.missao_removida is False
