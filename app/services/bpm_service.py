"""CRUD/lookups do catalogo smo.bpms (Fase 6.3).

Catalogo fechado (seed via scripts/seed_bpms.py). A UI nao permite criacao
livre — operador AREI apenas seleciona no dropdown do preview. Lookup por
codigo normalizado (case-insensitive, espacos colapsados) tolera variacoes
como '20 BPM', '20° BPM', '20BPM'.
"""
from __future__ import annotations

import re
from typing import cast

from app.models.database import get_connection
from app.services.catalogo_types import Bpm

__all__ = [
    "Bpm",
    "listar_bpms",
    "listar_bpms_por_municipio",
    "get_bpm",
    "lookup_bpm_por_codigo",
    "normalizar_codigo_bpm",
    "parse_lista_bpms",
]


_RE_DIGITOS: re.Pattern[str] = re.compile(r"(\d{1,3})")
# Separador " e " (com espacos em volta) — IGNORECASE pra tolerar " E ".
_RE_SEP_E: re.Pattern[str] = re.compile(r"\s+e\s+", re.IGNORECASE)
# Separadores atomicos: virgula, ponto-virgula, barra.
_RE_SEP_PONTUACAO: re.Pattern[str] = re.compile(r"[,;/]")
# Marcador interno usado para splitar apos normalizar separadores. Escolhido
# por ser improvavel aparecer no texto original (nao e digito nem '°'/'º').
_SEP_INTERNO: str = "\x1f"


def normalizar_codigo_bpm(raw: str) -> str:
    """'20° BPM' / '20BPM' / '20 bpm' -> '20 BPM'. Entrada vazia -> ''.

    Usado tanto no lookup quanto como chave de cache em whatsapp_catalogo.
    """
    if not raw:
        return ""
    m = _RE_DIGITOS.search(raw)
    if not m:
        return ""
    return f"{int(m.group(1))} BPM"


def parse_lista_bpms(trecho: str) -> list[str]:
    """Parseia um trecho textual com 1+ BPMs nas variantes aceitas (Fase 6.4).

    Aceita (parenteses opcionais em todas):
      '20 BPM, 1 BPM'  '20 BPM e 1 BPM'  '20° e 1° BPM'  '20/1 BPM'
      '20 BPM; 1 BPM'  '(20 BPM)'        '(89 BPM)'      ...
    Separadores: ',' ';' '/' ' e '. "BPM" pode aparecer 1x ao final ou em
    cada token. '°'/'º' opcionais (normalizacao extrai o primeiro digito).

    Retorna lista de codigos canonicos ["N BPM", ...] preservando ordem e
    removendo duplicatas. Tokens sem digito sao descartados. Entrada vazia
    ou so com parenteses vazios -> [].
    """
    if not trecho:
        return []
    texto: str = trecho.strip()
    if texto.startswith("(") and texto.endswith(")"):
        texto = texto[1:-1].strip()
    if not texto:
        return []
    normalizado: str = _RE_SEP_E.sub(_SEP_INTERNO, texto)
    normalizado = _RE_SEP_PONTUACAO.sub(_SEP_INTERNO, normalizado)
    saida: list[str] = []
    vistos: set[str] = set()
    for tok in normalizado.split(_SEP_INTERNO):
        codigo: str = normalizar_codigo_bpm(tok.strip())
        if not codigo or codigo in vistos:
            continue
        vistos.add(codigo)
        saida.append(codigo)
    return saida


def _row_to_bpm(row: dict) -> Bpm:
    return Bpm(
        id=str(row["id"]),
        codigo=cast(str, row["codigo"]),
        numero=int(row["numero"]),
        municipio_id=str(row["municipio_id"]),
    )


def listar_bpms() -> list[Bpm]:
    """Retorna todos os BPMs ordenados por numero (determinismo no dropdown)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, codigo, numero, municipio_id "
                "FROM smo.bpms ORDER BY numero"
            )
            return [_row_to_bpm(dict(r)) for r in cur.fetchall()]
    finally:
        conn.close()


def listar_bpms_por_municipio(municipio_id: str) -> list[Bpm]:
    """BPMs de um municipio (POA hoje tem 6). Ordenados por numero."""
    if not municipio_id:
        return []
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, codigo, numero, municipio_id "
                "FROM smo.bpms WHERE municipio_id = %s ORDER BY numero",
                (municipio_id,),
            )
            return [_row_to_bpm(dict(r)) for r in cur.fetchall()]
    finally:
        conn.close()


def get_bpm(bpm_id: str) -> Bpm | None:
    if not bpm_id:
        return None
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, codigo, numero, municipio_id "
                "FROM smo.bpms WHERE id = %s",
                (bpm_id,),
            )
            row = cur.fetchone()
            return _row_to_bpm(dict(row)) if row else None
    finally:
        conn.close()


def lookup_bpm_por_codigo(codigo: str) -> Bpm | None:
    """Match normalizado (numero extraido). '20° BPM' casa com '20 BPM'."""
    alvo: str = normalizar_codigo_bpm(codigo)
    if not alvo:
        return None
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, codigo, numero, municipio_id "
                "FROM smo.bpms WHERE codigo = %s",
                (alvo,),
            )
            row = cur.fetchone()
            return _row_to_bpm(dict(row)) if row else None
    finally:
        conn.close()
