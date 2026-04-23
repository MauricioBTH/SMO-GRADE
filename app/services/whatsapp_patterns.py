"""
Regex patterns e constantes para o parser de texto WhatsApp.
Separado para manter whatsapp_parser.py < 500 LOC.
"""
import re

# ---------------------------------------------------------------------------
# Cabecalho — campos do bloco numerico
# ---------------------------------------------------------------------------

RE_UNIDADE = re.compile(
    r"\*?\s*(\d+[°º]?\s*(?:BATAL[HÃA]+O\s+DE\s+POL[IÍ][CÇ]IA\s+DE\s+CHOQUE"
    r"|BPChq|RPMon|BATALHAO\s+DE\s+POLICIA\s+DE\s+CHOQUE"
    r"|REGIMENTO\s+DE\s+POL[IÍ][CÇ]?[IA]*\s+MONTADA"
    r"|Choque))\s*\*?",
    re.IGNORECASE,
)

RE_DATA = re.compile(
    r"(?:Previs[ãa]o\s+(?:do\s+dia|de\s+efetivo)|Data)\s*[\s:\-]+(\d{1,2})[°º]?\s*[/\-](\d{1,2})[/\-](\d{2,4})",
    re.IGNORECASE,
)

_MESES_EXTENSO = {
    "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03",
    "abril": "04", "maio": "05", "junho": "06", "julho": "07",
    "agosto": "08", "setembro": "09", "outubro": "10",
    "novembro": "11", "dezembro": "12",
}

RE_DATA_EXTENSO = re.compile(
    r"(?:Previs[ãa]o\s+(?:do\s+dia|de\s+efetivo)|Data)\s*[\s:\-]+(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})",
    re.IGNORECASE,
)

# Data solta numa linha (dd/mm/yyyy sem prefixo)
RE_DATA_SOLTA = re.compile(
    r"(?:^|\n)\s*(\d{1,2}/\d{1,2}/\d{2,4})\s*$",
    re.MULTILINE,
)

RE_TURNO = re.compile(r"Turno\s*:\s*(.+)", re.IGNORECASE)

RE_OF_SUPERIOR = re.compile(
    r"Oficial\s+(?:Superior|Supervisor)\s+CPChq\s+(.+)", re.IGNORECASE
)

RE_COPOM = re.compile(r"COPOM\s*:\s*(.+)", re.IGNORECASE)

RE_EFETIVO_TOTAL = re.compile(r"Efetivo\s+Total\s*:\s*(\d+)", re.IGNORECASE)
RE_OFICIAL = re.compile(r"Oficial\s*(?:is)?\s*:\s*(\d+)", re.IGNORECASE)
RE_SGT = re.compile(r"Sgt\s*:\s*(\d+)", re.IGNORECASE)
RE_SD = re.compile(r"S[Dd]\s*:\s*(\d+)", re.IGNORECASE)
RE_VTRS = re.compile(r"VTRs?\s*:\s*(\d+)", re.IGNORECASE)
RE_MOTOS = re.compile(r"(\d+)\s*(?:motocicletas?|motos?)", re.IGNORECASE)
RE_EF_MOT = re.compile(r"Efetivo\s+Motorizado\s*:\s*(\d+)", re.IGNORECASE)
RE_ACE = re.compile(
    r"Armas\s+de\s+Condu[çc][ãa]o\s+El[ée]trica\s+Empregadas?\s*:\s*(\d+)",
    re.IGNORECASE,
)
RE_PORTATEIS = re.compile(
    r"Armas\s+(?:Port[áa]teis|de\s+Porte)\s*,?\s*Empregadas?\s*:\s*(\d+)",
    re.IGNORECASE,
)
RE_LONGAS = re.compile(
    r"Armas\s+Longas\s*,?\s*Empregadas?\s*:\s*(\d+)", re.IGNORECASE
)
RE_LOCAL = re.compile(
    r"Local\s+de\s+Atua[çc][ãa]o\s*:\s*(.+)", re.IGNORECASE
)
RE_MISSOES_OSV = re.compile(
    r"Miss[õo]es?\s*(?:/\s*Osv)?\s*:\s*(.+)", re.IGNORECASE
)
RE_ANIMAIS = re.compile(
    r"Animais\s+Empregad[oa]s?\s*:\s*(.*)", re.IGNORECASE
)

# ---------------------------------------------------------------------------
# Deteccao de fracao
# ---------------------------------------------------------------------------

