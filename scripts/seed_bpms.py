"""Seed dos BPMs de Porto Alegre (CPC).

Uso:
    python -m scripts.seed_bpms

Parseia a primeira linha util de `API_Municipios_CRPMs.txt` (Comando de
Policiamento da Capital — Porto Alegre) e insere 6 BPMs:
  9 BPM, 11 BPM, 20 BPM, 1 BPM, 21 BPM, 19 BPM

Todos vinculados ao municipio_id de Porto Alegre. Idempotente — ja existente
e ignorado via ON CONFLICT.

Dependencia: seed_catalogos.py ja aplicado (precisa do municipio POA).
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

_RE_BPM: re.Pattern[str] = re.compile(r"(\d{1,2})\s*BPM", re.IGNORECASE)


@dataclass(frozen=True)
class BpmParsed:
    numero: int
    codigo: str


def parse_bpms_cpc(caminho: Path) -> list[BpmParsed]:
    """Le a linha do CPC e extrai BPMs na ordem do texto.

    Linha esperada: '... Porto Alegre; composto pelos seguintes batalhoes:
    9 BPM, 11 BPM, 20 BPM, 1 BPM, 21 BPM e 19 BPM;'
    """
    if not caminho.is_file():
        raise RuntimeError(f"Arquivo nao encontrado: {caminho}")

    texto: str = caminho.read_text(encoding="utf-8")
    # Pega o bloco do CPC ate o proximo item 'II -' (ou fim do texto).
    # Non-greedy + `;` parava no 1o ponto-e-virgula (apos "Porto Alegre;"),
    # antes da lista de BPMs.
    m = re.search(
        r"I\s*-\s*Comando\s+de\s+Policiamento\s+da\s+Capital.+?(?=\n\s*II\s*-|\Z)",
        texto,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        raise RuntimeError("Bloco do CPC nao encontrado em API_Municipios_CRPMs.txt")
    bloco: str = m.group(0)

    numeros_vistos: set[int] = set()
    resultado: list[BpmParsed] = []
    for mm in _RE_BPM.finditer(bloco):
        n = int(mm.group(1))
        if n in numeros_vistos:
            continue
        numeros_vistos.add(n)
        resultado.append(BpmParsed(numero=n, codigo=f"{n} BPM"))
    if len(resultado) < 6:
        raise RuntimeError(
            f"Esperava pelo menos 6 BPMs de POA, encontrou {len(resultado)}"
        )
    return resultado


def _resolver_municipio_poa() -> str:
    """Retorna o id do municipio 'Porto Alegre'."""
    achado = catalogo_service.lookup_municipio_por_nome("Porto Alegre")
    if not achado:
        raise RuntimeError(
            "Municipio 'Porto Alegre' nao encontrado no catalogo — "
            "rode seed_catalogos.py antes."
        )
    return achado.id


def seed_bpms(parsed: list[BpmParsed], municipio_poa_id: str) -> int:
    """Insere BPMs idempotentemente. Retorna total de novos criados."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            criados: int = 0
            for b in parsed:
                cur.execute(
                    "INSERT INTO smo.bpms (codigo, numero, municipio_id) "
                    "VALUES (%s, %s, %s) "
                    "ON CONFLICT (codigo) DO NOTHING RETURNING id",
                    (b.codigo, b.numero, municipio_poa_id),
                )
                if cur.fetchone() is not None:
                    criados += 1
                    print(f"  + BPM {b.codigo}")
        conn.commit()
        return criados
    finally:
        conn.close()


def main() -> int:
    try:
        parsed = parse_bpms_cpc(API_TXT)
    except RuntimeError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    app = create_app()
    with app.app_context():
        try:
            poa_id: str = _resolver_municipio_poa()
        except RuntimeError as exc:
            print(f"Erro: {exc}", file=sys.stderr)
            return 1
        print(f"Semeando {len(parsed)} BPMs em Porto Alegre...")
        n = seed_bpms(parsed, poa_id)
        print(f"  {n} novos BPMs cadastrados")
    print("Seed concluido.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
