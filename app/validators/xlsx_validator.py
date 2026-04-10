import re
from typing import TypedDict


class FracaoRow(TypedDict):
    unidade: str
    data: str
    turno: str
    fracao: str
    comandante: str
    telefone: str
    equipes: int
    pms: int
    horario_inicio: str
    horario_fim: str
    missao: str


class CabecalhoRow(TypedDict):
    unidade: str
    data: str
    turno: str
    oficial_superior: str
    tel_oficial: str
    tel_copom: str
    operador_diurno: str
    tel_op_diurno: str
    horario_op_diurno: str
    operador_noturno: str
    tel_op_noturno: str
    horario_op_noturno: str
    efetivo_total: int
    oficiais: int
    sargentos: int
    soldados: int
    vtrs: int
    motos: int
    ef_motorizado: int
    armas_ace: int
    armas_portateis: int
    armas_longas: int
    animais: int
    animais_tipo: str
    locais_atuacao: str
    missoes_osv: str


UNIDADES_VALIDAS = frozenset({
    "1 BPChq", "1º BPChq",
    "2 BPChq", "2º BPChq",
    "3 BPChq", "3º BPChq",
    "4 BPChq", "4º BPChq",
    "5 BPChq", "5º BPChq",
    "6 BPChq", "6º BPChq",
    "4 RPMon", "4º RPMon",
})

COLUNAS_FRACOES = frozenset({
    "unidade", "data", "turno", "fracao", "comandante",
    "telefone", "equipes", "pms", "horario_inicio", "horario_fim", "missao",
})

COLUNAS_CABECALHO = frozenset({
    "unidade", "data", "turno", "oficial_superior", "tel_oficial",
    "tel_copom", "operador_diurno", "tel_op_diurno", "horario_op_diurno",
    "operador_noturno", "tel_op_noturno", "horario_op_noturno",
    "efetivo_total", "oficiais", "sargentos", "soldados", "vtrs",
    "motos", "ef_motorizado", "armas_ace", "armas_portateis",
    "armas_longas", "animais", "locais_atuacao", "missoes_osv",
})

_STRIP_HTML = re.compile(r"<[^>]+>")
_MAX_TEXT_LEN = 500


def sanitize_text(value: str) -> str:
    cleaned = _STRIP_HTML.sub("", str(value))
    cleaned = cleaned.replace("\x00", "")
    return cleaned[:_MAX_TEXT_LEN].strip()


def safe_int(value: object) -> int:
    try:
        return int(float(str(value)))
    except (ValueError, TypeError):
        return 0


_DIGITOS = re.compile(r"(\d+)")


def parse_animais(value: object) -> tuple[int, str]:
    """Extrai quantidade e tipo de animal de textos como '03 caes' ou '16 cavalos'."""
    texto = sanitize_text(str(value)) if value else ""
    if not texto:
        return 0, ""
    match = _DIGITOS.search(texto)
    qtd = int(match.group(1)) if match else 0
    tipo = _DIGITOS.sub("", texto).strip()
    return qtd, tipo


def validate_fracoes(rows: list[dict]) -> list[FracaoRow]:
    if not rows:
        raise ValueError("Aba 'fracoes' vazia")

    colunas = set(rows[0].keys())
    faltando = COLUNAS_FRACOES - colunas
    if faltando:
        raise ValueError(f"Colunas faltando em fracoes: {', '.join(sorted(faltando))}")

    validated: list[FracaoRow] = []
    for idx, row in enumerate(rows):
        unidade = sanitize_text(row.get("unidade", ""))
        if not unidade:
            raise ValueError(f"Linha {idx + 2}: unidade vazia")

        validated.append(FracaoRow(
            unidade=unidade,
            data=sanitize_text(row.get("data", "")),
            turno=sanitize_text(row.get("turno", "")),
            fracao=sanitize_text(row.get("fracao", "")),
            comandante=sanitize_text(row.get("comandante", "")),
            telefone=sanitize_text(row.get("telefone", "")),
            equipes=safe_int(row.get("equipes", 0)),
            pms=safe_int(row.get("pms", 0)),
            horario_inicio=sanitize_text(row.get("horario_inicio", "")),
            horario_fim=sanitize_text(row.get("horario_fim", "")),
            missao=sanitize_text(row.get("missao", "")),
        ))

    return validated


def validate_cabecalho(rows: list[dict]) -> list[CabecalhoRow]:
    if not rows:
        return []

    colunas = set(rows[0].keys())
    faltando = COLUNAS_CABECALHO - colunas
    if faltando:
        raise ValueError(f"Colunas faltando em cabecalho: {', '.join(sorted(faltando))}")

    validated: list[CabecalhoRow] = []
    for row in rows:
        unidade = sanitize_text(row.get("unidade", ""))
        if not unidade:
            continue

        validated.append(CabecalhoRow(
            unidade=unidade,
            data=sanitize_text(row.get("data", "")),
            turno=sanitize_text(row.get("turno", "")),
            oficial_superior=sanitize_text(row.get("oficial_superior", "")),
            tel_oficial=sanitize_text(row.get("tel_oficial", "")),
            tel_copom=sanitize_text(row.get("tel_copom", "")),
            operador_diurno=sanitize_text(row.get("operador_diurno", "")),
            tel_op_diurno=sanitize_text(row.get("tel_op_diurno", "")),
            horario_op_diurno=sanitize_text(row.get("horario_op_diurno", "")),
            operador_noturno=sanitize_text(row.get("operador_noturno", "")),
            tel_op_noturno=sanitize_text(row.get("tel_op_noturno", "")),
            horario_op_noturno=sanitize_text(row.get("horario_op_noturno", "")),
            efetivo_total=safe_int(row.get("efetivo_total", 0)),
            oficiais=safe_int(row.get("oficiais", 0)),
            sargentos=safe_int(row.get("sargentos", 0)),
            soldados=safe_int(row.get("soldados", 0)),
            vtrs=safe_int(row.get("vtrs", 0)),
            motos=safe_int(row.get("motos", 0)),
            ef_motorizado=safe_int(row.get("ef_motorizado", 0)),
            armas_ace=safe_int(row.get("armas_ace", 0)),
            armas_portateis=safe_int(row.get("armas_portateis", 0)),
            armas_longas=safe_int(row.get("armas_longas", 0)),
            animais=parse_animais(row.get("animais", ""))[0],
            animais_tipo=parse_animais(row.get("animais", ""))[1],
            locais_atuacao=sanitize_text(row.get("locais_atuacao", "")),
            missoes_osv=sanitize_text(row.get("missoes_osv", "")),
        ))

    return validated
