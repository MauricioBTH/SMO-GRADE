import re
from typing import TypedDict


class _FracaoBase(TypedDict):
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


class MissaoVertice(TypedDict, total=False):
    """Vertice de smo.fracao_missoes (Fase 6.3). Um bloco canonico emite N
    desses. A lista ordenada vive em `FracaoRow.missoes`.

    Fase 6.4: BPMs passam a ser lista (um vertice em POA pode cobrir N BPMs).
    Lista vazia = sem BPM (caso geral: em_quartel=True ou municipio fora de POA).
    """
    ordem: int
    missao_nome_raw: str
    municipio_nome_raw: str
    bpm_raws: list[str]
    em_quartel: bool
    # Resolvidos pelo enriquecedor (whatsapp_catalogo):
    missao_id: str | None
    municipio_id: str | None
    bpm_ids: list[str]


class FracaoRow(_FracaoBase, total=False):
    # Campos catalogados (Fase 6.2) — opcionais; podem ser None.
    missao_id: str | None
    osv: str | None
    municipio_id: str | None
    municipio_nome_raw: str | None
    # Fase 6.3 — N vertices (canonico). Nao-canonico: lista de 1 item derivado.
    missoes: list[MissaoVertice]


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

        fr: FracaoRow = FracaoRow(
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
        )
        # Campos catalogados (Fase 6.2) — repassados sem ressanitizar ids
        # porque vem do preview ja validados no backend anterior.
        for key in ("missao_id", "osv", "municipio_id", "municipio_nome_raw"):
            if key in row and row[key] is not None:
                fr[key] = row[key] if key.endswith("_id") else sanitize_text(row[key])

        # Vertices (Fase 6.3). Se a chave existe, normaliza; caso contrario,
        # save_fracoes trata como lista vazia (compat com XLSX legado).
        if "missoes" in row and isinstance(row["missoes"], list):
            fr["missoes"] = _normalizar_vertices(row["missoes"])

        validated.append(fr)

    return validated


def _normalizar_vertices(raw: list[dict]) -> list[MissaoVertice]:
    """Sanitiza strings e coage tipos nos vertices vindos do preview JSON.
    Renumeracao final da `ordem` fica com db_service._inserir_vertices.

    Fase 6.4: aceita bpm_raws/bpm_ids (plural, canonico) e, por compat com
    payload legado de 6.3, tambem aceita bpm_raw/bpm_id singulares — ambos
    sao normalizados para lista. em_quartel=True zera bpm_ids.
    """
    out: list[MissaoVertice] = []
    for i, v in enumerate(raw):
        if not isinstance(v, dict):
            continue
        em_q: bool = bool(v.get("em_quartel", False))
        out.append(MissaoVertice(
            ordem=safe_int(v.get("ordem", i + 1)),
            missao_nome_raw=sanitize_text(v.get("missao_nome_raw", "") or ""),
            municipio_nome_raw=sanitize_text(v.get("municipio_nome_raw", "") or ""),
            bpm_raws=_coagir_bpm_raws(v),
            em_quartel=em_q,
            missao_id=v.get("missao_id") or None,
            municipio_id=v.get("municipio_id") or None,
            bpm_ids=[] if em_q else _coagir_bpm_ids(v),
        ))
    return out


def _coagir_bpm_raws(v: dict) -> list[str]:
    """Extrai e sanitiza bpm_raws do payload, tolerando a forma singular (6.3)."""
    crus = v.get("bpm_raws")
    if isinstance(crus, list):
        return [sanitize_text(str(x)) for x in crus if x]
    singular = v.get("bpm_raw")
    if singular:
        return [sanitize_text(str(singular))]
    return []


def _coagir_bpm_ids(v: dict) -> list[str]:
    """Extrai bpm_ids do payload, tolerando a forma singular (6.3).
    Ids vindos do catalogo sao UUIDs ja validados — apenas dedup preservando ordem."""
    crus = v.get("bpm_ids")
    lista: list[str] = []
    if isinstance(crus, list):
        lista = [str(x) for x in crus if x]
    else:
        singular = v.get("bpm_id")
        if singular:
            lista = [str(singular)]
    vistos: set[str] = set()
    saida: list[str] = []
    for x in lista:
        if x in vistos:
            continue
        vistos.add(x)
        saida.append(x)
    return saida


def validar_vertices_n_n(
    fracoes: list[FracaoRow], poa_crpm_sigla: str = "CPC",
    municipios_index: dict[str, str] | None = None,
) -> list[str]:
    """Regra 6.3/6.4 pre-save: cada fracao deve ter >=1 vertice com municipio_id;
    se POA e nao em_quartel, exige ao menos 1 BPM (lista nao-vazia). Levanta
    ValueError com mensagens agregadas. `municipios_index`:
    {municipio_id: crpm_sigla} (injetavel p/ teste). Retorna lista de avisos
    informativos (nao bloqueantes) — erros levantam.
    """
    erros: list[str] = []
    avisos: list[str] = []
    for fr in fracoes:
        titulo: str = fr.get("fracao") or fr.get("comandante") or "fracao"
        vertices: list[MissaoVertice] = fr.get("missoes") or []
        if not vertices:
            erros.append(f"[{titulo}] sem missoes no preview.")
            continue
        for v in vertices:
            if not v.get("municipio_id"):
                erros.append(
                    f"[{titulo}] missao '{v.get('missao_nome_raw', '?')}' "
                    f"sem municipio no catalogo."
                )
                continue
            if municipios_index is not None and not v.get("em_quartel", False):
                sigla: str = (municipios_index.get(
                    v["municipio_id"] or "", ""
                ) or "").upper()
                bpm_ids: list[str] = v.get("bpm_ids") or []
                if sigla == poa_crpm_sigla.upper() and not bpm_ids:
                    erros.append(
                        f"[{titulo}] missao '{v.get('missao_nome_raw', '?')}' "
                        f"em Porto Alegre exige BPM (ou marcar 'em quartel')."
                    )
    if erros:
        raise ValueError(" | ".join(erros))
    return avisos


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
            animais=safe_int(row.get("animais", 0)) if isinstance(row.get("animais"), (int, float)) else parse_animais(row.get("animais", ""))[0],
            animais_tipo=sanitize_text(row.get("animais_tipo", "")) or parse_animais(row.get("animais", ""))[1],
            locais_atuacao=sanitize_text(row.get("locais_atuacao", "")),
            missoes_osv=sanitize_text(row.get("missoes_osv", "")),
        ))

    return validated
