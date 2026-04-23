"""
Entrypoint do parser WhatsApp. Modulos especializados:
  * whatsapp_helpers   - utilitarios e segmentacao
  * whatsapp_cabecalho - parse_cabecalho
  * whatsapp_fracoes   - parse_fracoes
  * whatsapp_catalogo  - enriquecimento via smo.missoes/smo.municipios
"""
from collections import Counter
from typing import TypedDict

from app.services.whatsapp_cabecalho import parse_cabecalho
from app.services.whatsapp_catalogo import enriquecer_com_catalogo
from app.services.whatsapp_fracoes import parse_fracoes
from app.services.whatsapp_helpers import (
    calcular_horario_emprego, segmentar_texto,
)
from app.validators.xlsx_validator import (
    CabecalhoRow, FracaoRow, sanitize_text,
)

__all__ = [
    "ParseResult",
    "parse_cabecalho",
    "parse_fracoes",
    "parse_texto_whatsapp",
    "calcular_horario_emprego",
]


class ParseResult(TypedDict):
    cabecalhos: list[CabecalhoRow]
    fracoes: list[FracaoRow]
    avisos: list[str]


def _corrigir_ano_inconsistente(
    cabecalhos: list[CabecalhoRow],
    fracoes: list[FracaoRow],
    avisos: list[str],
) -> None:
    """Detecta o ano mais frequente e corrige datas com ano diferente."""
    anos: list[str] = []
    for c in cabecalhos:
        d = c.get("data", "")
        partes = d.split("/")
        if len(partes) == 3 and len(partes[2]) == 4:
            anos.append(partes[2])

    if not anos:
        return

    contagem = Counter(anos)
    ano_dominante = contagem.most_common(1)[0][0]
    if contagem[ano_dominante] == len(anos):
        return

    def _fix_data(d: str) -> str:
        partes = d.split("/")
        if len(partes) == 3 and len(partes[2]) == 4 and partes[2] != ano_dominante:
            return f"{partes[0]}/{partes[1]}/{ano_dominante}"
        return d

    for c in cabecalhos:
        old = c.get("data", "")
        new = _fix_data(old)
        if old != new:
            avisos.append(
                f"Ano corrigido: {old} -> {new} (unidade={c.get('unidade','')})"
            )
            c["data"] = new

    for f in fracoes:
        old = f.get("data", "")
        new = _fix_data(old)
        if old != new:
            f["data"] = new


def parse_texto_whatsapp(texto: str) -> ParseResult:
    """Ponto de entrada principal: parseia texto WhatsApp completo."""
    texto = sanitize_text(texto) if len(texto) <= 500 else texto.replace("\x00", "")

    segmentos = segmentar_texto(texto)
    cabecalhos: list[CabecalhoRow] = []
    todas_fracoes: list[FracaoRow] = []
    avisos: list[str] = []

    ultima_data = ""
    for seg in segmentos:
        cab, av = parse_cabecalho(seg)
        fracoes = parse_fracoes(seg)

        if cab.get("data"):
            ultima_data = cab["data"]
        elif ultima_data:
            cab["data"] = ultima_data
            for fr in fracoes:
                fr["data"] = ultima_data
            avisos.append(
                f"Data inferida {ultima_data} para {cab.get('unidade', '?')}"
            )

        cabecalhos.append(cab)
        todas_fracoes.extend(fracoes)
        avisos.extend(av)

    if not todas_fracoes:
        avisos.append("Nenhuma fracao identificada")

    _corrigir_ano_inconsistente(cabecalhos, todas_fracoes, avisos)
    calcular_horario_emprego(cabecalhos, todas_fracoes)
    enriquecer_com_catalogo(todas_fracoes, avisos)

    return ParseResult(cabecalhos=cabecalhos, fracoes=todas_fracoes, avisos=avisos)
