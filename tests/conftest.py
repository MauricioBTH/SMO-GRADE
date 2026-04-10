"""Fixtures compartilhadas para testes da Fase 4."""

import pytest
from app import create_app


# ---------- Dados mock: cabecalho ----------

def _gerar_cabecalho_mock() -> list[dict]:
    """10 dias de dados para 2 unidades."""
    base = {
        "turno": "diurno", "oficial_superior": "Maj Fulano",
        "tel_oficial": "51999990000", "tel_copom": "51999990001",
        "operador_diurno": "Sd Silva", "tel_op_diurno": "51999990002",
        "horario_op_diurno": "06:00-18:00", "operador_noturno": "Sd Costa",
        "tel_op_noturno": "51999990003", "horario_op_noturno": "18:00-06:00",
        "ef_motorizado": 5, "animais_tipo": "", "locais_atuacao": "Centro",
        "missoes_osv": "",
    }
    registros = []
    for dia in range(1, 11):
        data_str = f"{dia:02d}/03/2026"
        # 1 BPChq — crescente
        registros.append({
            **base, "unidade": "1 BPChq", "data": data_str,
            "efetivo_total": 50 + dia * 2, "oficiais": 5 + (dia % 3),
            "sargentos": 10 + dia, "soldados": 35 + dia,
            "vtrs": 8 + (dia % 4), "motos": 3, "armas_ace": 2,
            "armas_portateis": 40 + dia, "armas_longas": 10, "animais": 2,
        })
        # 2 BPChq — decrescente
        registros.append({
            **base, "unidade": "2 BPChq", "data": data_str,
            "efetivo_total": 60 - dia * 2, "oficiais": 6,
            "sargentos": 12 - (dia % 3), "soldados": 42 - dia,
            "vtrs": 10 - (dia % 4), "motos": 4, "armas_ace": 3,
            "armas_portateis": 50 - dia, "armas_longas": 12, "animais": 0,
        })
    return registros


# ---------- Dados mock: fracoes ----------

def _gerar_fracoes_mock() -> list[dict]:
    """Fracoes variadas para 3 dias, 2 unidades."""
    registros = []
    missoes = ["PATRULHAMENTO OSTENSIVO", "OPERACAO CENTRO", "ESCOLTA", "PATRULHAMENTO OSTENSIVO"]
    fracoes_nomes = ["Prontidao A", "Prontidao B", "PATRES Alpha", "Canil 01"]
    horarios = [
        ("06:00", "14:00"), ("14:00", "22:00"), ("18:00", "23:59"), ("08:00", "16:00"),
    ]

    for dia in [1, 2, 3]:
        data_str = f"{dia:02d}/03/2026"
        for i in range(4):
            unidade = "1 BPChq" if i < 2 else "2 BPChq"
            registros.append({
                "unidade": unidade, "data": data_str, "turno": "diurno",
                "fracao": fracoes_nomes[i], "comandante": f"Sgt Teste {i}",
                "telefone": "51999000000", "equipes": 2 + (i % 2),
                "pms": 8 + i * 2, "horario_inicio": horarios[i][0],
                "horario_fim": horarios[i][1], "missao": missoes[i],
            })

    # Dia extra (segunda-feira 02/03/2026 e sexta 06/03/2026)
    registros.append({
        "unidade": "1 BPChq", "data": "06/03/2026", "turno": "noturno",
        "fracao": "Prontidao A", "comandante": "Sgt Extra",
        "telefone": "51999111111", "equipes": 3, "pms": 15,
        "horario_inicio": "22:00", "horario_fim": "06:00",
        "missao": "PATRULHAMENTO OSTENSIVO",
    })

    return registros


@pytest.fixture
def cabecalho_mock() -> list[dict]:
    return _gerar_cabecalho_mock()


@pytest.fixture
def fracoes_mock() -> list[dict]:
    return _gerar_fracoes_mock()


@pytest.fixture
def cabecalho_uma_unidade() -> list[dict]:
    """Apenas 1 BPChq."""
    return [r for r in _gerar_cabecalho_mock() if r["unidade"] == "1 BPChq"]


@pytest.fixture
def cabecalho_um_registro() -> list[dict]:
    """Apenas 1 registro (edge case para tendencia)."""
    return [_gerar_cabecalho_mock()[0]]


@pytest.fixture
def fracoes_missao_vazia() -> list[dict]:
    """Fracoes com missao vazia/None."""
    base = _gerar_fracoes_mock()[:2]
    base[0]["missao"] = ""
    base[1]["missao"] = None
    return base


@pytest.fixture
def fracoes_horario_invalido() -> list[dict]:
    """Fracoes com horarios invalidos."""
    base = _gerar_fracoes_mock()[:2]
    base[0]["horario_inicio"] = "abc"
    base[0]["horario_fim"] = ""
    base[1]["horario_inicio"] = None
    base[1]["horario_fim"] = None
    return base


@pytest.fixture
def cabecalho_formato_iso() -> list[dict]:
    """Datas em formato yyyy-mm-dd (fallback)."""
    return [
        {
            "unidade": "3 BPChq", "data": "2026-03-01",
            "efetivo_total": 45, "oficiais": 4, "sargentos": 9,
            "soldados": 32, "vtrs": 7, "motos": 2, "armas_ace": 1,
            "armas_portateis": 35, "armas_longas": 8, "animais": 0,
        },
        {
            "unidade": "3 BPChq", "data": "2026-03-02",
            "efetivo_total": 48, "oficiais": 5, "sargentos": 10,
            "soldados": 33, "vtrs": 7, "motos": 3, "armas_ace": 2,
            "armas_portateis": 36, "armas_longas": 9, "animais": 1,
        },
    ]


@pytest.fixture
def app_client():
    """Flask test client (sem banco, endpoints retornam 503)."""
    app = create_app()
    app.config["TESTING"] = True
    app.config["SUPABASE_DB_URL"] = ""
    with app.test_client() as client:
        yield client


@pytest.fixture
def app_client_com_db(monkeypatch):
    """Flask test client com SUPABASE_DB_URL fake + mocks de fetch."""
    app = create_app()
    app.config["TESTING"] = True
    app.config["SUPABASE_DB_URL"] = "postgresql://fake:fake@localhost/fake"

    mock_cab = _gerar_cabecalho_mock()
    mock_frac = _gerar_fracoes_mock()

    monkeypatch.setattr(
        "app.routes.api.fetch_cabecalho_by_range",
        lambda di, df, u: mock_cab,
    )
    monkeypatch.setattr(
        "app.routes.api.fetch_fracoes_by_range",
        lambda di, df, u: mock_frac,
    )

    with app.test_client() as client:
        yield client
