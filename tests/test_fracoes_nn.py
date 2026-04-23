"""Testes do modelo N:N (Fases 6.3 e 6.4).

Cobre:
  - Validator `validate_fracoes` repassa `missoes` do JSON do preview.
  - `validar_vertices_n_n` bloqueia fracoes sem vertice ou sem municipio_id.
  - `validar_vertices_n_n` exige BPM em POA quando nao em_quartel.
  - Parser canonico emite MissaoVertice para blocos 'Missao N: ... Municipio: ...'.
  - `bpm_service.normalizar_codigo_bpm` cobre as variantes esperadas.
  - Fase 6.4: `parse_lista_bpms` e o parser canonico cobrem as 8 sintaxes de
    lista de BPMs em POA.
"""
from __future__ import annotations

import pytest

from app.services.bpm_service import normalizar_codigo_bpm, parse_lista_bpms
from app.services.whatsapp_parser import parse_texto_whatsapp
from app.validators.xlsx_validator import (
    MissaoVertice, validar_vertices_n_n, validate_fracoes,
)


# ---------------------------------------------------------------------------
# bpm_service.normalizar_codigo_bpm
# ---------------------------------------------------------------------------


class TestNormalizarCodigoBpm:
    @pytest.mark.parametrize("entrada,esperado", [
        ("20 BPM", "20 BPM"),
        ("20° BPM", "20 BPM"),
        ("20BPM", "20 BPM"),
        ("20 bpm", "20 BPM"),
        ("1 BPM", "1 BPM"),
        ("1º BPM", "1 BPM"),
        ("", ""),
        ("sem numero", ""),
    ])
    def test_variantes(self, entrada: str, esperado: str) -> None:
        assert normalizar_codigo_bpm(entrada) == esperado


# ---------------------------------------------------------------------------
# validate_fracoes — passa `missoes` do preview
# ---------------------------------------------------------------------------


class TestValidateFracoesMissoes:
    def test_repassa_missoes(self) -> None:
        rows = [{
            "unidade": "1 BPChq", "data": "01/04/2026", "turno": "Diurno",
            "fracao": "F1", "comandante": "CMT", "telefone": "999",
            "equipes": 1, "pms": 10, "horario_inicio": "07:30",
            "horario_fim": "19:30", "missao": "",
            "missoes": [
                {
                    "ordem": 1, "missao_nome_raw": "Prontidao",
                    "municipio_nome_raw": "Porto Alegre",
                    "municipio_id": "mu-1", "bpm_ids": [],
                    "bpm_raws": [], "em_quartel": True,
                    "missao_id": None,
                },
            ],
        }]
        out = validate_fracoes(rows)
        assert len(out) == 1
        assert out[0]["missoes"]
        v0: MissaoVertice = out[0]["missoes"][0]
        assert v0["municipio_id"] == "mu-1"
        assert v0["em_quartel"] is True
        # em_quartel forca bpm_ids=[] mesmo se vier no payload
        assert v0["bpm_ids"] == []

    def test_em_quartel_forca_bpm_none(self) -> None:
        rows = [{
            "unidade": "1 BPChq", "data": "01/04/2026", "turno": "Diurno",
            "fracao": "F1", "comandante": "CMT", "telefone": "999",
            "equipes": 1, "pms": 10, "horario_inicio": "07:30",
            "horario_fim": "19:30", "missao": "",
            "missoes": [{
                "ordem": 1, "missao_nome_raw": "Pernoite",
                "municipio_nome_raw": "Porto Alegre",
                "municipio_id": "mu-1", "bpm_ids": ["bpm-x"],
                "em_quartel": True,
            }],
        }]
        out = validate_fracoes(rows)
        assert out[0]["missoes"][0]["bpm_ids"] == []


# ---------------------------------------------------------------------------
# validar_vertices_n_n — regras de bloqueio
# ---------------------------------------------------------------------------


