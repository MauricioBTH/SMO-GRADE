"""Parser do bloco de cabecalho (informacoes gerais da unidade)."""
import re

from app.services.whatsapp_helpers import _extrair_telefone, _extrair_unidade_data
from app.services.whatsapp_patterns import (
    RE_ACE, RE_ANIMAIS, RE_COPOM, RE_EFETIVO_TOTAL, RE_EF_MOT, RE_LOCAL,
    RE_LONGAS, RE_MISSOES_OSV, RE_MOTOS, RE_OF_SUPERIOR, RE_OFICIAL,
    RE_PORTATEIS, RE_SD, RE_SGT, RE_TELEFONE, RE_TURNO, RE_VTRS,
)
from app.validators.xlsx_validator import (
    CabecalhoRow, parse_animais, safe_int, sanitize_text,
)


def parse_cabecalho(texto: str) -> tuple[CabecalhoRow, list[str]]:
    """Extrai dados do cabecalho (bloco numerico + header) do texto."""
    avisos: list[str] = []
    texto = re.sub(r"\*([^*]+)\*", r"\1", texto)
    linhas = texto.splitlines()

    unidade, data = _extrair_unidade_data(texto)
    if not unidade:
        avisos.append("Unidade nao identificada")
    if not data:
        avisos.append("Data nao identificada")

    turno = ""
    m = RE_TURNO.search(texto)
    if m:
        turno = sanitize_text(m.group(1))

    of_superior, tel_oficial = "", ""
    m = RE_OF_SUPERIOR.search(texto)
    if m:
        of_superior, tel_oficial = _extrair_telefone(m.group(1))
        of_superior = sanitize_text(of_superior)
        tel_oficial = sanitize_text(tel_oficial)

    tel_copom = ""
    m = RE_COPOM.search(texto)
    if m:
        raw_copom = m.group(1)
        m_tel = RE_TELEFONE.search(raw_copom)
        tel_copom = sanitize_text(m_tel.group(0) if m_tel else raw_copom)

    op_d, tel_d, hor_d = "", "", ""
    op_n, tel_n, hor_n = "", "", ""
    for i, ln in enumerate(linhas):
        s = ln.strip()
        if re.match(r"^SD\s+PM\s+", s, re.IGNORECASE) and not re.match(r"^SD\s+PM\s*:\s*\d+", s, re.IGNORECASE):
            nome = sanitize_text(s)
            hor = ""
            if i + 1 < len(linhas):
                hm = re.match(r"Hor[áa]rio\s*:\s*(.+)", linhas[i + 1].strip(), re.IGNORECASE)
                if hm:
                    hor = sanitize_text(hm.group(1))
            if not op_d:
                op_d, hor_d = nome, hor
            elif not op_n:
                op_n, hor_n = nome, hor

    nums: dict[str, int | str] = {}
    for ln in linhas:
        s = ln.strip()
        for pat, key in [
            (RE_EFETIVO_TOTAL, "efetivo_total"), (RE_EF_MOT, "ef_motorizado"),
            (RE_ACE, "armas_ace"), (RE_PORTATEIS, "armas_portateis"),
            (RE_LONGAS, "armas_longas"),
        ]:
            m = pat.search(s)
            if m:
                nums[key] = safe_int(m.group(1))
                break
        else:
            m = RE_OFICIAL.search(s)
            if m and not RE_OF_SUPERIOR.search(s) and "OF de SV" not in s:
                nums["oficiais"] = safe_int(m.group(1))
                continue
            m = RE_SGT.search(s)
            if m and not re.match(r"^\d+[°º]\s*SGT\s+PM\s*:", s) and "Aux" not in s:
                nums["sargentos"] = safe_int(m.group(1))
                continue
            m = RE_SD.search(s)
            if m and re.match(r"^\s*\d+\.?\d*\s*\.?\s*S[Dd]\s*:", s):
                nums["soldados"] = safe_int(m.group(1))
                continue
            m = RE_VTRS.search(s)
            if m:
                nums["vtrs"] = safe_int(m.group(1))
                m2 = RE_MOTOS.search(s)
                if m2:
                    nums["motos"] = safe_int(m2.group(1))
                continue
            m = RE_LOCAL.search(s)
            if m:
                nums["locais_atuacao"] = sanitize_text(m.group(1))
                continue
            m = RE_MISSOES_OSV.search(s)
            if m:
                nums["missoes_osv"] = sanitize_text(m.group(1))
                continue
            m = RE_ANIMAIS.search(s)
            if m:
                a, t = parse_animais(m.group(1))
                nums["animais"] = a
                nums["animais_tipo"] = t

    ef_total = nums.get("efetivo_total", 0)
    if ef_total == 0:
        avisos.append("Efetivo total nao encontrado")

    cab = CabecalhoRow(
        unidade=unidade, data=data, turno=turno,
        oficial_superior=of_superior, tel_oficial=tel_oficial,
        tel_copom=tel_copom,
        operador_diurno=op_d, tel_op_diurno=tel_d, horario_op_diurno=hor_d,
        operador_noturno=op_n, tel_op_noturno=tel_n, horario_op_noturno=hor_n,
        efetivo_total=safe_int(ef_total),
        oficiais=safe_int(nums.get("oficiais", 0)),
        sargentos=safe_int(nums.get("sargentos", 0)),
        soldados=safe_int(nums.get("soldados", 0)),
        vtrs=safe_int(nums.get("vtrs", 0)),
        motos=safe_int(nums.get("motos", 0)),
        ef_motorizado=safe_int(nums.get("ef_motorizado", 0)),
        armas_ace=safe_int(nums.get("armas_ace", 0)),
        armas_portateis=safe_int(nums.get("armas_portateis", 0)),
        armas_longas=safe_int(nums.get("armas_longas", 0)),
        animais=safe_int(nums.get("animais", 0)),
        animais_tipo=str(nums.get("animais_tipo", "")),
        locais_atuacao=str(nums.get("locais_atuacao", "")),
        missoes_osv=str(nums.get("missoes_osv", "")),
    )
    return cab, avisos