RE_CMT = re.compile(r"^\s*\*?\s*Cmt\s*:\s*(.+)", re.IGNORECASE)
RE_OF_SV_CMT = re.compile(
    r"^\s*\*?\s*Of\.\s*de\s+SV\s*:\s*(.+)", re.IGNORECASE
)
RE_AUX_SV_CMT = re.compile(
    r"^\s*\*?\s*Aux\.\s*de\s+SV\s*:\s*(.+)", re.IGNORECASE
)
RE_TURNO_HEADER = re.compile(
    r"^\s*(\d+)[°º](?:/\d+[°º])?\s*(?:TURNO|T\b).*$", re.IGNORECASE
)
RE_NOME_FRACAO = re.compile(
    r"^[A-ZÀ-ÚÇ][A-ZÀ-ÚÇ\s/\-]+(?:\s+[IVX]+)?$"
)
RE_MISSAO_NUM = re.compile(
    r"^\s*\d+\.\s*MISS[ÃA]O\s*:\s*(.+)", re.IGNORECASE
)
RE_ESQ_PEL = re.compile(r"^\s*\d+[°º]\s*Esq", re.IGNORECASE)

RE_EQUIPES = re.compile(
    r"(?:Equipes?|Efetivo)\s*:\s*(?:(\d+)\s*(?:Equipes?\s*)?\(\s*(\d+)\s*PM|\(?\s*(\d+)\s*PM)",
    re.IGNORECASE,
)
RE_MISSAO = re.compile(r"Miss[ãa]o\s*:\s*(.+)", re.IGNORECASE)
RE_OSV = re.compile(r"OSv\s*:\s*(.+)", re.IGNORECASE)
RE_MUNICIPIO = re.compile(
    r"Munic[ií]pio\s*:\s*(.+)", re.IGNORECASE
)

# ---------------------------------------------------------------------------
# Fase 6.3 — grammar canonica N:N (Missao K + Municipio + BPM opcional)
# Fase 6.4 — o trecho de BPM passa a aceitar 1..N BPMs em 8 variantes; a
# extracao e conversao em lista canonica ficam com bpm_service.parse_lista_bpms.
# ---------------------------------------------------------------------------

# Tokens do trecho de BPM: com BPM ("20 BPM", "20° BPM") ou so numero ("20", "20°").
_PAT_BPM_TOKEN_COM_BPM: str = r"\d{1,3}[°º]?\s*BPM"
_PAT_BPM_TOKEN_SO_NUM:  str = r"\d{1,3}[°º]?"
# Separadores aceitos: virgula/ponto-virgula/barra com whitespace opcional, ou ' e '.
_PAT_BPM_SEP: str = r"(?:\s*[,;/]\s*|\s+e\s+)"
# Alternativa A — BPM aparece em todos os tokens ("20 BPM, 1 BPM", "20 BPM e 1 BPM").
_PAT_BPM_ALL: str = (
    rf"{_PAT_BPM_TOKEN_COM_BPM}"
    rf"(?:{_PAT_BPM_SEP}{_PAT_BPM_TOKEN_COM_BPM})*"
)
# Alternativa B — BPM aparece so no ultimo token ("20° e 1° BPM", "20/1 BPM").
_PAT_BPM_TAIL: str = (
    rf"{_PAT_BPM_TOKEN_SO_NUM}"
    rf"(?:{_PAT_BPM_SEP}{_PAT_BPM_TOKEN_SO_NUM})*"
    rf"\s*BPM"
)
# Trecho completo: A ou B. Parenteses externos opcionais no uso abaixo.
_PAT_BPM_TRECHO: str = rf"(?:{_PAT_BPM_ALL}|{_PAT_BPM_TAIL})"

RE_MISSAO_MUNICIPIO = re.compile(
    rf"^\s*Miss[ãa]o\s+(?P<ordem>\d+)\s*:\s*"
    rf"(?P<missao>.+?)\s+"
    rf"Munic[ií]pio\s*:\s*"
    rf"(?P<municipio>.+?)"
    rf"(?:\s*\(?\s*(?P<bpm>{_PAT_BPM_TRECHO})\s*\)?)?\s*$",
    re.IGNORECASE,
)

# Fallback: 'Missao K: <nome>' sem municipio na linha — tipico de missoes
# em quartel (Prontidao/Pernoite) ou casos onde operador escreve so o nome.
RE_MISSAO_ORDEM_SIMPLES = re.compile(
    r"^\s*Miss[ãa]o\s+(?P<ordem>\d+)\s*:\s*(?P<missao>.+?)\s*$",
    re.IGNORECASE,
)

RE_EQUIPES_EFETIVO = re.compile(
    r"^\s*Equipes?\s*:\s*(?P<n>\d+)\s*\(\s*(?P<efetivo>\d+)\s*PMs?\s*\)",
    re.IGNORECASE,
)

