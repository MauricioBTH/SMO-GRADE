"""Helpers compartilhados pelos modulos do parser WhatsApp."""
import re

from app.services.whatsapp_patterns import (
    RE_DATA, RE_DATA_EXTENSO, RE_DATA_SOLTA, RE_HHMM, RE_TELEFONE,
    RE_UNIDADE, UNIDADE_MAP, _MESES_EXTENSO,
)


def _normalizar_unidade(raw: str) -> str:
    key = re.sub(r"\s+", " ", raw.strip()).upper()
    for k, v in UNIDADE_MAP.items():
        if k in key:
            return v
    return raw.strip()


def _parse_horario(texto: str) -> tuple[str, str]:
    """Extrai horario_inicio e horario_fim de texto livre."""
    texto = texto.strip().rstrip(".")
    low = texto.lower()

    if low in ("24hs", "24h", "24 hs", "24 horas"):
        return "00:00", "23:59"
    if low.startswith("retorno"):
        return "Retorno", ""
    if "qtl" in low or "prel" in low or "desl" in low:
        matches = RE_HHMM.findall(texto)
        if len(matches) >= 2:
            h1 = f"{int(matches[0][0]):02d}:{int(matches[0][1] or '0'):02d}"
            h2 = f"{int(matches[-1][0]):02d}:{int(matches[-1][1] or '0'):02d}"
            return h1, h2
        if matches:
            h1 = f"{int(matches[0][0]):02d}:{int(matches[0][1] or '0'):02d}"
            return h1, ""
        return texto, ""

    matches = RE_HHMM.findall(texto)
    if len(matches) >= 2:
        h1 = f"{int(matches[0][0]):02d}:{int(matches[0][1] or '0'):02d}"
        h2 = f"{int(matches[1][0]):02d}:{int(matches[1][1] or '0'):02d}"
        return h1, h2
    if matches:
        h1 = f"{int(matches[0][0]):02d}:{int(matches[0][1] or '0'):02d}"
        return h1, ""
    return texto, ""


def _horario_para_minutos(h: str) -> int | None:
    """Converte string HH:MM para minutos desde meia-noite. None se nao parseavel."""
    if not h or not any(c.isdigit() for c in h):
        return None
    m = RE_HHMM.search(h)
    if not m:
        return None
    return int(m.group(1)) * 60 + int(m.group(2) or "0")


def calcular_horario_emprego(
    cabecalhos: list[dict], fracoes: list[dict]
) -> None:
    """Enriquece cada cabecalho com 'horario_emprego' derivado das fracoes da unidade."""
    for cab in cabecalhos:
        unidade = cab.get("unidade", "")
        fracs = [f for f in fracoes if f.get("unidade") == unidade]

        min_inicio: int | None = None
        max_fim_adj: int | None = None

        for f in fracs:
            ini = _horario_para_minutos(f.get("horario_inicio", ""))
            fim = _horario_para_minutos(f.get("horario_fim", ""))

            if ini is not None:
                if min_inicio is None or ini < min_inicio:
                    min_inicio = ini

            if fim is not None:
                fim_adj = fim
                if ini is not None and fim <= ini:
                    fim_adj = fim + 1440
                if max_fim_adj is None or fim_adj > max_fim_adj:
                    max_fim_adj = fim_adj

        if min_inicio is None:
            cab["horario_emprego"] = ""
            continue

        h1 = f"{min_inicio // 60:02d}:{min_inicio % 60:02d}"
        if max_fim_adj is None:
            cab["horario_emprego"] = h1
            continue

        fim_real = max_fim_adj % 1440
        h2 = f"{fim_real // 60:02d}:{fim_real % 60:02d}"
        cab["horario_emprego"] = f"{h1} às {h2}"


def _extrair_telefone(texto: str) -> tuple[str, str]:
    """Retorna (nome_limpo, telefone)."""
    m = RE_TELEFONE.search(texto)
    if m:
        tel = m.group(0).strip()
        nome = texto[:m.start()].strip().rstrip("-").strip()
        return nome, tel
    return texto.strip(), ""


def _extrair_unidade_data(texto: str) -> tuple[str, str]:
    """Extrai unidade normalizada e data do texto."""
    unidade = ""
    m = RE_UNIDADE.search(texto)
    if m:
        unidade = _normalizar_unidade(m.group(1))

    data = ""
    m = RE_DATA.search(texto)
    if m:
        dia, mes, ano = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        if len(ano) == 2:
            ano = f"20{ano}"
        data = f"{dia}/{mes}/{ano}"
    else:
        m = RE_DATA_EXTENSO.search(texto)
        if m:
            dia = m.group(1).zfill(2)
            mes = _MESES_EXTENSO.get(m.group(2).lower(), "")
            ano = m.group(3)
            if mes:
                data = f"{dia}/{mes}/{ano}"
        else:
            m = RE_DATA_SOLTA.search(texto)
            if m:
                data = m.group(1).strip()
                partes = re.split(r"[/\-]", data)
                if len(partes) == 3 and len(partes[2]) == 2:
                    data = f"{partes[0]}/{partes[1]}/20{partes[2]}"
                elif len(partes) == 3:
                    data = f"{partes[0]}/{partes[1]}/{partes[2]}"

    return unidade, data


_RE_SEGMENTO = re.compile(r"(?=(?:^|\n)\*?DADOS\s+PARA\s+PLANILHA)", re.IGNORECASE)


def segmentar_texto(texto: str) -> list[str]:
    """Divide texto em segmentos, 1 por unidade. Se nao encontra marcador, retorna [texto]."""
    partes = _RE_SEGMENTO.split(texto)
    partes = [p.strip() for p in partes if p.strip()]
    return partes if partes else [texto]
