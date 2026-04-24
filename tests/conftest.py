"""Fixtures compartilhadas para testes."""
from __future__ import annotations

import pytest

from app import create_app
from app.models.user import User
from app.services.catalogo_types import Unidade


# ---------- Catalogo de unidades (mock DB-free) ----------

_UNIDADES_FAKE: list[Unidade] = [
    Unidade(
        id=f"00000000-0000-0000-0000-00000000010{n}",
        nome=f"{n}° BPChq",
        nome_normalizado=f"{n} BPCHQ",
        municipio_sede_id=f"00000000-0000-0000-0000-00000000020{n}",
        ativo=True,
    )
    for n in range(1, 7)
] + [
    Unidade(
        id="00000000-0000-0000-0000-000000000107",
        nome="4° RPMon",
        nome_normalizado="4 RPMON",
        municipio_sede_id="00000000-0000-0000-0000-000000000207",
        ativo=True,
    )
]

_NOMES_FAKE: frozenset[str] = frozenset(
    {u.nome for u in _UNIDADES_FAKE}
    | {u.nome.replace("° ", " ") for u in _UNIDADES_FAKE}
)


@pytest.fixture(autouse=True)
def _mock_unidade_service(monkeypatch):
    """Evita hit no DB de catalogo em qualquer teste que importe rotas/services
    que dependem de unidade_service. Testes DB-integrados podem re-mockar."""
    monkeypatch.setattr(
        "app.services.unidade_service.listar_unidades",
        lambda somente_ativas=True: list(_UNIDADES_FAKE),
    )
    monkeypatch.setattr(
        "app.services.unidade_service.get_nomes_validos",
        lambda: _NOMES_FAKE,
    )
    monkeypatch.setattr(
        "app.services.user_service.get_nomes_validos",
        lambda: _NOMES_FAKE,
        raising=False,
    )
    monkeypatch.setattr(
        "app.routes.operador.get_nomes_validos",
        lambda: _NOMES_FAKE,
        raising=False,
    )


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
    return [r for r in _gerar_cabecalho_mock() if r["unidade"] == "1 BPChq"]


@pytest.fixture
def cabecalho_um_registro() -> list[dict]:
    return [_gerar_cabecalho_mock()[0]]


@pytest.fixture
def fracoes_missao_vazia() -> list[dict]:
    base = _gerar_fracoes_mock()[:2]
    base[0]["missao"] = ""
    base[1]["missao"] = None
    return base


@pytest.fixture
def fracoes_horario_invalido() -> list[dict]:
    base = _gerar_fracoes_mock()[:2]
    base[0]["horario_inicio"] = "abc"
    base[0]["horario_fim"] = ""
    base[1]["horario_inicio"] = None
    base[1]["horario_fim"] = None
    return base


@pytest.fixture
def cabecalho_formato_iso() -> list[dict]:
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


# ---------- Usuario fake para autenticacao em testes ----------

def _user_gestor_fake() -> User:
    return User(
        id="00000000-0000-0000-0000-000000000001",
        nome="Gestor Teste",
        email="gestor@teste.local",
        role="gestor",
        unidade=None,
        totp_ativo=False,
        ativo=True,
    )


def _login_como(client, monkeypatch, user: User) -> None:
    monkeypatch.setattr(
        "app.user_service.get_by_id",
        lambda uid: user if uid == user.id else None,
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.user_service.get_by_id",
        lambda uid: user if uid == user.id else None,
    )
    with client.session_transaction() as sess:
        sess["_user_id"] = user.id
        sess["_fresh"] = True


@pytest.fixture
def app_client(monkeypatch):
    """Flask test client autenticado como Gestor, sem banco."""
    app = create_app()
    app.config["TESTING"] = True
    app.config["DATABASE_URL"] = ""
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SESSION_PROTECTION"] = None
    with app.test_client() as client:
        _login_como(client, monkeypatch, _user_gestor_fake())
        yield client


@pytest.fixture
def app_client_com_db(monkeypatch):
    """Flask test client autenticado como Gestor + DB fake + fetch mockados."""
    app = create_app()
    app.config["TESTING"] = True
    app.config["DATABASE_URL"] = "postgresql://fake:fake@localhost/fake"
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SESSION_PROTECTION"] = None

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
        _login_como(client, monkeypatch, _user_gestor_fake())
        yield client
