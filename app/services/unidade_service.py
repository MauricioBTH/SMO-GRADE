"""Lookups do catalogo smo.unidades (Fase 6.4.1).

Catalogo fechado e pequeno (~7 unidades: 1°-6° BPChq + 4° RPMon). Seed via
scripts/seed_unidades.py. Uso principal: derivar municipio_sede_id para
missoes em quartel (Prontidao/Pernoite/Retorno) que nao trazem municipio
na linha do WhatsApp — o resolver do catalogo usa a unidade da fracao.

Lookup por nome_normalizado (digito + sigla uppercase, ex: '1 BPCHQ') —
tolera variantes: '1°BPChq' / '1 BPChq' / '1º BPChq' / '1ºBPChq'.
"""
from __future__ import annotations

import re
from typing import cast

from app.models.database import get_connection
from app.services.catalogo_types import Unidade

__all__ = [
    "Unidade",
    "listar_unidades",
    "get_unidade",
    "lookup_unidade_por_nome",
    "normalizar_codigo_unidade",
]


# Extrai primeiro digito (1-3) + sigla alfabetica. Tolera '°'/'º' e espacos
# opcionais. Ex: '1° BPChq' / '4ºRPMon' / '20 BPChq'.
_RE_UNIDADE: re.Pattern[str] = re.compile(
    r"(\d{1,3})\s*[°º]?\s*([A-Za-z]+)"
)


def normalizar_codigo_unidade(raw: str) -> str:
    """'1° BPChq' / '1BPChq' / '4º RPMon' -> '1 BPCHQ' / '4 RPMON'.
    Entrada vazia ou sem digito+sigla -> ''.
    """
    if not raw:
        return ""
    m = _RE_UNIDADE.search(raw)
    if not m:
        return ""
    return f"{int(m.group(1))} {m.group(2).upper()}"


def _row_to_unidade(row: dict) -> Unidade:
    return Unidade(
        id=str(row["id"]),
        nome=cast(str, row["nome"]),
        nome_normalizado=cast(str, row["nome_normalizado"]),
        municipio_sede_id=str(row["municipio_sede_id"]),
        ativo=bool(row["ativo"]),
    )


def listar_unidades(somente_ativas: bool = True) -> list[Unidade]:
    where: str = "WHERE ativo = TRUE" if somente_ativas else ""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT id, nome, nome_normalizado, municipio_sede_id, ativo "
                f"FROM smo.unidades {where} ORDER BY nome_normalizado"
            )
            return [_row_to_unidade(dict(r)) for r in cur.fetchall()]
    finally:
        conn.close()


def get_unidade(unidade_id: str) -> Unidade | None:
    if not unidade_id:
        return None
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, nome, nome_normalizado, municipio_sede_id, ativo "
                "FROM smo.unidades WHERE id = %s",
                (unidade_id,),
            )
            row = cur.fetchone()
            return _row_to_unidade(dict(row)) if row else None
    finally:
        conn.close()


def lookup_unidade_por_nome(raw: str) -> Unidade | None:
    """Match por nome_normalizado. '1° BPChq' casa com '1 BPCHQ'."""
    alvo: str = normalizar_codigo_unidade(raw)
    if not alvo:
        return None
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, nome, nome_normalizado, municipio_sede_id, ativo "
                "FROM smo.unidades WHERE nome_normalizado = %s",
                (alvo,),
            )
            row = cur.fetchone()
            return _row_to_unidade(dict(row)) if row else None
    finally:
        conn.close()