class TestValidarVerticesNN:
    def _frac(self, missoes: list[dict]) -> dict:
        return {
            "unidade": "1 BPChq", "data": "01/04/2026", "turno": "Diurno",
            "fracao": "F1", "comandante": "CMT", "telefone": "",
            "equipes": 1, "pms": 5, "horario_inicio": "",
            "horario_fim": "", "missao": "", "missoes": missoes,
        }

    def test_sem_missoes_falha(self) -> None:
        with pytest.raises(ValueError, match="sem missoes"):
            validar_vertices_n_n([self._frac([])])

    def test_sem_municipio_falha(self) -> None:
        with pytest.raises(ValueError, match="sem municipio"):
            validar_vertices_n_n([self._frac([
                {"missao_nome_raw": "X", "municipio_id": None,
                 "em_quartel": False},
            ])])

    def test_poa_sem_bpm_sem_quartel_falha(self) -> None:
        idx = {"mu-1": "CPC"}
        with pytest.raises(ValueError, match="Porto Alegre exige BPM"):
            validar_vertices_n_n([self._frac([
                {"missao_nome_raw": "X", "municipio_id": "mu-1",
                 "em_quartel": False, "bpm_ids": []},
            ])], municipios_index=idx)

    def test_poa_com_bpm_ok(self) -> None:
        idx = {"mu-1": "CPC"}
        # nao levanta
        validar_vertices_n_n([self._frac([
            {"missao_nome_raw": "X", "municipio_id": "mu-1",
             "em_quartel": False, "bpm_ids": ["bpm-a"]},
        ])], municipios_index=idx)

    def test_poa_com_multiplos_bpms_ok(self) -> None:
        """Fase 6.4: uma missao POA com 2+ BPMs passa validacao."""
        idx = {"mu-1": "CPC"}
        validar_vertices_n_n([self._frac([
            {"missao_nome_raw": "Policiamento Ostensivo",
             "municipio_id": "mu-1", "em_quartel": False,
             "bpm_ids": ["bpm-a", "bpm-b"]},
        ])], municipios_index=idx)

    def test_poa_em_quartel_dispensa_bpm(self) -> None:
        idx = {"mu-1": "CPC"}
        validar_vertices_n_n([self._frac([
            {"missao_nome_raw": "Pernoite", "municipio_id": "mu-1",
             "em_quartel": True, "bpm_ids": []},
        ])], municipios_index=idx)

    def test_fora_de_poa_dispensa_bpm(self) -> None:
        idx = {"mu-2": "RM"}
        validar_vertices_n_n([self._frac([
            {"missao_nome_raw": "Patrulha", "municipio_id": "mu-2",
             "em_quartel": False, "bpm_ids": []},
        ])], municipios_index=idx)


# ---------------------------------------------------------------------------
# Parser canonico — "Missao N: ... Municipio: ... (X BPM)"
# ---------------------------------------------------------------------------


_HEADER_1BPCHQ = (
    "*DADOS PARA PLANILHA DE COMANDO E CONTROLE DE MEIOS OPERACIONAIS*\n"
    "*BRIGADA MILITAR*\n"
    "*CPChq*\n"
    "*1° BATALHÃO DE POLICIA DE CHOQUE*\n"
    "*Previsão do dia 01/04/2026*\n\n"
)

_RODAPE = (
    "\nData: 01/04/2026\n"
    "Turno: 2/3\n"
    "1. Efetivo Total: 30\n"
    "   1.1 Oficial: 01\n"
    "   1.2 Sgt: 05\n"
    "   1.3 SD: 24\n"
    "2. VTRs: 3 + 0 motos\n"
    "3. Efetivo Motorizado: 12\n"
    "4. Armas de Condução Elétrica Empregadas: 05\n"
    "5. Armas Portáteis Empregadas: 30\n"
    "6. Armas Longas Empregadas: 10\n"
    "7. Local de Atuação: POA\n"
    "8. Missões/Osv: Patrulha\n"
)


