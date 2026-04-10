"""Testes — endpoints API Fase 4."""

import json
import pytest


class TestEndpointProjecoes:

    def test_503_sem_banco(self, app_client):
        resp = app_client.get("/api/analista/projecoes?data_inicio=2026-03-01&data_fim=2026-03-10")
        assert resp.status_code == 503

    def test_400_sem_datas(self, app_client_com_db):
        resp = app_client_com_db.get("/api/analista/projecoes")
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert "obrigatorios" in data["erro"]

    def test_400_data_inicio_vazia(self, app_client_com_db):
        resp = app_client_com_db.get("/api/analista/projecoes?data_inicio=&data_fim=2026-03-10")
        assert resp.status_code == 400

    def test_200_com_dados(self, app_client_com_db):
        resp = app_client_com_db.get(
            "/api/analista/projecoes?data_inicio=2026-03-01&data_fim=2026-03-10"
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "media_movel" in data
        assert "tendencia" in data
        assert "sazonalidade" in data
        assert "indicadores" in data

    def test_media_movel_presente(self, app_client_com_db):
        resp = app_client_com_db.get(
            "/api/analista/projecoes?data_inicio=2026-03-01&data_fim=2026-03-10"
        )
        data = json.loads(resp.data)
        assert len(data["media_movel"]) > 0

    def test_janela_customizada(self, app_client_com_db):
        resp = app_client_com_db.get(
            "/api/analista/projecoes?data_inicio=2026-03-01&data_fim=2026-03-10&janela=3"
        )
        assert resp.status_code == 200

    def test_janela_invalida_usa_default(self, app_client_com_db):
        resp = app_client_com_db.get(
            "/api/analista/projecoes?data_inicio=2026-03-01&data_fim=2026-03-10&janela=abc"
        )
        assert resp.status_code == 200

    def test_janela_acima_max_limitada(self, app_client_com_db):
        resp = app_client_com_db.get(
            "/api/analista/projecoes?data_inicio=2026-03-01&data_fim=2026-03-10&janela=999"
        )
        assert resp.status_code == 200

    def test_com_filtro_unidades(self, app_client_com_db):
        resp = app_client_com_db.get(
            "/api/analista/projecoes?data_inicio=2026-03-01&data_fim=2026-03-10&unidades=1+BPChq"
        )
        assert resp.status_code == 200

    def test_indicadores_estrutura(self, app_client_com_db):
        resp = app_client_com_db.get(
            "/api/analista/projecoes?data_inicio=2026-03-01&data_fim=2026-03-10"
        )
        data = json.loads(resp.data)
        indicadores = data["indicadores"]
        assert isinstance(indicadores, dict)
        for unidade in indicadores:
            for campo in indicadores[unidade]:
                ind = indicadores[unidade][campo]
                assert "media" in ind
                assert "ultimo" in ind
                assert "variacao_pct" in ind


class TestEndpointFracoesAnalytics:

    def test_503_sem_banco(self, app_client):
        resp = app_client.get("/api/analista/fracoes-analytics?data_inicio=2026-03-01&data_fim=2026-03-10")
        assert resp.status_code == 503

    def test_400_sem_datas(self, app_client_com_db):
        resp = app_client_com_db.get("/api/analista/fracoes-analytics")
        assert resp.status_code == 400

    def test_200_com_dados(self, app_client_com_db):
        resp = app_client_com_db.get(
            "/api/analista/fracoes-analytics?data_inicio=2026-03-01&data_fim=2026-03-10"
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "missoes" in data
        assert "fracoes_freq" in data
        assert "cobertura_horaria" in data
        assert "padroes_diarios" in data
        assert "concentracao" in data

    def test_missoes_ranking_presente(self, app_client_com_db):
        resp = app_client_com_db.get(
            "/api/analista/fracoes-analytics?data_inicio=2026-03-01&data_fim=2026-03-10"
        )
        data = json.loads(resp.data)
        assert "ranking" in data["missoes"]
        assert len(data["missoes"]["ranking"]) > 0

    def test_cobertura_24_horas(self, app_client_com_db):
        resp = app_client_com_db.get(
            "/api/analista/fracoes-analytics?data_inicio=2026-03-01&data_fim=2026-03-10"
        )
        data = json.loads(resp.data)
        assert len(data["cobertura_horaria"]["horas_cobertura"]) == 24

    def test_padroes_diarios_presente(self, app_client_com_db):
        resp = app_client_com_db.get(
            "/api/analista/fracoes-analytics?data_inicio=2026-03-01&data_fim=2026-03-10"
        )
        data = json.loads(resp.data)
        assert len(data["padroes_diarios"]["por_dia_semana"]) > 0

    def test_com_filtro_unidades(self, app_client_com_db):
        resp = app_client_com_db.get(
            "/api/analista/fracoes-analytics?data_inicio=2026-03-01&data_fim=2026-03-10&unidades=1+BPChq,2+BPChq"
        )
        assert resp.status_code == 200

    def test_concentracao_estrutura(self, app_client_com_db):
        resp = app_client_com_db.get(
            "/api/analista/fracoes-analytics?data_inicio=2026-03-01&data_fim=2026-03-10"
        )
        data = json.loads(resp.data)
        conc = data["concentracao"]
        assert "por_missao" in conc
        assert "por_fracao" in conc
        if conc["por_missao"]:
            m = conc["por_missao"][0]
            assert "missao" in m
            assert "pms_medio_dia" in m
