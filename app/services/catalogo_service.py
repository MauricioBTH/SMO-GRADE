"""CRUD e lookups dos catalogos smo.crpms / smo.municipios / smo.missoes."""
from __future__ import annotations

from typing import cast

import psycopg2

from app.models.database import get_connection
from app.services.catalogo_types import (
    Crpm, CrpmCreate, Missao, MissaoCreate, MissaoUpdate,
    Municipio, MunicipioCreate, MunicipioUpdate, normalizar,
)

__all__ = [
    "Crpm", "Missao", "Municipio",
    "CrpmCreate", "MissaoCreate", "MissaoUpdate",
    "MunicipioCreate", "MunicipioUpdate", "normalizar",
    "listar_crpms", "get_crpm_por_id", "get_crpm_por_sigla", "criar_crpm",
    "listar_municipios", "get_municipio", "lookup_municipio_por_nome",
    "criar_municipio", "atualizar_municipio",
    "listar_missoes", "get_missao", "lookup_missao_por_nome",
    "criar_missao", "atualizar_missao",
]


def _row_to_crpm(row: dict) -> Crpm:
    return Crpm(
        id=str(row["id"]),
        sigla=cast(str, row["sigla"]),
        nome=cast(str, row["nome"]),
        sede=cast("str | None", row.get("sede")),
        ordem=int(row["ordem"]),
        ativo=bool(row["ativo"]),
    )


def _row_to_municipio(row: dict) -> Municipio:
    return Municipio(
        id=str(row["id"]),
        nome=cast(str, row["nome"]),
        crpm_id=str(row["crpm_id"]),
        crpm_sigla=cast(str, row.get("crpm_sigla", "")),
        ativo=bool(row["ativo"]),
    )


def _row_to_missao(row: dict) -> Missao:
    return Missao(
        id=str(row["id"]),
        nome=cast(str, row["nome"]),
        descricao=cast("str | None", row.get("descricao")),
        ativo=bool(row["ativo"]),
    )


# ---------------------------------------------------------------------------
# CRPMs (leitura pela UI; escrita apenas via seed)
# ---------------------------------------------------------------------------


def listar_crpms(somente_ativos: bool = True) -> list[Crpm]:
    where: str = "WHERE ativo = TRUE" if somente_ativos else ""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT id, sigla, nome, sede, ordem, ativo FROM smo.crpms "
                f"{where} ORDER BY ordem"
            )
            return [_row_to_crpm(dict(r)) for r in cur.fetchall()]
    finally:
        conn.close()


def get_crpm_por_id(crpm_id: str) -> Crpm | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, sigla, nome, sede, ordem, ativo FROM smo.crpms "
                "WHERE id = %s",
                (crpm_id,),
            )
            row = cur.fetchone()
            return _row_to_crpm(dict(row)) if row else None
    finally:
        conn.close()


def get_crpm_por_sigla(sigla: str) -> Crpm | None:
    sigla_norm: str = sigla.strip()
    if not sigla_norm:
        return None
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, sigla, nome, sede, ordem, ativo FROM smo.crpms "
                "WHERE UPPER(sigla) = UPPER(%s)",
                (sigla_norm,),
            )
            row = cur.fetchone()
            return _row_to_crpm(dict(row)) if row else None
    finally:
        conn.close()


def criar_crpm(payload: CrpmCreate) -> Crpm:
    """Usado somente pelo seed. UI nao permite criar CRPMs (lista normativa fechada)."""
    for campo in ("sigla", "nome", "ordem"):
        if campo not in payload or payload.get(campo) in (None, ""):
            raise ValueError(f"Campo obrigatorio: {campo}")
    sigla: str = cast(str, payload["sigla"]).strip()
    nome: str = cast(str, payload["nome"]).strip()
    sede_val = payload.get("sede")
    sede: str | None = (
        sede_val.strip() if isinstance(sede_val, str) and sede_val.strip() else None
    )
    ordem: int = int(payload["ordem"])
    if ordem < 1 or ordem > 99:
        raise ValueError("ordem fora do intervalo 1..99")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO smo.crpms (sigla, nome, sede, ordem) "
                "VALUES (%s, %s, %s, %s) "
                "RETURNING id, sigla, nome, sede, ordem, ativo",
                (sigla, nome, sede, ordem),
            )
            row = cur.fetchone()
            if row is None:
                raise RuntimeError("Falha ao inserir CRPM")
        conn.commit()
        return _row_to_crpm(dict(row))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Municipios
