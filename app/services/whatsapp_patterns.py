"""
Regex patterns e constantes para o parser de texto WhatsApp.
Separado para manter whatsapp_parser.py < 500 LOC.
"""
import re

# ---------------------------------------------------------------------------
# Cabecalho — campos do bloco numerico
# ---------------------------------------------------------------------------

RE_UNIDADE = re.compile(
    r"\*\s*(\d+[°º]?\s*(?:BATAL[HÃA]+O\s+DE\s+POLI[CÇ]IA\s+DE\s+CHOQUE"
    r"|BPChq|RPMon|BATALHAO\s+DE\s+POLICIA\s+DE\s+CHOQUE))\s*\*",
    re.IGNORECASE,
)

RE_DATA = re.compile(
    r"(?:Previs[ãa]o\s+do\s+dia|Data)\s*:?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
    re.IGNORECASE,
)

RE_TURNO = re.compile(r"Turno\s*:\s*(.+)", re.IGNORECASE)

RE_OF_SUPERIOR = re.compile(
    r"Oficial\s+Superior\s+CPChq\s+(.+)", re.IGNORECASE
)

RE_COPOM = re.compile(r"COPOM\s*:\s*(.+)", re.IGNORECASE)

RE_EFETIVO_TOTAL = re.compile(r"Efetivo\s+Total\s*:\s*(\d+)", re.IGNORECASE)
RE_OFICIAL = re.compile(r"Oficial\s*(?:is)?\s*:\s*(\d+)", re.IGNORECASE)
RE_SGT = re.compile(r"Sgt\s*:\s*(\d+)", re.IGNORECASE)
RE_SD = re.compile(r"S[Dd]\s*:\s*(\d+)", re.IGNORECASE)
RE_VTRS = re.compile(r"VTRs?\s*:\s*(\d+)", re.IGNORECASE)
RE_MOTOS = re.compile(r"(\d+)\s*motocicletas?", re.IGNORECASE)
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
    r"^\s*(\d+)[°º]\s*TURNO\s*$", re.IGNORECASE
)
RE_NOME_FRACAO = re.compile(
    r"^[A-ZÀ-ÚÇ][A-ZÀ-ÚÇ\s/\-]+(?:\s+[IVX]+)?$"
)
RE_MISSAO_NUM = re.compile(
    r"^\s*\d+\.\s*MISS[ÃA]O\s*:\s*(.+)", re.IGNORECASE
)
RE_ESQ_PEL = re.compile(r"^\s*\d+[°º]\s*Esq", re.IGNORECASE)

RE_EQUIPES = re.compile(
    r"(?:Equipes?|Efetivo)\s*:\s*(\d*)\s*(?:Equipes?\s*)?\(?\s*(\d+)\s*PM",
    re.IGNORECASE,
)
RE_MISSAO = re.compile(r"Miss[ãa]o\s*:\s*(.+)", re.IGNORECASE)
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
    r"|Oficial\s+Superior"
    r")",
    re.IGNORECASE,
)
RE_VTR_EQUIPE = re.compile(r"^\s*VTR/EQUIPE", re.IGNORECASE)

RE_INICIO_BLOCO_NUM = re.compile(
    r"^\s*\d*\.?\s*Efetivo\s+Total\s*:", re.IGNORECASE
)

RE_TELEFONE = re.compile(r"\(?\d{2}\)?\s*[\-]?\s*\d{4,5}\s*[\-]?\s*\d{3,4}")

RE_HHMM = re.compile(r"(\d{1,2})\s*[h:]\s*(\d{0,2})")

# ---------------------------------------------------------------------------
# Normalizacao de unidade
# ---------------------------------------------------------------------------

UNIDADE_MAP: dict[str, str] = {}
for _n in range(1, 7):
    for _suf in ("BATALHÃO DE POLICIA DE CHOQUE", "BATALHAO DE POLICIA DE CHOQUE",
                 "BPChq"):
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