class TestParserCanonico:
    def test_bloco_canonico_gera_missoes_list(self) -> None:
        bloco = (
            "PELOTÃO ALFA\n"
            "Cmt: TEN PM SILVA (51) 99999-9999\n"
            "Equipes: 2 (20 PMs)\n"
            "Missão 1: Policiamento Ostensivo Município: Porto Alegre (20 BPM)\n"
            "Missão 2: Apoio a Evento Município: Canoas\n"
            "Horário: 07:30 às 19:30\n"
        )
        texto = _HEADER_1BPCHQ + bloco + _RODAPE
        res = parse_texto_whatsapp(texto)
        assert res["fracoes"], "parser deve emitir ao menos 1 fracao"
        fr = res["fracoes"][0]
        missoes = fr.get("missoes") or []
        assert len(missoes) == 2
        assert missoes[0]["municipio_nome_raw"].upper().startswith("PORTO ALEGRE")
        assert missoes[0]["bpm_raws"] == ["20 BPM"]
        assert missoes[0]["em_quartel"] is False
        assert missoes[1]["municipio_nome_raw"].upper().startswith("CANOAS")
        assert missoes[1]["bpm_raws"] == []

    def test_prontidao_detecta_em_quartel(self) -> None:
        bloco = (
            "PELOTÃO BRAVO\n"
            "Cmt: TEN PM ALFA (51) 98888-8888\n"
            "Equipes: 1 (10 PMs)\n"
            "Missão 1: Prontidão na sede Município: Porto Alegre\n"
            "Horário: 07:30 às 19:30\n"
        )
        texto = _HEADER_1BPCHQ + bloco + _RODAPE
        res = parse_texto_whatsapp(texto)
        assert res["fracoes"]
        missoes = res["fracoes"][0].get("missoes") or []
        assert missoes, "deve emitir vertice"
        assert missoes[0]["em_quartel"] is True
        assert missoes[0]["bpm_raws"] == []

    def test_missao_sem_municipio_gera_vertice(self) -> None:
        """Missao K: <nome> sem 'Municipio:' na linha ainda gera vertice
        — tipico de Prontidao pura. municipio_nome_raw fica vazio e o
        operador resolve no preview."""
        bloco = (
            "PELOTÃO ALFA\n"
            "Cmt: TEN SILVA (51) 99999-9999\n"
            "Equipes: 2 (20 PMs)\n"
            "Missão 1: Prontidão\n"
            "Missão 2: Policiamento Ostensivo Município: Porto Alegre (20 BPM)\n"
            "Missão 3: Apoio a Evento Município: Canoas\n"
            "Horário: 07:30 às 19:30\n"
        )
        texto = _HEADER_1BPCHQ + bloco + _RODAPE
        res = parse_texto_whatsapp(texto)
        assert res["fracoes"]
        missoes = res["fracoes"][0].get("missoes") or []
        assert len(missoes) == 3
        assert missoes[0]["missao_nome_raw"].lower().startswith("prontid")
        assert missoes[0]["municipio_nome_raw"] == ""
        assert missoes[0]["em_quartel"] is True
        assert missoes[0]["bpm_raws"] == []
        assert missoes[1]["municipio_nome_raw"].upper().startswith("PORTO ALEGRE")
        assert missoes[1]["bpm_raws"] == ["20 BPM"]
        assert missoes[2]["municipio_nome_raw"].upper().startswith("CANOAS")


# ---------------------------------------------------------------------------
# Fase 6.4 — parse_lista_bpms (8 variantes sintaticas)
# ---------------------------------------------------------------------------


# Matriz exigida pela Fase 6.4 — cobrir as 8 variantes aceitas + casos extras.
_VARIANTES_BPM = [
    # 4 variantes com parenteses
    ("(20 BPM, 1 BPM)", ["20 BPM", "1 BPM"]),
    ("(20 BPM e 1 BPM)", ["20 BPM", "1 BPM"]),
    ("(20° e 1° BPM)", ["20 BPM", "1 BPM"]),
    ("(20/1 BPM)", ["20 BPM", "1 BPM"]),
    # 4 variantes sem parenteses
    ("20 BPM, 1 BPM", ["20 BPM", "1 BPM"]),
    ("20 BPM e 1 BPM", ["20 BPM", "1 BPM"]),
    ("20° e 1° BPM", ["20 BPM", "1 BPM"]),
    ("20 BPM; 1 BPM", ["20 BPM", "1 BPM"]),
    # Casos auxiliares (sanity)
    ("(20 BPM)", ["20 BPM"]),
    ("20 BPM", ["20 BPM"]),
    ("(11BPM)", ["11 BPM"]),
    ("(9º BPM)", ["9 BPM"]),
    # Ordem preservada, duplicatas removidas
    ("20 BPM, 1 BPM, 20 BPM", ["20 BPM", "1 BPM"]),
    # Case-insensitive no separador ' e '
    ("20 bpm E 1 bpm", ["20 BPM", "1 BPM"]),
    # Vazios
    ("", []),
    ("()", []),
    ("   ", []),
]


class TestParseListaBpms:
    @pytest.mark.parametrize("entrada,esperado", _VARIANTES_BPM)
    def test_matriz_variantes(
        self, entrada: str, esperado: list[str]
    ) -> None:
        assert parse_lista_bpms(entrada) == esperado


# ---------------------------------------------------------------------------
# Fase 6.4 — parser canonico produz bpm_raws (lista) em blocos multi-BPM
# ---------------------------------------------------------------------------


def _bloco_poa_com_bpms(trecho_bpm: str) -> str:
    """Monta um bloco canonico com uma missao POA + um trecho de BPMs."""
    return (
        "PELOTÃO ALFA\n"
        "Cmt: TEN PM SILVA (51) 99999-9999\n"
        "Equipes: 2 (20 PMs)\n"
        f"Missão 1: Policiamento Ostensivo Município: Porto Alegre {trecho_bpm}\n"
        "Horário: 07:30 às 19:30\n"
    )


