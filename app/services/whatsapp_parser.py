"""
Parser de textos WhatsApp semi-padronizados das unidades CPChq.
Extrai cabecalho (bloco numerico) e fracoes (blocos Cmt/Equipe/Missao).
"""
import re
from typing import TypedDict

from app.validators.xlsx_validator import (
    CabecalhoRow,
    FracaoRow,
    parse_animais,
    safe_int,
    sanitize_text,
)
from app.services.whatsapp_patterns import (
    RE_UNIDADE, RE_DATA, RE_TURNO, RE_OF_SUPERIOR, RE_COPOM,
    RE_EFETIVO_TOTAL, RE_OFICIAL, RE_SGT, RE_SD, RE_VTRS, RE_MOTOS,
    RE_EF_MOT, RE_ACE, RE_PORTATEIS, RE_LONGAS, RE_LOCAL, RE_MISSOES_OSV,
    RE_ANIMAIS, RE_CMT, RE_OF_SV_CMT, RE_AUX_SV_CMT, RE_TURNO_HEADER,
    RE_NOME_FRACAO, RE_MISSAO_NUM, RE_ESQ_PEL, RE_EQUIPES, RE_MISSAO,
    RE_HORARIO, RE_HORA_EMPREGO, RE_SKIP, RE_VTR_EQUIPE,
    RE_INICIO_BLOCO_NUM, RE_TELEFONE, RE_HHMM, UNIDADE_MAP,
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
                    fim_adj = fim + 1440  # dia seguinte
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
        data = m.group(1).strip()
        partes = re.split(r"[/\-]", data)
        if len(partes) == 3 and len(partes[2]) == 2:
            data = f"{partes[0]}/{partes[1]}/20{partes[2]}"
        elif len(partes) == 3:
            data = f"{partes[0]}/{partes[1]}/{partes[2]}"

    return unidade, data


# ---------------------------------------------------------------------------
# Segmentacao multi-unidade
# ---------------------------------------------------------------------------

_RE_SEGMENTO = re.compile(r"(?=(?:^|\n)\*?DADOS\s+PARA\s+PLANILHA)", re.IGNORECASE)


def _segmentar_texto(texto: str) -> list[str]:
    """Divide texto em segmentos, 1 por unidade. Se nao encontra marcador, retorna [texto]."""
    partes = _RE_SEGMENTO.split(texto)
    partes = [p.strip() for p in partes if p.strip()]
    return partes if partes else [texto]


# ---------------------------------------------------------------------------
# parse_cabecalho
# ---------------------------------------------------------------------------

def parse_cabecalho(texto: str) -> tuple[CabecalhoRow, list[str]]:
    """Extrai dados do cabecalho (bloco numerico + header) do texto."""
    avisos: list[str] = []
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

    # Operadores (linhas SD PM seguidas de Horario)
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

    # Bloco numerico
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


# ---------------------------------------------------------------------------
# parse_fracoes
# ---------------------------------------------------------------------------

def _e_linha_cabecalho_numerico(linha: str) -> bool:
    s = linha.strip()
    if RE_INICIO_BLOCO_NUM.match(s):
        return True
    if re.match(r"^\s*\d+\.?\d*\s*\.?\s*(Oficial|Sgt|S[Dd]|VTR|Efetivo\s+Motor|Armas|Local|Miss[õo]es|Animais)", s, re.IGNORECASE):
        return True
    if RE_TURNO.match(s):
        return True
    return False


def parse_fracoes(texto: str) -> list[FracaoRow]:
    """Extrai lista de fracoes do texto WhatsApp."""
    linhas = texto.splitlines()
    unidade, data = _extrair_unidade_data(texto)

    blocos: list[dict] = []
    bloco_atual: dict | None = None
    turno_header = ""
    nome_secao = ""
    em_bloco_numerico = False
    em_bloco_vtr = False

    def _novo(fracao: str = "", cmt: str = "", tel: str = "",
              missao: str = "") -> dict:
        return {
            "fracao": fracao, "comandante": cmt, "telefone": tel,
            "equipes": 0, "pms": 0, "horario_inicio": "", "horario_fim": "",
            "missao": missao, "turno": turno_header,
        }

    i = 0
    while i < len(linhas):
        ln_s = linhas[i].strip()
        i += 1

        if not ln_s:
            em_bloco_vtr = False
            continue

        # Missao numerada (6BPChq com "1. MISSÃO:")
        m = RE_MISSAO_NUM.match(ln_s)
        if m:
            if bloco_atual:
                blocos.append(bloco_atual)
            em_bloco_numerico = False
            bloco_atual = _novo(missao=sanitize_text(m.group(1)))
            continue

        # Missao standalone como inicio de fracao (6BPChq sem numero)
        m_ms = re.match(r"^\s*MISS[ÃA]O\s*:\s*(.+)", ln_s, re.IGNORECASE)
        if m_ms:
            # Nova fracao se nao ha bloco ou bloco ja tem cmt+missao
            if bloco_atual is None or (
                    bloco_atual.get("comandante") and bloco_atual.get("missao")):
                if bloco_atual:
                    blocos.append(bloco_atual)
                em_bloco_numerico = False
                bloco_atual = _novo(missao=sanitize_text(m_ms.group(1)))
                continue

        # Header de nova unidade (*...*) reseta contexto de bloco numerico
        if ln_s.startswith("*") and ln_s.endswith("*"):
            em_bloco_numerico = False
            continue

        # Header de nova unidade SEM asteriscos — reseta bloco numerico
        if re.match(r"^DADOS\s+PARA\s+PLANILHA", ln_s, re.IGNORECASE):
            em_bloco_numerico = False
            if bloco_atual:
                blocos.append(bloco_atual)
                bloco_atual = None
            nome_secao = ""
            continue

        if _e_linha_cabecalho_numerico(ln_s):
            em_bloco_numerico = True
            if bloco_atual:
                blocos.append(bloco_atual)
                bloco_atual = None
            continue

        if em_bloco_numerico:
            continue

        if RE_VTR_EQUIPE.match(ln_s):
            em_bloco_vtr = True
            continue

        if em_bloco_vtr:
            continue

        if RE_SKIP.match(ln_s):
            continue

        if ln_s.startswith("*") and ln_s.endswith("*"):
            continue

        if re.match(r"^OF\s+SA\s+", ln_s, re.IGNORECASE):
            continue
        if re.match(r"^OF\s+de\s+SV\s*:", ln_s, re.IGNORECASE):
            continue
        if re.match(r"^Data\s*:", ln_s, re.IGNORECASE):
            continue
        if re.match(r"^COPOM\s*:", ln_s, re.IGNORECASE):
            continue
        if re.match(r"^Efetivo\s+de\s+\d", ln_s, re.IGNORECASE):
            continue
        if re.match(r"^\*\s*(DATA|OF\s+de\s+SV)\s*:", ln_s, re.IGNORECASE):
            continue
        if re.match(r"^\*\s*Tel\s*:", ln_s, re.IGNORECASE) and bloco_atual is None:
            continue

        # Turno header
        m = RE_TURNO_HEADER.match(ln_s)
        if m:
            if bloco_atual:
                blocos.append(bloco_atual)
                bloco_atual = None
            turno_header = ln_s.strip()
            # Turnos compostos com local (ex: "2°/3° T - SANTA MARIA") viram nome de secao
            if re.search(r"\bT\b\s*[-–]\s*\w", ln_s):
                nome_secao = sanitize_text(ln_s)
            else:
                nome_secao = ""
            continue

        # Esq/Pel header (4RPMon)
        if RE_ESQ_PEL.match(ln_s):
            if bloco_atual:
                blocos.append(bloco_atual)
            nome_secao = sanitize_text(ln_s)
            bloco_atual = None
            continue

        # Nome de fracao com ordinal (ex: "3ª CIA") — exclui nomes de unidade
        if (re.match(r"^\d+[ªº°]\s+[A-ZÀ-ÚÇ]", ln_s) and len(ln_s) > 3
                and not RE_SKIP.match(ln_s)
                and not re.search(r"BATAL|RPMon|BPChq", ln_s, re.IGNORECASE)):
            if bloco_atual:
                blocos.append(bloco_atual)
            nome_secao = sanitize_text(ln_s)
            bloco_atual = None
            continue

        # Nome de fracao em CAPS
        if (RE_NOME_FRACAO.match(ln_s) and len(ln_s) > 3
                and not re.match(r"^(SD|SGT|TEN|CAP|MAJ|CEL)\s+PM", ln_s, re.IGNORECASE)
                and not RE_SKIP.match(ln_s)):
            if bloco_atual:
                blocos.append(bloco_atual)
            nome_secao = sanitize_text(ln_s)
            bloco_atual = None
            continue

        # Cmt:
        m = RE_CMT.match(ln_s)
        if m:
            raw_cmt = re.sub(r"^Cmt\s*:\s*", "", m.group(1).strip(), flags=re.IGNORECASE)
            nome, tel = _extrair_telefone(raw_cmt)
            if bloco_atual and not bloco_atual["comandante"]:
                bloco_atual["comandante"] = sanitize_text(nome)
                bloco_atual["telefone"] = sanitize_text(tel)
                if nome_secao and not bloco_atual["fracao"]:
                    bloco_atual["fracao"] = nome_secao
                    nome_secao = ""
            else:
                if bloco_atual:
                    blocos.append(bloco_atual)
                bloco_atual = _novo(fracao=nome_secao or "",
                                    cmt=sanitize_text(nome),
                                    tel=sanitize_text(tel))
                nome_secao = ""
            continue

        # Of. de SV
        m = RE_OF_SV_CMT.match(ln_s)
        if m:
            raw = m.group(1).strip()
            if raw:
                nome, tel = _extrair_telefone(raw)
                if bloco_atual and not bloco_atual["comandante"]:
                    bloco_atual["comandante"] = sanitize_text(nome)
                    bloco_atual["telefone"] = sanitize_text(tel)
                else:
                    if bloco_atual:
                        blocos.append(bloco_atual)
                    bloco_atual = _novo(fracao=nome_secao or turno_header or "",
                                        cmt=sanitize_text(nome),
                                        tel=sanitize_text(tel))
                    nome_secao = ""
            continue

        # Aux. de SV
        m = RE_AUX_SV_CMT.match(ln_s)
        if m:
            raw = m.group(1).strip()
            if raw:
                nome, tel = _extrair_telefone(raw)
                if bloco_atual and not bloco_atual["comandante"]:
                    bloco_atual["comandante"] = sanitize_text(nome)
                    bloco_atual["telefone"] = sanitize_text(tel)
                elif not bloco_atual:
                    bloco_atual = _novo(fracao=nome_secao or turno_header or "",
                                        cmt=sanitize_text(nome),
                                        tel=sanitize_text(tel))
                    nome_secao = ""
            continue

        # Graduacao sozinha (ex: "Sd PM Jaime") — so apos turno/secao
        if (not bloco_atual and (turno_header or nome_secao)
                and re.match(r"^(Sd|SD|Sgt|SGT|1[°º]?\s*Sgt|2[°º]?\s*Sgt|"
                             r"Ten|TEN|Cap|CAP)\.?\s+PME?\s+\w", ln_s, re.IGNORECASE)):
            nome, tel = _extrair_telefone(ln_s)
            bloco_atual = _novo(fracao=nome_secao or turno_header or "",
                                cmt=sanitize_text(nome), tel=sanitize_text(tel))
            nome_secao = ""
            continue

        # Campos dentro do bloco atual
        if bloco_atual is None:
            continue

        tm = re.match(r"^\s*\*?\s*Tel\s*:\s*(.+)", ln_s, re.IGNORECASE)
        if tm and not bloco_atual["telefone"]:
            bloco_atual["telefone"] = sanitize_text(tm.group(1))
            continue

        m = RE_EQUIPES.search(ln_s)
        if m:
            if m.group(3):  # "Equipes: 50 PM's" (sem parenteses)
                bloco_atual["equipes"] = 0
                bloco_atual["pms"] = safe_int(m.group(3))
            else:  # "Equipes: 06 (22 PM's)" (com parenteses)
                bloco_atual["equipes"] = safe_int(m.group(1)) if m.group(1) else 0
                bloco_atual["pms"] = safe_int(m.group(2))
            continue

        m = RE_MISSAO.search(ln_s)
        if m:
            bloco_atual["missao"] = sanitize_text(m.group(1))
            continue

        m = RE_HORARIO.match(ln_s) or RE_HORA_EMPREGO.match(ln_s)
        if m:
            bloco_atual["horario_inicio"], bloco_atual["horario_fim"] = \
                _parse_horario(m.group(1))
            continue

        hm = re.match(r"^\s*\*\s*Hor[áa]rio\s*:\s*(.+)", ln_s, re.IGNORECASE)
        if hm:
            bloco_atual["horario_inicio"], bloco_atual["horario_fim"] = \
                _parse_horario(hm.group(1))
            continue

    if bloco_atual:
        blocos.append(bloco_atual)

    return [
        FracaoRow(
            unidade=unidade, data=data,
            turno=sanitize_text(b.get("turno", "")),
            fracao=sanitize_text(b.get("fracao", "")),
            comandante=sanitize_text(b.get("comandante", "")),
            telefone=sanitize_text(b.get("telefone", "")),
            equipes=safe_int(b.get("equipes", 0)),
            pms=safe_int(b.get("pms", 0)),
            horario_inicio=b.get("horario_inicio", ""),
            horario_fim=b.get("horario_fim", ""),
            missao=sanitize_text(b.get("missao", "")),
        )
        for b in blocos
    ]


# ---------------------------------------------------------------------------
# Funcao principal
# ---------------------------------------------------------------------------

class ParseResult(TypedDict):
    cabecalhos: list[CabecalhoRow]
    fracoes: list[FracaoRow]
    avisos: list[str]


def parse_texto_whatsapp(texto: str) -> ParseResult:
    """Ponto de entrada principal: parseia texto WhatsApp completo."""
    texto = sanitize_text(texto) if len(texto) <= 500 else texto.replace("\x00", "")

    segmentos = _segmentar_texto(texto)
    cabecalhos: list[CabecalhoRow] = []
    todas_fracoes: list[FracaoRow] = []
    avisos: list[str] = []

    for seg in segmentos:
        cab, av = parse_cabecalho(seg)
        fracoes = parse_fracoes(seg)
        cabecalhos.append(cab)
        todas_fracoes.extend(fracoes)
        avisos.extend(av)

    if not todas_fracoes:
        avisos.append("Nenhuma fracao identificada")

    calcular_horario_emprego(cabecalhos, todas_fracoes)

    return ParseResult(cabecalhos=cabecalhos, fracoes=todas_fracoes, avisos=avisos)
