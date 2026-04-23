"""Parser dos blocos de fracao (Cmt/Equipe/Missao/OSv/Municipio).

Fase 6.3: alem do modelo 1:1 legado, emite `FracaoRow.missoes` com N
vertices quando a grammar canonica (`Missao K: ... Municipio: ... (X BPM)`)
e detectada. Formatos antigos continuam passando e geram 1 vertice derivado
dos campos legados — invariante garantida por `_materializar_missoes`.
"""
import re

from app.services.bpm_service import parse_lista_bpms
from app.services.whatsapp_helpers import (
    _extrair_telefone, _extrair_unidade_data, _parse_horario,
)
from app.services.whatsapp_patterns import (
    RE_AUX_SV_CMT, RE_CMT, RE_EM_QUARTEL, RE_EQUIPES,
    RE_ESQ_PEL, RE_HORA_EMPREGO, RE_HORARIO,
    RE_INICIO_BLOCO_NUM, RE_MISSAO, RE_MISSAO_MUNICIPIO, RE_MISSAO_NUM,
    RE_MISSAO_ORDEM_SIMPLES, RE_MUNICIPIO, RE_NOME_FRACAO, RE_OF_SV_CMT,
    RE_OSV, RE_SKIP, RE_TURNO, RE_TURNO_HEADER, RE_VTR_EQUIPE,
)
from app.validators.xlsx_validator import (
    FracaoRow, MissaoVertice, safe_int, sanitize_text,
)


def _inferir_em_quartel(missao_nome: str) -> bool:
    """Heuristica §5.4: Prontidao/Pernoite/Aquartelado -> em_quartel=True.

    Serve apenas como pre-selecao; operador confirma/override no preview.
    """
    return bool(missao_nome) and bool(RE_EM_QUARTEL.match(missao_nome.strip()))


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
            "osv": "", "municipio_nome_raw": "",
            "missoes_canonico": [],
        }

    i = 0
    while i < len(linhas):
        ln_s = linhas[i].strip()
        i += 1

        if not ln_s:
            em_bloco_vtr = False
            continue

        ln_s = re.sub(r"\*([^*]+)\*", r"\1", ln_s).strip()

        m = RE_MISSAO_NUM.match(ln_s)
        if m:
            if bloco_atual:
                blocos.append(bloco_atual)
            em_bloco_numerico = False
            bloco_atual = _novo(missao=sanitize_text(m.group(1)))
            continue

        m_ms = re.match(r"^\s*MISS[ÃA]O\s*:\s*(.+)", ln_s, re.IGNORECASE)
        if m_ms:
            if bloco_atual is None or (
                    bloco_atual.get("comandante") and bloco_atual.get("missao")):
                if bloco_atual:
                    blocos.append(bloco_atual)
                em_bloco_numerico = False
                bloco_atual = _novo(missao=sanitize_text(m_ms.group(1)))
                continue

        if ln_s.startswith("*") and ln_s.endswith("*"):
            em_bloco_numerico = False
            continue

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

        m = RE_TURNO_HEADER.match(ln_s)
        if m:
            if bloco_atual:
                blocos.append(bloco_atual)
                bloco_atual = None
            turno_header = ln_s.strip()
            if re.search(r"\bT\b\s*[-–]\s*\w", ln_s):
                nome_secao = sanitize_text(ln_s)
            else:
                nome_secao = ""
            continue

        if RE_ESQ_PEL.match(ln_s):
            if bloco_atual:
                blocos.append(bloco_atual)
            nome_secao = sanitize_text(ln_s)
            bloco_atual = None
            continue

        if (re.match(r"^\d+[ªº°]\s+[A-ZÀ-ÚÇ]", ln_s) and len(ln_s) > 3
                and not RE_SKIP.match(ln_s)
                and not re.search(r"BATAL|RPMon|BPChq", ln_s, re.IGNORECASE)):
            if bloco_atual:
                blocos.append(bloco_atual)
            nome_secao = sanitize_text(ln_s)
            bloco_atual = None
            continue

        if (RE_NOME_FRACAO.match(ln_s) and len(ln_s) > 3
                and not re.match(r"^(SD|SGT|TEN|CAP|MAJ|CEL)\s+PM", ln_s, re.IGNORECASE)
                and not RE_SKIP.match(ln_s)):
            if bloco_atual:
                blocos.append(bloco_atual)
            nome_secao = sanitize_text(ln_s)
            bloco_atual = None
            continue

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

        if (not bloco_atual and (turno_header or nome_secao)
                and re.match(r"^(Sd|SD|Sgt|SGT|1[°º]?\s*Sgt|2[°º]?\s*Sgt|"
                             r"Ten|TEN|Cap|CAP)\.?\s+PME?\s+\w", ln_s, re.IGNORECASE)):
            nome, tel = _extrair_telefone(ln_s)
            bloco_atual = _novo(fracao=nome_secao or turno_header or "",
                                cmt=sanitize_text(nome), tel=sanitize_text(tel))
            nome_secao = ""
            continue

        if bloco_atual is None:
            continue

        tm = re.match(r"^\s*\*?\s*Tel\s*:\s*(.+)", ln_s, re.IGNORECASE)
        if tm and not bloco_atual["telefone"]:
            bloco_atual["telefone"] = sanitize_text(tm.group(1))
            continue

        m = RE_EQUIPES.search(ln_s)
        if m:
            if m.group(3):
                bloco_atual["equipes"] = 0
                bloco_atual["pms"] = safe_int(m.group(3))
            else:
                bloco_atual["equipes"] = safe_int(m.group(1)) if m.group(1) else 0
                bloco_atual["pms"] = safe_int(m.group(2))
            continue

        # Grammar canonica 6.3: 'Missao K: <nome> Municipio: <nome> (X BPM)?'
        # Detecta ANTES de RE_MISSAO (que so capturaria ate o fim da linha e
        # incluiria 'Municipio: ...' no campo missao, corrompendo ambos).
        # Fase 6.4: o trecho de BPM pode conter 1..N batalhoes; a extracao
        # da lista canonica fica com bpm_service.parse_lista_bpms.
        m_cm = RE_MISSAO_MUNICIPIO.match(ln_s)
        if m_cm:
            missao_nome_raw: str = sanitize_text(m_cm.group("missao"))
            muni_nome_raw: str = sanitize_text(m_cm.group("municipio"))
            em_q: bool = _inferir_em_quartel(missao_nome_raw)
            # Descartamos BPMs quando em_quartel=True (regra §5.4).
            bpm_raws: list[str] = (
                [] if em_q else parse_lista_bpms(m_cm.group("bpm") or "")
            )
            bloco_atual["missoes_canonico"].append({
                "ordem": int(m_cm.group("ordem")),
                "missao_nome_raw": missao_nome_raw,
                "municipio_nome_raw": muni_nome_raw,
                "bpm_raws": bpm_raws,
                "em_quartel": em_q,
            })
            # Legacy fields espelham a PRIMEIRA missao — backcompat com 6.2.
            if not bloco_atual.get("missao"):
                bloco_atual["missao"] = missao_nome_raw
            if not bloco_atual.get("municipio_nome_raw"):
                bloco_atual["municipio_nome_raw"] = muni_nome_raw
            continue

        # Fallback: 'Missao K: <nome>' sem municipio explicito (ex: Prontidao).
        # Gera vertice sem municipio; operador resolve no preview.
        m_cs = RE_MISSAO_ORDEM_SIMPLES.match(ln_s)
        if m_cs:
            missao_nome_simples: str = sanitize_text(m_cs.group("missao"))
            em_q_s: bool = _inferir_em_quartel(missao_nome_simples)
            bloco_atual["missoes_canonico"].append({
                "ordem": int(m_cs.group("ordem")),
                "missao_nome_raw": missao_nome_simples,
                "municipio_nome_raw": "",
                "bpm_raws": [],
                "em_quartel": em_q_s,
            })
            if not bloco_atual.get("missao"):
                bloco_atual["missao"] = missao_nome_simples
            continue

        m = RE_MISSAO.search(ln_s)
        if m:
            bloco_atual["missao"] = sanitize_text(m.group(1))
            continue

        m = RE_OSV.search(ln_s)
        if m:
            bloco_atual["osv"] = sanitize_text(m.group(1))
            continue

        m = RE_MUNICIPIO.search(ln_s)
        if m:
            bloco_atual["municipio_nome_raw"] = sanitize_text(m.group(1))
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

    linhas_fracoes: list[FracaoRow] = []
    for b in blocos:
        fr: FracaoRow = {
            "unidade": unidade,
            "data": data,
            "turno": sanitize_text(b.get("turno", "")),
            "fracao": sanitize_text(b.get("fracao", "")),
            "comandante": sanitize_text(b.get("comandante", "")),
            "telefone": sanitize_text(b.get("telefone", "")),
            "equipes": safe_int(b.get("equipes", 0)),
            "pms": safe_int(b.get("pms", 0)),
            "horario_inicio": b.get("horario_inicio", ""),
            "horario_fim": b.get("horario_fim", ""),
            "missao": sanitize_text(b.get("missao", "")),
        }
        osv: str = sanitize_text(b.get("osv", ""))
        if osv:
            fr["osv"] = osv
        mun: str = sanitize_text(b.get("municipio_nome_raw", ""))
        if mun:
            fr["municipio_nome_raw"] = mun
        fr["missoes"] = _materializar_missoes(b)
        linhas_fracoes.append(fr)
    return linhas_fracoes


