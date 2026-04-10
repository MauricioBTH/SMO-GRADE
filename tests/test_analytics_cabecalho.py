"""Testes — analytics_cabecalho (Fase 4)."""

import pytest
from app.services.analytics_cabecalho import (
    calcular_media_movel,
    calcular_tendencia,
    calcular_sazonalidade,
    calcular_indicadores,
)


# ========== calcular_media_movel ==========

class TestMediaMovel:

    def test_retorna_vazio_sem_dados(self):
        assert calcular_media_movel([]) == {}

    def test_retorna_unidades_corretas(self, cabecalho_mock):
        result = calcular_media_movel(cabecalho_mock, janela=3)
        assert "1 BPChq" in result
        assert "2 BPChq" in result

    def test_quantidade_registros_por_unidade(self, cabecalho_mock):
        result = calcular_media_movel(cabecalho_mock, janela=3)
        assert len(result["1 BPChq"]) == 10
        assert len(result["2 BPChq"]) == 10

    def test_campos_mm_presentes(self, cabecalho_mock):
        result = calcular_media_movel(cabecalho_mock, janela=3)
        registro = result["1 BPChq"][0]
        assert "efetivo_total" in registro
        assert "efetivo_total_mm" in registro
        assert "vtrs_mm" in registro

    def test_mm_primeiro_registro_igual_valor(self, cabecalho_mock):
        """Com janela=3 e min_periods=1, primeiro registro MM = proprio valor."""
        result = calcular_media_movel(cabecalho_mock, janela=3)
        r = result["1 BPChq"][0]
        assert r["efetivo_total_mm"] == float(r["efetivo_total"])

    def test_mm_suaviza_valores(self, cabecalho_mock):
        """MM com janela=5 deve ser diferente do valor bruto nos registros finais."""
        result = calcular_media_movel(cabecalho_mock, janela=5)
        registros = result["1 BPChq"]
        ultimo = registros[-1]
        assert ultimo["efetivo_total_mm"] != float(ultimo["efetivo_total"])

    def test_janela_1_mm_igual_valor(self, cabecalho_mock):
        """Com janela=1, MM deve ser igual ao valor original."""
        result = calcular_media_movel(cabecalho_mock, janela=1)
        for r in result["1 BPChq"]:
            assert r["efetivo_total_mm"] == float(r["efetivo_total"])

    def test_formato_iso_funciona(self, cabecalho_formato_iso):
        result = calcular_media_movel(cabecalho_formato_iso, janela=2)
        assert "3 BPChq" in result
        assert len(result["3 BPChq"]) == 2

    def test_uma_unidade_isolada(self, cabecalho_uma_unidade):
        result = calcular_media_movel(cabecalho_uma_unidade, janela=3)
        assert len(result) == 1
        assert "1 BPChq" in result


# ========== calcular_tendencia ==========

class TestTendencia:

    def test_retorna_vazio_sem_dados(self):
        assert calcular_tendencia([]) == {}

    def test_1bpchq_crescente(self, cabecalho_mock):
        """1 BPChq tem efetivo crescente nos dados mock."""
        result = calcular_tendencia(cabecalho_mock)
        tend = result["1 BPChq"]["efetivo_total"]
        assert tend["direcao"] == "crescente"
        assert tend["coef"] > 0

    def test_2bpchq_decrescente(self, cabecalho_mock):
        """2 BPChq tem efetivo decrescente nos dados mock."""
        result = calcular_tendencia(cabecalho_mock)
        tend = result["2 BPChq"]["efetivo_total"]
        assert tend["direcao"] == "decrescente"
        assert tend["coef"] < 0

    def test_um_registro_retorna_vazio(self, cabecalho_um_registro):
        """Com apenas 1 registro, nao ha como calcular tendencia."""
        result = calcular_tendencia(cabecalho_um_registro)
        assert result["1 BPChq"] == {}

    def test_todos_campos_presentes(self, cabecalho_mock):
        result = calcular_tendencia(cabecalho_mock)
        campos_esperados = [
            "efetivo_total", "oficiais", "sargentos", "soldados",
            "vtrs", "motos", "armas_ace", "armas_portateis", "armas_longas", "animais",
        ]
        for campo in campos_esperados:
            assert campo in result["1 BPChq"]
            assert "coef" in result["1 BPChq"][campo]
            assert "direcao" in result["1 BPChq"][campo]

    def test_direcao_valores_validos(self, cabecalho_mock):
        result = calcular_tendencia(cabecalho_mock)
        for unidade in result:
            for campo in result[unidade]:
                assert result[unidade][campo]["direcao"] in ("crescente", "decrescente", "estavel")

    def test_formato_iso(self, cabecalho_formato_iso):
        result = calcular_tendencia(cabecalho_formato_iso)
        assert "3 BPChq" in result
        assert result["3 BPChq"]["efetivo_total"]["direcao"] == "crescente"


# ========== calcular_sazonalidade ==========