# Heuristica: missao cujo nome comeca com esses tokens -> em quartel (sem BPM).
RE_EM_QUARTEL = re.compile(
    r"^\s*(prontid[ãa]o|pernoite|aquartelado|em\s+quartel)",
    re.IGNORECASE,
)

# Normaliza captura de BPM "20° BPM", "1  BPM", etc. -> "20 BPM"
RE_BPM_NUMERO = re.compile(r"(\d{1,2})", re.ASCII)
RE_HORARIO = re.compile(
    r"Hor[áa]rio\s*(?:de\s+emprego)?\s*:\s*(.+)", re.IGNORECASE
)
RE_HORA_EMPREGO = re.compile(
    r"Hora\s+de\s+emprego\s*:\s*(.+)", re.IGNORECASE
)

# Linhas a ignorar
RE_SKIP = re.compile(
    r"^\s*("
    r"MOT\s*:|PTR\s+\d|QSO\s*:"
    r"|TOTAL\s*:\s*\d+"
    r"|\d+[°º]\s*SGT\s+PM\s*:\s*\d+"
    r"|SD\s+PM\s*:\s*\d+"
    r"|1[°º]\s*SGT\s+PM\s*:\s*\d+"
    r"|2[°º]\s*SGT\s+PM\s*:\s*\d+"
    r"|INFORMA[ÇC][ÕO]ES\s+GERAIS"
    r"|EQUIPES\s+E\s+EMPREGO"
    r"|QUADRO\s+DE\s+MEIOS"
    r"|Efetivo\s+de\s+\d"
    r"|MOT\s+OF\s+SV"
    r"|VTR\s*:\s*\*"
    r"|Local\s+de\s+atua"
    r"|Oficial\s+Supervis\w+"
    r"|Oficial\s+Superior"
    r"|DADOS\s+PARA\s+PLANILHA"
    r"|BRIGADA\s+MILITAR$"
    r"|^CPChq$"
    r"|\d+[°º]?\s*(?:BATAL[HÃA]+O|BPChq|RPMon)"
    r"|Previs[ãa]o\s+do\s+dia"
    r")",
    re.IGNORECASE,
)
RE_VTR_EQUIPE = re.compile(r"^\s*VTR/EQUIPE", re.IGNORECASE)

RE_INICIO_BLOCO_NUM = re.compile(
    r"^\s*\d*\.?\s*Efetivo\s+Total\s*:", re.IGNORECASE
)

RE_TELEFONE = re.compile(r"\(?\d{2}\)?\s*[\-]?\s*\d?\s*\d{4,5}\s*[\-]?\s*\d{3,4}")

RE_HHMM = re.compile(r"(\d{1,2})\s*[hH:]\s*(\d{0,2})")

# ---------------------------------------------------------------------------
# Normalizacao de unidade
# ---------------------------------------------------------------------------

UNIDADE_MAP: dict[str, str] = {}
for _n in range(1, 7):
    for _suf in ("BATALHÃO DE POLÍCIA DE CHOQUE", "BATALHÃO DE POLICIA DE CHOQUE",
                 "BATALHAO DE POLÍCIA DE CHOQUE", "BATALHAO DE POLICIA DE CHOQUE",
                 "BPChq", "CHOQUE"):
        UNIDADE_MAP[f"{_n} {_suf}".upper()] = f"{_n} BPChq"
        UNIDADE_MAP[f"{_n}° {_suf}".upper()] = f"{_n} BPChq"
        UNIDADE_MAP[f"{_n}º {_suf}".upper()] = f"{_n} BPChq"
for _n in range(1, 7):
    UNIDADE_MAP[f"{_n}°BPCHQ"] = f"{_n} BPChq"
    UNIDADE_MAP[f"{_n}ºBPCHQ"] = f"{_n} BPChq"
UNIDADE_MAP["4 RPMON"] = "4 RPMon"
UNIDADE_MAP["4° RPMON"] = "4 RPMon"
UNIDADE_MAP["4º RPMON"] = "4 RPMon"
UNIDADE_MAP["4°RPMON"] = "4 RPMon"
UNIDADE_MAP["4ºRPMON"] = "4 RPMon"
for _var in ("REGIMENTO DE POLICA MONTADA", "REGIMENTO DE POLICIA MONTADA",
             "REGIMENTO DE POLÍCIA MONTADA"):
    UNIDADE_MAP[f"4 {_var}"] = "4 RPMon"
    UNIDADE_MAP[f"4° {_var}"] = "4 RPMon"
    UNIDADE_MAP[f"4º {_var}"] = "4 RPMon"
    UNIDADE_MAP[f"4°{_var}"] = "4 RPMon"
    UNIDADE_MAP[f"4º{_var}"] = "4 RPMon"