# ---------------------------------------------------------------------------


_SQL_MUNICIPIO_BASE: str = (
    "SELECT m.id, m.nome, m.crpm_id, m.ativo, c.sigla AS crpm_sigla "
    "FROM smo.municipios m JOIN smo.crpms c ON c.id = m.crpm_id"
)


def listar_municipios(
    crpm_id: str | None = None,
    q: str | None = None,
    somente_ativos: bool = True,
    limite: int = 500,
) -> list[Municipio]:
    clausulas: list[str] = []
    valores: list[object] = []
    if somente_ativos:
        clausulas.append("m.ativo = TRUE")
    if crpm_id:
        clausulas.append("m.crpm_id = %s")
        valores.append(crpm_id)
    if q:
        q_norm: str = q.strip()
        if q_norm:
            clausulas.append("LOWER(m.nome) LIKE LOWER(%s)")
            valores.append(f"%{q_norm}%")
    where: str = f"WHERE {' AND '.join(clausulas)}" if clausulas else ""
    valores.append(int(limite))

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"{_SQL_MUNICIPIO_BASE} {where} ORDER BY m.nome LIMIT %s",
                tuple(valores),
            )
            return [_row_to_municipio(dict(r)) for r in cur.fetchall()]
    finally:
        conn.close()


def get_municipio(id_municipio: str) -> Municipio | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"{_SQL_MUNICIPIO_BASE} WHERE m.id = %s", (id_municipio,))
            row = cur.fetchone()
            return _row_to_municipio(dict(row)) if row else None
    finally:
        conn.close()


def lookup_municipio_por_nome(
    nome: str, crpm_id: str | None = None
) -> Municipio | None:
    """Match exato por nome normalizado. Filtro em Python (sem extensao unaccent)."""
    nome_norm: str = normalizar(nome)
    if not nome_norm:
        return None
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if crpm_id:
                cur.execute(
                    f"{_SQL_MUNICIPIO_BASE} WHERE m.ativo = TRUE AND m.crpm_id = %s",
                    (crpm_id,),
                )
            else:
                cur.execute(f"{_SQL_MUNICIPIO_BASE} WHERE m.ativo = TRUE")
            candidatos: list[dict] = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    for row in candidatos:
        if normalizar(cast(str, row["nome"])) == nome_norm:
            return _row_to_municipio(row)
    return None


def criar_municipio(payload: MunicipioCreate) -> Municipio:
    for campo in ("nome", "crpm_id"):
        if not payload.get(campo):
            raise ValueError(f"Campo obrigatorio: {campo}")
    nome: str = cast(str, payload["nome"]).strip()
    if not nome:
        raise ValueError("nome nao pode ser vazio")
    crpm_id: str = cast(str, payload["crpm_id"])
    if get_crpm_por_id(crpm_id) is None:
        raise ValueError("CRPM inexistente")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "INSERT INTO smo.municipios (nome, crpm_id) VALUES (%s, %s) "
                    "RETURNING id",
                    (nome, crpm_id),
                )
            except psycopg2.errors.UniqueViolation as exc:
                conn.rollback()
                raise ValueError(
                    f"Municipio '{nome}' ja cadastrado neste CRPM"
                ) from exc
            row = cur.fetchone()
            if row is None:
                raise RuntimeError("Falha ao inserir municipio")
            mun_id: str = str(row["id"])
        conn.commit()
    finally:
        conn.close()

    resultado = get_municipio(mun_id)
    if resultado is None:
        raise RuntimeError("Municipio criado mas nao pode ser relido")
    return resultado


def atualizar_municipio(id_municipio: str, payload: MunicipioUpdate) -> Municipio:
    campos: list[str] = []
    valores: list[object] = []
    if "nome" in payload:
        nome = cast(str, payload["nome"]).strip()
        if not nome:
            raise ValueError("nome nao pode ser vazio")
        campos.append("nome = %s")
        valores.append(nome)
    if "crpm_id" in payload:
        crpm_id = cast(str, payload["crpm_id"])
        if get_crpm_por_id(crpm_id) is None:
            raise ValueError("CRPM inexistente")
        campos.append("crpm_id = %s")
        valores.append(crpm_id)
    if "ativo" in payload:
        campos.append("ativo = %s")
        valores.append(bool(payload["ativo"]))
    if not campos:
        raise ValueError("Nada para atualizar")

    valores.append(id_municipio)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    f"UPDATE smo.municipios SET {', '.join(campos)} "
                    f"WHERE id = %s RETURNING id",
                    tuple(valores),
                )
            except psycopg2.errors.UniqueViolation as exc:
                conn.rollback()
                raise ValueError("Municipio duplicado neste CRPM") from exc
            row = cur.fetchone()
            if row is None:
                raise ValueError("Municipio nao encontrado")
        conn.commit()
    finally:
        conn.close()

    resultado = get_municipio(id_municipio)
    if resultado is None:
        raise RuntimeError("Municipio atualizado mas nao encontrado")
    return resultado


