"""Testes — analytics_fracoes (Fase 4)."""

import pytest
from app.services.analytics_fracoes import (
    analisar_missoes,
    analisar_fracoes_freq,
    analisar_cobertura_horaria,
    analisar_padroes_diarios,
    analisar_concentracao,
)


# ========== analisar_missoes ==========

class TestMissoes:

    def test_retorna_vazio_sem_dados(self):
        result = analisar_missoes([])
        assert result == {"ranking": [], "evolucao": {}}

    def test_ranking_ordenado_por_frequencia(self, fracoes_mock):
        result = analisar_missoes(fracoes_mock)
        ranking = result["ranking"]
        assert len(ranking) > 0
        # PATRULHAMENTO OSTENSIVO aparece mais vezes (3 fracoes x 3 dias + 1 extra)
        assert ranking[0]["missao"] == "PATRULHAMENTO OSTENSIVO"

    def test_ranking_campos_presentes(self, fracoes_mock):
        result = analisar_missoes(fracoes_mock)
        r = result["ranking"][0]
        assert "missao" in r
        assert "total" in r
        assert "pms_total" in r
        assert "equipes_total" in r

    def test_ranking_total_correto(self, fracoes_mock):
        result = analisar_missoes(fracoes_mock)
        ranking = result["ranking"]
        # PATRULHAMENTO OSTENSIVO: fracoes[0] e fracoes[3] por dia (3 dias) + 1 extra = 7
        patr = next(r for r in ranking if r["missao"] == "PATRULHAMENTO OSTENSIVO")
        assert patr["total"] == 7

    def test_evolucao_contem_top_missoes(self, fracoes_mock):
        result = analisar_missoes(fracoes_mock)
        evolucao = result["evolucao"]
        assert "PATRULHAMENTO OSTENSIVO" in evolucao

    def test_evolucao_registros_por_data(self, fracoes_mock):
        result = analisar_missoes(fracoes_mock)
        evo = result["evolucao"]["PATRULHAMENTO OSTENSIVO"]
        assert len(evo) > 0
        assert "data" in evo[0]
        assert "count" in evo[0]
        assert "pms" in evo[0]

    def test_missao_vazia_ignorada(self, fracoes_missao_vazia):
        result = analisar_missoes(fracoes_missao_vazia)
        assert result["ranking"] == []

    def test_ranking_max_20(self):
        """Ranking deve retornar no maximo 20 missoes."""
        fracoes = []
        for i in range(25):
            fracoes.append({
                "unidade": "1 BPChq", "data": "01/01/2026", "turno": "diurno",
                "fracao": "Frac", "comandante": "Cmd", "telefone": "000",
                "equipes": 1, "pms": 5, "horario_inicio": "06:00",
                "horario_fim": "14:00", "missao": f"MISSAO_{i:02d}",
            })
        result = analisar_missoes(fracoes)
        assert len(result["ranking"]) <= 20


# ========== analisar_fracoes_freq ==========

class TestFracoesFreq:

    def test_retorna_vazio_sem_dados(self):
        result = analisar_fracoes_freq([])
        assert result == {"por_unidade": {}, "geral": []}

    def test_geral_contem_todas_fracoes(self, fracoes_mock):
        result = analisar_fracoes_freq(fracoes_mock)
        geral = result["geral"]
        nomes = [r["fracao"] for r in geral]
        assert "Prontidao A" in nomes
        assert "Prontidao B" in nomes
        assert "PATRES Alpha" in nomes
        assert "Canil 01" in nomes

    def test_por_unidade_chaves_corretas(self, fracoes_mock):
        result = analisar_fracoes_freq(fracoes_mock)
        assert "1 BPChq" in result["por_unidade"]
        assert "2 BPChq" in result["por_unidade"]

    def test_geral_campos_presentes(self, fracoes_mock):
        result = analisar_fracoes_freq(fracoes_mock)
        r = result["geral"][0]
        assert "fracao" in r
        assert "total" in r
        assert "pms_total" in r

    def test_por_unidade_total_coerente(self, fracoes_mock):
        result = analisar_fracoes_freq(fracoes_mock)
        # 1 BPChq tem Prontidao A e Prontidao B (+ extra Prontidao A)
        fracoes_1bp = result["por_unidade"]["1 BPChq"]
        total = sum(f["total"] for f in fracoes_1bp)
        assert total > 0

    def test_geral_max_20(self):
        """Geral deve retornar no maximo 20."""
        fracoes = []
        for i in range(25):
            fracoes.append({
                "unidade": "1 BPChq", "data": "01/01/2026", "turno": "d",
                "fracao": f"Fracao_{i:02d}", "comandante": "C", "telefone": "0",
                "equipes": 1, "pms": 3, "horario_inicio": "06:00",
                "horario_fim": "14:00", "missao": "M",
            })
        result = analisar_fracoes_freq(fracoes)
        assert len(result["geral"]) <= 20


# ========== analisar_cobertura_horaria ==========