class TestSazonalidade:

    def test_retorna_vazio_sem_dados(self):
        assert calcular_sazonalidade([]) == {}

    def test_retorna_mes_correto(self, cabecalho_mock):
        """Dados mock sao todos de marco (mes 3)."""
        result = calcular_sazonalidade(cabecalho_mock)
        assert "1 BPChq" in result
        meses = result["1 BPChq"]
        assert len(meses) == 1
        assert meses[0]["mes"] == 3
        assert meses[0]["mes_label"] == "Mar"

    def test_campos_media_presentes(self, cabecalho_mock):
        result = calcular_sazonalidade(cabecalho_mock)
        mes = result["1 BPChq"][0]
        assert "efetivo_total_media" in mes
        assert "vtrs_media" in mes
        assert "soldados_media" in mes

    def test_media_coerente(self, cabecalho_mock):
        """A media do efetivo deve estar entre o menor e maior valor."""
        result = calcular_sazonalidade(cabecalho_mock)
        media_ef = result["1 BPChq"][0]["efetivo_total_media"]
        # 1 BPChq: efetivo = 52, 54, ..., 70 => media = 61
        assert 50 < media_ef < 72

    def test_multiplos_meses(self):
        """Dados em jan e fev devem gerar 2 registros de sazonalidade."""
        dados = [
            {"unidade": "1 BPChq", "data": "15/01/2026",
             "efetivo_total": 50, "oficiais": 5, "sargentos": 10, "soldados": 35,
             "vtrs": 8, "motos": 3, "armas_ace": 2, "armas_portateis": 40,
             "armas_longas": 10, "animais": 2},
            {"unidade": "1 BPChq", "data": "15/02/2026",
             "efetivo_total": 60, "oficiais": 6, "sargentos": 12, "soldados": 42,
             "vtrs": 9, "motos": 4, "armas_ace": 3, "armas_portateis": 45,
             "armas_longas": 11, "animais": 3},
        ]
        result = calcular_sazonalidade(dados)
        assert len(result["1 BPChq"]) == 2
        assert result["1 BPChq"][0]["mes_label"] == "Jan"
        assert result["1 BPChq"][1]["mes_label"] == "Fev"


# ========== calcular_indicadores ==========

class TestIndicadores:

    def test_retorna_vazio_sem_dados(self):
        assert calcular_indicadores([]) == {}

    def test_ultimo_valor_correto(self, cabecalho_mock):
        result = calcular_indicadores(cabecalho_mock)
        # 1 BPChq: ultimo dia = 10/03, efetivo = 50 + 10*2 = 70
        assert result["1 BPChq"]["efetivo_total"]["ultimo"] == 70

    def test_media_coerente(self, cabecalho_mock):
        result = calcular_indicadores(cabecalho_mock)
        media = result["1 BPChq"]["efetivo_total"]["media"]
        assert 50 < media < 72

    def test_variacao_positiva_1bpchq(self, cabecalho_mock):
        """1 BPChq cresce, variacao deve ser positiva."""
        result = calcular_indicadores(cabecalho_mock)
        var = result["1 BPChq"]["efetivo_total"]["variacao_pct"]
        assert var > 0

    def test_variacao_negativa_2bpchq(self, cabecalho_mock):
        """2 BPChq decresce, variacao deve ser negativa."""
        result = calcular_indicadores(cabecalho_mock)
        var = result["2 BPChq"]["efetivo_total"]["variacao_pct"]
        assert var < 0

    def test_variacao_zero_quando_primeiro_zero(self):
        """Se primeiro valor for 0, variacao_pct = 0 (sem divisao por zero)."""
        dados = [
            {"unidade": "X", "data": "01/01/2026",
             "efetivo_total": 0, "oficiais": 0, "sargentos": 0, "soldados": 0,
             "vtrs": 0, "motos": 0, "armas_ace": 0, "armas_portateis": 0,
             "armas_longas": 0, "animais": 0},
            {"unidade": "X", "data": "02/01/2026",
             "efetivo_total": 50, "oficiais": 5, "sargentos": 10, "soldados": 35,
             "vtrs": 8, "motos": 3, "armas_ace": 2, "armas_portateis": 40,
             "armas_longas": 10, "animais": 2},
        ]
        result = calcular_indicadores(dados)
        assert result["X"]["efetivo_total"]["variacao_pct"] == 0.0

    def test_todos_campos_numericos_presentes(self, cabecalho_mock):
        result = calcular_indicadores(cabecalho_mock)
        campos = [
            "efetivo_total", "oficiais", "sargentos", "soldados",
            "vtrs", "motos", "armas_ace", "armas_portateis", "armas_longas", "animais",
        ]
        for campo in campos:
            assert campo in result["1 BPChq"]
            ind = result["1 BPChq"][campo]
            assert "media" in ind
            assert "ultimo" in ind
            assert "variacao_pct" in ind

    def test_tipos_retorno(self, cabecalho_mock):
        result = calcular_indicadores(cabecalho_mock)
        ind = result["1 BPChq"]["efetivo_total"]
        assert isinstance(ind["media"], float)
        assert isinstance(ind["ultimo"], int)
        assert isinstance(ind["variacao_pct"], float)