# ---------------------------------------------------------------------------
# Missoes
# ---------------------------------------------------------------------------


def listar_missoes(
    q: str | None = None, somente_ativas: bool = True, limite: int = 500
) -> list[Missao]:
    clausulas: list[str] = []
    valores: list[object] = []
    if somente_ativas:
        clausulas.append("ativo = TRUE")
    if q:
        q_norm: str = q.strip()
        if q_norm:
            clausulas.append("LOWER(nome) LIKE LOWER(%s)")
            valores.append(f"%{q_norm}%")
    where: str = f"WHERE {' AND '.join(clausulas)}" if clausulas else ""
    valores.append(int(limite))

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT id, nome, descricao, ativo FROM smo.missoes "
                f"{where} ORDER BY nome LIMIT %s",
                tuple(valores),
            )
            return [_row_to_missao(dict(r)) for r in cur.fetchall()]
    finally:
        conn.close()


def get_missao(id_missao: str) -> Missao | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, nome, descricao, ativo FROM smo.missoes WHERE id = %s",
                (id_missao,),
            )
            row = cur.fetchone()
            return _row_to_missao(dict(row)) if row else None
    finally:
        conn.close()


def lookup_missao_por_nome(nome: str) -> Missao | None:
    """Match exato por nome normalizado (uppercase, sem acentos, trim)."""
    nome_norm: str = normalizar(nome)
    if not nome_norm:
        return None
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, nome, descricao, ativo FROM smo.missoes "
                "WHERE ativo = TRUE"
            )
            candidatos: list[dict] = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    for row in candidatos:
        if normalizar(cast(str, row["nome"])) == nome_norm:
            return _row_to_missao(row)
    return None


def criar_missao(payload: MissaoCreate) -> Missao:
    if not payload.get("nome"):
        raise ValueError("Campo obrigatorio: nome")
    nome: str = cast(str, payload["nome"]).strip().upper()
    if not nome:
        raise ValueError("nome nao pode ser vazio")
    descricao_val = payload.get("descricao")
    descricao: str | None = (
        descricao_val.strip()
        if isinstance(descricao_val, str) and descricao_val.strip() else None
    )

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "INSERT INTO smo.missoes (nome, descricao) VALUES (%s, %s) "
                    "RETURNING id, nome, descricao, ativo",
                    (nome, descricao),
                )
            except psycopg2.errors.UniqueViolation as exc:
                conn.rollback()
                raise ValueError(f"Missao '{nome}' ja cadastrada") from exc
            row = cur.fetchone()
            if row is None:
                raise RuntimeError("Falha ao inserir missao")
        conn.commit()
        return _row_to_missao(dict(row))
    finally:
        conn.close()


def atualizar_missao(id_missao: str, payload: MissaoUpdate) -> Missao:
    campos: list[str] = []
    valores: list[object] = []
    if "nome" in payload:
        nome = cast(str, payload["nome"]).strip().upper()
        if not nome:
            raise ValueError("nome nao pode ser vazio")
        campos.append("nome = %s")
        valores.append(nome)
    if "descricao" in payload:
        dvalor = payload.get("descricao")
        descricao = (
            dvalor.strip() if isinstance(dvalor, str) and dvalor.strip() else None
        )
        campos.append("descricao = %s")
        valores.append(descricao)
    if "ativo" in payload:
        campos.append("ativo = %s")
        valores.append(bool(payload["ativo"]))
    if not campos:
        raise ValueError("Nada para atualizar")

    valores.append(id_missao)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    f"UPDATE smo.missoes SET {', '.join(campos)} WHERE id = %s "
                    f"RETURNING id, nome, descricao, ativo",
                    tuple(valores),
                )
            except psycopg2.errors.UniqueViolation as exc:
                conn.rollback()
                raise ValueError("Nome de missao duplicado") from exc
            row = cur.fetchone()
            if row is None:
                raise ValueError("Missao nao encontrada")
        conn.commit()
        return _row_to_missao(dict(row))
    finally:
        conn.close()
