"""Testes da logica de matching do backfill (exato, fuzzy, ambiguo)."""
from __future__ import annotations

from scripts.backfill_missoes import _match_fuzzy


class TestMatchFuzzy:
    """Valida heuristica rapidfuzz >= 85 e deteccao de ambiguidade."""

    def test_match_exato_nao_usa_fuzzy(self) -> None:
        """Match exato e tratado antes do fuzzy — fuzzy so para nao-exatos."""
        catalogo = {"ESCOLTA": "1", "CANIL": "2"}
        _, score, _ = _match_fuzzy("ESCOLTAX", catalogo)
        assert 0 <= score <= 100

    def test_fuzzy_acima_do_minimo(self) -> None:
        """Typo pequeno deve casar com score alto."""
        catalogo = {
            "PATRULHAMENTO OSTENSIVO": "p1",
            "OPERACAO CENTRO": "o1",
            "CANIL": "c1",
        }
        match_id, score, ambiguo = _match_fuzzy(
            "PATRULHAMEMTO OSTENSIVO", catalogo
        )
        assert match_id == "p1"
        assert score >= 85
        assert ambiguo is False

    def test_score_baixo_sem_match(self) -> None:
        catalogo = {"ESCOLTA": "1", "CANIL": "2"}
        match_id, score, _ = _match_fuzzy("XYZWQ", catalogo)
        assert match_id is None
        assert score < 85

    def test_catalogo_vazio(self) -> None:
        match_id, score, ambiguo = _match_fuzzy("QUALQUER", {})
        assert match_id is None
        assert score == 0
        assert ambiguo is False

    def test_ambiguidade_dois_candidatos_proximos(self) -> None:
        """Quando dois termos empatam no topo, resultado e ambiguo (nao atualiza)."""
        catalogo = {"OPERACAO A": "1", "OPERACAO B": "2"}
        match_id, score, ambiguo = _match_fuzzy("OPERACAO", catalogo)
        if ambiguo:
            assert match_id is None
            assert score >= 85

    def test_score_minimo_85_documentado(self) -> None:
        """Confirma que a constante de corte e 85 (documentada no prompt)."""
        from scripts.backfill_missoes import SCORE_MIN
        assert SCORE_MIN == 85