_VARIANTES_CANONICAS = [
    ("(20 BPM, 1 BPM)", ["20 BPM", "1 BPM"]),
    ("(20 BPM e 1 BPM)", ["20 BPM", "1 BPM"]),
    ("(20° e 1° BPM)", ["20 BPM", "1 BPM"]),
    ("(20/1 BPM)", ["20 BPM", "1 BPM"]),
    ("20 BPM, 1 BPM", ["20 BPM", "1 BPM"]),
    ("20 BPM e 1 BPM", ["20 BPM", "1 BPM"]),
    ("20° e 1° BPM", ["20 BPM", "1 BPM"]),
    ("20 BPM; 1 BPM", ["20 BPM", "1 BPM"]),
]


class TestParserCanonicoMultiBpm:
    """Garante que o parser end-to-end (parse_texto_whatsapp) emite
    bpm_raws lista nas 8 sintaxes aceitas para POA."""

    @pytest.mark.parametrize("trecho,esperado", _VARIANTES_CANONICAS)
    def test_parser_emite_bpm_raws_lista(
        self, trecho: str, esperado: list[str]
    ) -> None:
        texto = _HEADER_1BPCHQ + _bloco_poa_com_bpms(trecho) + _RODAPE
        res = parse_texto_whatsapp(texto)
        assert res["fracoes"], "parser deve emitir ao menos 1 fracao"
        missoes = res["fracoes"][0].get("missoes") or []
        assert missoes, "bloco canonico deve produzir vertice"
        v = missoes[0]
        assert v["municipio_nome_raw"].upper().startswith("PORTO ALEGRE")
        assert v["em_quartel"] is False
        assert v["bpm_raws"] == esperado


# ---------------------------------------------------------------------------
# Fase 6.4 — invariantes de validacao N:N
# ---------------------------------------------------------------------------


class TestValidarVerticesNN64:
    """Fase 6.4: invariantes especificas de multiplos BPMs e em_quartel."""

    def _frac(self, missoes: list[dict]) -> dict:
        return {
            "unidade": "1 BPChq", "data": "01/04/2026", "turno": "Diurno",
            "fracao": "F1", "comandante": "CMT", "telefone": "",
            "equipes": 1, "pms": 5, "horario_inicio": "",
            "horario_fim": "", "missao": "", "missoes": missoes,
        }

    def test_poa_com_n_bpms_preserva_lista(self) -> None:
        """validate_fracoes preserva bpm_ids quando em_quartel=False."""
        rows = [self._frac([{
            "ordem": 1, "missao_nome_raw": "Policiamento Ostensivo",
            "municipio_nome_raw": "Porto Alegre",
            "municipio_id": "mu-1", "em_quartel": False,
            "bpm_ids": ["bpm-a", "bpm-b", "bpm-c"],
        }])]
        out = validate_fracoes(rows)
        v: MissaoVertice = out[0]["missoes"][0]
        assert v["bpm_ids"] == ["bpm-a", "bpm-b", "bpm-c"]

    def test_em_quartel_zera_lista_mesmo_com_bpms(self) -> None:
        """em_quartel=True sobrepoe bpm_ids (mesmo que vierem no payload)."""
        rows = [self._frac([{
            "ordem": 1, "missao_nome_raw": "Pernoite",
            "municipio_nome_raw": "Porto Alegre",
            "municipio_id": "mu-1", "em_quartel": True,
            "bpm_ids": ["bpm-a", "bpm-b"],
        }])]
        out = validate_fracoes(rows)
        assert out[0]["missoes"][0]["bpm_ids"] == []

    def test_bpm_ids_legacy_singular_e_coagido(self) -> None:
        """Compat 6.3: payload com bpm_id singular vira lista de 1 elemento."""
        rows = [self._frac([{
            "ordem": 1, "missao_nome_raw": "Policiamento Ostensivo",
            "municipio_nome_raw": "Porto Alegre",
            "municipio_id": "mu-1", "em_quartel": False,
            "bpm_id": "bpm-legado",
        }])]
        out = validate_fracoes(rows)
        assert out[0]["missoes"][0]["bpm_ids"] == ["bpm-legado"]

    def test_bpm_ids_deduplica(self) -> None:
        """Payload com ids duplicados gera lista sem repeticao."""
        rows = [self._frac([{
            "ordem": 1, "missao_nome_raw": "Policiamento Ostensivo",
            "municipio_nome_raw": "Porto Alegre",
            "municipio_id": "mu-1", "em_quartel": False,
            "bpm_ids": ["bpm-a", "bpm-b", "bpm-a"],
        }])]
        out = validate_fracoes(rows)
        assert out[0]["missoes"][0]["bpm_ids"] == ["bpm-a", "bpm-b"]