def _materializar_missoes(bloco: dict) -> list[MissaoVertice]:
    """Produz a lista ordenada §6.3 para um bloco parseado.

    - Se grammar canonica foi detectada (>=1 linha Missao K: ...): re-numera
      1..N para manter invariante mesmo que o texto pule ordens (ex: 1,3,5).
    - Senao: gera 1 vertice derivado dos campos legados `missao` +
      `municipio_nome_raw`. `em_quartel` inferido pela mesma heuristica.
    - Bloco sem nenhuma missao (nem canonica nem legada): lista vazia — o
      enriquecedor vai acusar no preview como fracao invalida.
    """
    canonico: list[dict] = list(bloco.get("missoes_canonico") or [])
    if canonico:
        canonico.sort(key=lambda m: int(m.get("ordem") or 0))
        saida: list[MissaoVertice] = []
        for idx, m in enumerate(canonico, start=1):
            raws: list[str] = list(m.get("bpm_raws") or [])
            saida.append(MissaoVertice(
                ordem=idx,
                missao_nome_raw=sanitize_text(m.get("missao_nome_raw", "")),
                municipio_nome_raw=sanitize_text(m.get("municipio_nome_raw", "")),
                bpm_raws=raws,
                em_quartel=bool(m.get("em_quartel", False)),
            ))
        return saida

    missao_legado: str = sanitize_text(bloco.get("missao", ""))
    muni_legado: str = sanitize_text(bloco.get("municipio_nome_raw", ""))
    if not missao_legado and not muni_legado:
        return []
    return [MissaoVertice(
        ordem=1,
        missao_nome_raw=missao_legado,
        municipio_nome_raw=muni_legado,
        bpm_raws=[],
        em_quartel=_inferir_em_quartel(missao_legado),
    )]