class TestCoberturaHoraria:

    def test_retorna_vazio_sem_dados(self):
        result = analisar_cobertura_horaria([])
        assert result == {"por_turno": [], "por_unidade_turno": {}, "horas_cobertura": []}

    def test_24_horas_na_cobertura(self, fracoes_mock):
        result = analisar_cobertura_horaria(fracoes_mock)
        assert len(result["horas_cobertura"]) == 24

    def test_horas_cobertura_estrutura(self, fracoes_mock):
        result = analisar_cobertura_horaria(fracoes_mock)
        h = result["horas_cobertura"][0]
        assert "hora" in h
        assert "pms_medio" in h
        assert h["hora"] == 0

    def test_por_turno_classificacao_correta(self, fracoes_mock):
        result = analisar_cobertura_horaria(fracoes_mock)
        turnos = [t["turno"] for t in result["por_turno"]]
        # Deve ter manha (06:00, 08:00), tarde (14:00), noite (18:00, 22:00)
        assert "manha" in turnos
        assert "tarde" in turnos
        assert "noite" in turnos

    def test_por_turno_campos_presentes(self, fracoes_mock):
        result = analisar_cobertura_horaria(fracoes_mock)
        t = result["por_turno"][0]
        assert "turno" in t
        assert "total_fracoes" in t
        assert "pms_total" in t
        assert "equipes_total" in t

    def test_por_unidade_turno_presente(self, fracoes_mock):
        result = analisar_cobertura_horaria(fracoes_mock)
        assert "1 BPChq" in result["por_unidade_turno"]

    def test_horario_invalido_classificado_indefinido(self, fracoes_horario_invalido):
        result = analisar_cobertura_horaria(fracoes_horario_invalido)
        turnos = [t["turno"] for t in result["por_turno"]]
        assert "indefinido" in turnos

    def test_horas_com_cobertura_positiva(self, fracoes_mock):
        """Horas entre 06:00 e 22:00 devem ter cobertura > 0."""
        result = analisar_cobertura_horaria(fracoes_mock)
        horas = result["horas_cobertura"]
        # Hora 10 deve ter PMs (Prontidao A 06-14 e Canil 08-16)
        hora_10 = next(h for h in horas if h["hora"] == 10)
        assert hora_10["pms_medio"] > 0

    def test_pms_medio_tipo_numerico(self, fracoes_mock):
        result = analisar_cobertura_horaria(fracoes_mock)
        for h in result["horas_cobertura"]:
            assert isinstance(h["pms_medio"], (int, float))


# ========== analisar_padroes_diarios ==========

class TestPadroesDiarios:

    def test_retorna_vazio_sem_dados(self):
        result = analisar_padroes_diarios([])
        assert result == {"por_dia_semana": []}

    def test_contem_dias_da_semana(self, fracoes_mock):
        result = analisar_padroes_diarios(fracoes_mock)
        dias = result["por_dia_semana"]
        assert len(dias) > 0

    def test_campos_presentes(self, fracoes_mock):
        result = analisar_padroes_diarios(fracoes_mock)
        d = result["por_dia_semana"][0]
        assert "dia" in d
        assert "dia_label" in d
        assert "fracoes_media" in d
        assert "pms_medio" in d

    def test_dia_label_valido(self, fracoes_mock):
        result = analisar_padroes_diarios(fracoes_mock)
        labels_validos = {"Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"}
        for d in result["por_dia_semana"]:
            assert d["dia_label"] in labels_validos

    def test_dia_numerico_0_a_6(self, fracoes_mock):
        result = analisar_padroes_diarios(fracoes_mock)
        for d in result["por_dia_semana"]:
            assert 0 <= d["dia"] <= 6

    def test_pms_medio_positivo(self, fracoes_mock):
        result = analisar_padroes_diarios(fracoes_mock)
        for d in result["por_dia_semana"]:
            assert d["pms_medio"] >= 0

    def test_fracoes_media_positiva(self, fracoes_mock):
        result = analisar_padroes_diarios(fracoes_mock)
        for d in result["por_dia_semana"]:
            assert d["fracoes_media"] > 0


# ========== analisar_concentracao ==========

class TestConcentracao:

    def test_retorna_vazio_sem_dados(self):
        result = analisar_concentracao([])
        assert result == {"por_missao": [], "por_fracao": []}

    def test_por_missao_presente(self, fracoes_mock):
        result = analisar_concentracao(fracoes_mock)
        assert len(result["por_missao"]) > 0

    def test_por_fracao_presente(self, fracoes_mock):
        result = analisar_concentracao(fracoes_mock)
        assert len(result["por_fracao"]) > 0

    def test_por_missao_campos(self, fracoes_mock):
        result = analisar_concentracao(fracoes_mock)
        m = result["por_missao"][0]
        assert "missao" in m
        assert "pms_medio_dia" in m
        assert "equipes_medio_dia" in m

    def test_por_fracao_campos(self, fracoes_mock):
        result = analisar_concentracao(fracoes_mock)
        f = result["por_fracao"][0]
        assert "fracao" in f
        assert "pms_medio_dia" in f
        assert "equipes_medio_dia" in f

    def test_ordenado_por_pms_desc(self, fracoes_mock):
        result = analisar_concentracao(fracoes_mock)
        pms_list = [m["pms_medio_dia"] for m in result["por_missao"]]
        assert pms_list == sorted(pms_list, reverse=True)

    def test_missao_vazia_ignorada(self, fracoes_missao_vazia):
        result = analisar_concentracao(fracoes_missao_vazia)
        assert result["por_missao"] == []

    def test_max_15_missoes(self):
        """Deve retornar no maximo 15 missoes."""
        fracoes = []
        for i in range(20):
            fracoes.append({
                "unidade": "1 BPChq", "data": "01/01/2026", "turno": "d",
                "fracao": "F", "comandante": "C", "telefone": "0",
                "equipes": 1, "pms": 5, "horario_inicio": "06:00",
                "horario_fim": "14:00", "missao": f"Missao {i}",
            })
        result = analisar_concentracao(fracoes)
        assert len(result["por_missao"]) <= 15

    def test_tipos_numericos(self, fracoes_mock):
        result = analisar_concentracao(fracoes_mock)
        for m in result["por_missao"]:
            assert isinstance(m["pms_medio_dia"], float)
            assert isinstance(m["equipes_medio_dia"], float)
