"""Seed dos catalogos smo.crpms, smo.municipios e smo.missoes.

Uso:
    python -m scripts.seed_catalogos

Parseia `API_Municipios_CRPMs.txt` (Art. 3o, 21 CRPMs) e insere:
  * 21 CRPMs (ordem I..XXI -> 1..21)
  * Todos os municipios listados, vinculados ao CRPM da sua circunscricao
  * Lista curada inicial de missoes padrao (pode ser expandida via UI)

Idempotente: checa existencia antes de inserir (ON CONFLICT DO NOTHING via
lookups). Rodar 1x apos `python -m scripts.migrate`.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402
from app.models.database import get_connection  # noqa: E402
from app.services import catalogo_service  # noqa: E402

ROOT_DIR: Path = Path(__file__).resolve().parent.parent
API_TXT: Path = ROOT_DIR / "API_Municipios_CRPMs.txt"

_RE_LINHA_CRPM: re.Pattern[str] = re.compile(
    r"^\s*(?P<rom>[IVX]+)\s*-\s*(?P<nome>[^-]+?)\s*-\s*(?P<sigla>[A-Z/]+)\s*"
    r"(?:,\s*com\s+sede\s+em\s+(?P<sede>[^:]+?)\s*:|:\s*)"
    r"\s*Munic[ií]pios?\s+(?:de|em|do|da)?\s*(?P<munic>.+?);?\s*$",
    re.IGNORECASE,
)

_ROMAN_TO_INT: dict[str, int] = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8,
    "IX": 9, "X": 10, "XI": 11, "XII": 12, "XIII": 13, "XIV": 14, "XV": 15,
    "XVI": 16, "XVII": 17, "XVIII": 18, "XIX": 19, "XX": 20, "XXI": 21,
}

# Missoes padrao (caixa alta). Pode crescer via /admin/catalogos/missoes.
MISSOES_PADRAO: tuple[tuple[str, str], ...] = (
    ("PATRULHAMENTO OSTENSIVO", "Patrulhamento rotineiro de area"),
    ("OPERACAO CENTRO", "Operacao focada em area central"),
    ("ESCOLTA", "Escolta de autoridade ou comboio"),
    ("ROTA DAS CONVIVENCIAS", "Operacao Rota das Convivencias"),
    ("RADIOPATRULHAMENTO", "Resposta por radiopatrulha"),
    ("OPERACAO AVANTE", "Operacao Avante"),
    ("OPERACAO SERRA SEGURA", "Operacao Serra Segura"),
    ("CHOQUE DE ORDEM", "Choque de Ordem Publica"),
)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CrpmParsed:
    ordem: int
    sigla: str
    nome: str
    sede: str | None
    municipios: tuple[str, ...]


def _limpar_municipio(m: str) -> str:
    """Limpa sufixos, espacos e tags no nome do municipio."""
    s = m.strip().rstrip(";").rstrip(".").strip()
    s = re.sub(r"\be\s+Viam[aã]o\s*$", "Viamao", s)  # pontual - termino com "e "
    s = re.sub(r"^e\s+", "", s, flags=re.IGNORECASE)
    return s.strip()


def _split_municipios(raw: str) -> list[str]:
    """Separa lista 'a, b, c e d' em lista limpa, tratando ultimo ' e '."""
    raw = raw.rstrip("; ").strip()
    raw = re.sub(r"\s+e\s+(?=[A-Z])", ", ", raw)
    partes = [p.strip() for p in raw.split(",")]
    return [p for p in (_limpar_municipio(x) for x in partes) if p]


def parse_api_txt(caminho: Path) -> list[CrpmParsed]:
    """Le o TXT normativo e retorna 21 CrpmParsed."""
    if not caminho.is_file():
        raise RuntimeError(f"Arquivo nao encontrado: {caminho}")

    texto: str = caminho.read_text(encoding="utf-8")

    resultado: list[CrpmParsed] = []
    # Cada CRPM fica em uma linha terminada por ';' ou 'e' final
    # Dividir por linhas que comecem com numeral romano
    regex_linha = re.compile(
        r"(?P<rom>[IVX]+)\s*-\s*(?P<corpo>[^;]+?);",
        re.MULTILINE,
    )

    for match in regex_linha.finditer(texto + ";"):
        rom = match.group("rom")
        if rom not in _ROMAN_TO_INT:
            continue
        corpo: str = match.group("corpo").strip()
        # Extrair sigla: esta depois de " - " no comeco
        m_sigla = re.match(
            r"(?P<nome>[^-]+?)\s*-\s*(?P<sigla>[A-Z/]+)\s*(?:,\s*com\s+sede\s+em\s+(?P<sede>[^:]+?))?\s*:\s*(?P<rest>.+)",
            corpo,
            re.IGNORECASE | re.DOTALL,
        )
        if not m_sigla:
            continue
        nome = m_sigla.group("nome").strip()
        sigla = m_sigla.group("sigla").strip().upper()
        sede_raw = m_sigla.group("sede")
        sede = sede_raw.strip() if sede_raw else None
        rest = m_sigla.group("rest").strip()
        # 'rest' inicia com "Municipio de Porto Alegre;" ou "Municipios de a, b..."
        m_mun = re.match(
            r"Munic[ií]pios?\s+(?:de|em|do|da)?\s*(?P<lista>.+)",
            rest,
            re.IGNORECASE | re.DOTALL,
        )
        lista_raw: str = m_mun.group("lista") if m_mun else rest
        municipios = tuple(_split_municipios(lista_raw))

        resultado.append(CrpmParsed(
            ordem=_ROMAN_TO_INT[rom],
            sigla=sigla,
            nome=nome,
            sede=sede,
            municipios=municipios,
        ))

    resultado.sort(key=lambda x: x.ordem)
    return resultado


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------


def seed_crpms(parsed: list[CrpmParsed]) -> dict[str, str]:
    """Insere CRPMs idempotentemente. Retorna {sigla: id}."""
    mapa: dict[str, str] = {}
    for p in parsed:
        existente = catalogo_service.get_crpm_por_sigla(p.sigla)
        if existente:
            mapa[p.sigla] = existente.id
            continue
        novo = catalogo_service.criar_crpm({
            "sigla": p.sigla, "nome": p.nome, "sede": p.sede, "ordem": p.ordem,
        })
        mapa[p.sigla] = novo.id
        print(f"  + CRPM {novo.sigla} ({novo.ordem})")
    return mapa


def seed_municipios(
    parsed: list[CrpmParsed], crpm_ids: dict[str, str]
) -> int:
    """Insere municipios em lote usando UMA conexao + ON CONFLICT DO NOTHING.

    Depende da constraint UNIQUE (nome, crpm_id) criada na migration 003.
    Retorna o total efetivamente inserido (excluindo duplicados).
    """
    pares: list[tuple[str, str]] = [
        (nome, crpm_ids[p.sigla])
        for p in parsed if p.sigla in crpm_ids
        for nome in p.municipios
    ]
    if not pares:
        return 0

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            from psycopg2.extras import execute_values
            inseridos = execute_values(
                cur,
                "INSERT INTO smo.municipios (nome, crpm_id) VALUES %s "
                "ON CONFLICT (nome, crpm_id) DO NOTHING RETURNING id",
                pares, fetch=True,
            )
            conn.commit()
            return len(inseridos)
    finally:
        conn.close()


def seed_missoes() -> int:
    """Insere missoes padrao idempotentemente. Retorna total novas."""
    criadas: int = 0
    for nome, desc in MISSOES_PADRAO:
        ja = catalogo_service.lookup_missao_por_nome(nome)
        if ja:
            continue
        catalogo_service.criar_missao({"nome": nome, "descricao": desc})
        criadas += 1
        print(f"  + missao '{nome}'")
    return criadas


def main() -> int:
    try:
        parsed = parse_api_txt(API_TXT)
    except RuntimeError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    if len(parsed) != 21:
        print(
            f"Aviso: esperava 21 CRPMs, parser encontrou {len(parsed)}",
            file=sys.stderr,
        )

    app = create_app()
    with app.app_context():
        print(f"Semeando {len(parsed)} CRPMs...")
        crpm_ids = seed_crpms(parsed)
        print(f"Semeando municipios...")
        n_mun = seed_municipios(parsed, crpm_ids)
        print(f"  {n_mun} novos municipios")
        print(f"Semeando missoes padrao...")
        n_mis = seed_missoes()
        print(f"  {n_mis} novas missoes")
    print("Seed concluido.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
