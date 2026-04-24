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

import psycopg2

from app.models.database import get_connection
from app.services.catalogo_types import Unidade, UnidadeCreate, UnidadeUpdate

__all__ = [
    "Unidade",
    "UnidadeCreate",
    "UnidadeUpdate",
    "listar_unidades",
    "get_unidade",
    "lookup_unidade_por_nome",
    "normalizar_codigo_unidade",
    "get_nomes_validos",
    "invalidar_cache_nomes",
    "criar_unidade",
    "atualizar_unidade",
]

_NOME_MAX_LEN: int = 60

_cache_nomes_validos: frozenset[str] | None = None


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


def get_nomes_validos() -> frozenset[str]:
    """Conjunto de nomes de unidade aceitos pela aplicacao (cacheado).

    Inclui o nome canonico do DB (ex: '1° BPChq') + variante sem '°'/'º'
    (ex: '1 BPChq') pra tolerar dados historicos e texto WhatsApp sem grau.
    Usado pela validacao de user.unidade (admin), validacao de rotas
    (/operador/historico/<unidade>/<data>) e xlsx_validator.

    Cache invalidado via invalidar_cache_nomes() apos mutacoes no catalogo.
    """
    global _cache_nomes_validos
    if _cache_nomes_validos is None:
        nomes: set[str] = {u.nome for u in listar_unidades(somente_ativas=True)}
        nomes |= {n.replace("° ", " ").replace("º ", " ") for n in nomes}
        _cache_nomes_validos = frozenset(nomes)
    return _cache_nomes_validos


def invalidar_cache_nomes() -> None:
    """Limpa o cache de get_nomes_validos. Chamar apos criar/atualizar
    unidades (Admin UI) ou desativar uma."""
    global _cache_nomes_validos
    _cache_nomes_validos = None


def criar_unidade(payload: UnidadeCreate) -> Unidade:
    """Cria unidade ativa, normaliza o nome, valida duplicidade + sede.

    Invalida o cache de get_nomes_validos. Levanta ValueError em caso de
    input invalido ou nome_normalizado ja existente.
    """
    nome: str = (payload.get("nome") or "").strip()
    municipio_sede_id: str = (payload.get("municipio_sede_id") or "").strip()
    if not nome:
        raise ValueError("Nome obrigatorio")
    if len(nome) > _NOME_MAX_LEN:
        raise ValueError(f"Nome excede {_NOME_MAX_LEN} caracteres")
    if not municipio_sede_id:
        raise ValueError("Municipio sede obrigatorio")
    normalizado: str = normalizar_codigo_unidade(nome)
    if not normalizado:
        raise ValueError(
            "Nome deve seguir o padrao '<numero> <sigla>' (ex: '7° BPChq')"
        )

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "INSERT INTO smo.unidades "
                    "(nome, nome_normalizado, municipio_sede_id) "
                    "VALUES (%s, %s, %s) "
                    "RETURNING id, nome, nome_normalizado, "
                    "municipio_sede_id, ativo",
                    (nome, normalizado, municipio_sede_id),
                )
            except psycopg2.errors.UniqueViolation as exc:
                conn.rollback()
                raise ValueError(
                    f"Unidade '{normalizado}' ja existe no catalogo"
                ) from exc
            except psycopg2.errors.ForeignKeyViolation as exc:
                conn.rollback()
                raise ValueError("Municipio sede invalido") from exc
            row = cur.fetchone()
            if row is None:
                raise RuntimeError("INSERT smo.unidades nao retornou id")
        conn.commit()
    finally:
        conn.close()
    invalidar_cache_nomes()
    return _row_to_unidade(dict(row))


def atualizar_unidade(unidade_id: str, payload: UnidadeUpdate) -> Unidade:
    """Atualiza nome/municipio_sede/ativo. Renormaliza se nome mudar.

    Invalida o cache de get_nomes_validos. Levanta ValueError se nada
    pra atualizar, unidade inexistente ou constraint violada.
    """
    campos: list[str] = []
    valores: list[object] = []
    if "nome" in payload:
        novo_nome: str = (payload.get("nome") or "").strip()
        if not novo_nome:
            raise ValueError("Nome nao pode ser vazio")
        if len(novo_nome) > _NOME_MAX_LEN:
            raise ValueError(f"Nome excede {_NOME_MAX_LEN} caracteres")
        normalizado: str = normalizar_codigo_unidade(novo_nome)
        if not normalizado:
            raise ValueError(
                "Nome deve seguir o padrao '<numero> <sigla>'"
            )
        campos.append("nome = %s")
        valores.append(novo_nome)
        campos.append("nome_normalizado = %s")
        valores.append(normalizado)
    if "municipio_sede_id" in payload:
        sede: str = (payload.get("municipio_sede_id") or "").strip()
        if not sede:
            raise ValueError("Municipio sede nao pode ser vazio")
        campos.append("municipio_sede_id = %s")
        valores.append(sede)
    if "ativo" in payload:
        campos.append("ativo = %s")
        valores.append(bool(payload["ativo"]))
    if not campos:
        raise ValueError("Nada para atualizar")

    valores.append(unidade_id)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    f"UPDATE smo.unidades SET {', '.join(campos)} "
                    "WHERE id = %s RETURNING id, nome, nome_normalizado, "
                    "municipio_sede_id, ativo",
                    tuple(valores),
                )
            except psycopg2.errors.UniqueViolation as exc:
                conn.rollback()
                raise ValueError(
                    "Ja existe outra unidade com esse nome normalizado"
                ) from exc
            except psycopg2.errors.ForeignKeyViolation as exc:
                conn.rollback()
                raise ValueError("Municipio sede invalido") from exc
            row = cur.fetchone()
            if row is None:
                raise ValueError("Unidade nao encontrada")
        conn.commit()
    finally:
        conn.close()
    invalidar_cache_nomes()
    return _row_to_unidade(dict(row))


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
