"""CRUD tipado para smo.usuarios e helpers de senha/TOTP."""
from __future__ import annotations

import re
from datetime import datetime
from typing import TypedDict, cast

import bcrypt

from app.models.database import get_connection
from app.models.user import ROLES_VALIDOS, Role, User
from app.services.unidade_service import get_nomes_validos

SENHA_MIN_LEN: int = 8
_SENHA_ESPECIAL_RE = re.compile(r"[^A-Za-z0-9]")


class UsuarioCreate(TypedDict, total=False):
    nome: str
    email: str
    senha: str
    role: Role
    unidade: str | None


class UsuarioUpdate(TypedDict, total=False):
    nome: str
    email: str
    role: Role
    unidade: str | None
    ativo: bool


def _row_to_user(row: dict) -> User:
    role_raw: str = cast(str, row["role"])
    if role_raw not in ROLES_VALIDOS:
        raise ValueError(f"Role invalido no banco: {role_raw}")
    role: Role = cast(Role, role_raw)
    return User(
        id=str(row["id"]),
        nome=cast(str, row["nome"]),
        email=cast(str, row["email"]),
        role=role,
        unidade=cast("str | None", row["unidade"]),
        totp_ativo=bool(row["totp_ativo"]),
        ativo=bool(row["ativo"]),
    )


def _hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")


def _validar_senha(senha: str) -> None:
    if len(senha) < SENHA_MIN_LEN:
        raise ValueError(f"Senha deve ter pelo menos {SENHA_MIN_LEN} caracteres")
    if not any(c.isupper() for c in senha):
        raise ValueError("Senha deve ter pelo menos uma letra maiuscula")
    if not _SENHA_ESPECIAL_RE.search(senha):
        raise ValueError("Senha deve ter pelo menos um caractere especial")


def _validar_payload_create(payload: UsuarioCreate) -> None:
    for campo in ("nome", "email", "senha", "role"):
        if not payload.get(campo):
            raise ValueError(f"Campo obrigatorio ausente: {campo}")
    if payload["role"] not in ROLES_VALIDOS:
        raise ValueError(f"Role invalido: {payload['role']}")
    unidade = payload.get("unidade")
    if unidade and unidade not in get_nomes_validos():
        raise ValueError(f"Unidade invalida: {unidade}")


def get_by_id(user_id: str) -> User | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, nome, email, role, unidade, totp_ativo, ativo "
                "FROM smo.usuarios WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return _row_to_user(dict(row))
    finally:
        conn.close()


def get_by_email(email: str) -> User | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, nome, email, role, unidade, totp_ativo, ativo "
                "FROM smo.usuarios WHERE lower(email) = lower(%s)",
                (email.strip(),),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return _row_to_user(dict(row))
    finally:
        conn.close()


def verificar_senha(email: str, senha: str) -> User | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, nome, email, role, unidade, totp_ativo, ativo, senha_hash "
                "FROM smo.usuarios WHERE lower(email) = lower(%s) AND ativo = TRUE",
                (email.strip(),),
            )
            row = cur.fetchone()
            if row is None:
                return None
            hash_armazenado: str = cast(str, row["senha_hash"])
            if not bcrypt.checkpw(senha.encode("utf-8"), hash_armazenado.encode("utf-8")):
                return None
            return _row_to_user(dict(row))
    finally:
        conn.close()


def create(payload: UsuarioCreate) -> User:
    _validar_payload_create(payload)
    senha: str = payload["senha"]
    _validar_senha(senha)

    email_norm: str = payload["email"].strip().lower()
    if get_by_email(email_norm) is not None:
        raise ValueError(f"E-mail ja cadastrado: {email_norm}")

    unidade: str | None = payload.get("unidade")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO smo.usuarios (nome, email, senha_hash, role, unidade)
                   VALUES (%s, %s, %s, %s, %s)
                   RETURNING id, nome, email, role, unidade, totp_ativo, ativo""",
                (
                    payload["nome"].strip(),
                    email_norm,
                    _hash_senha(senha),
                    payload["role"],
                    unidade.strip() if unidade else None,
                ),
            )
            row = cur.fetchone()
            if row is None:
                raise RuntimeError("Falha ao criar usuario")
        conn.commit()
        return _row_to_user(dict(row))
    finally:
        conn.close()


def update(user_id: str, payload: UsuarioUpdate) -> User:
    campos: list[str] = []
    valores: list[object] = []
    for campo in ("nome", "email", "role", "unidade", "ativo"):
        if campo in payload:
            if campo == "role" and payload["role"] not in ROLES_VALIDOS:
                raise ValueError(f"Role invalido: {payload['role']}")
            campos.append(f"{campo} = %s")
            valor = payload[campo]  # type: ignore[literal-required]
            if campo == "email" and isinstance(valor, str):
                valor = valor.strip().lower()
            if campo == "nome" and isinstance(valor, str):
                valor = valor.strip()
            valores.append(valor)
    if not campos:
        raise ValueError("Nada para atualizar")

    unidade_final = payload.get("unidade") if "unidade" in payload else None
    if unidade_final and unidade_final not in get_nomes_validos():
        raise ValueError(f"Unidade invalida: {unidade_final}")

    valores.append(user_id)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE smo.usuarios SET {', '.join(campos)} WHERE id = %s "
                "RETURNING id, nome, email, role, unidade, totp_ativo, ativo",
                tuple(valores),
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError("Usuario nao encontrado")
        conn.commit()
        return _row_to_user(dict(row))
    finally:
        conn.close()


def desativar(user_id: str) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE smo.usuarios SET ativo = FALSE WHERE id = %s",
                (user_id,),
            )
        conn.commit()
    finally:
        conn.close()


def alterar_senha(user_id: str, senha_nova: str) -> None:
    _validar_senha(senha_nova)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE smo.usuarios SET senha_hash = %s WHERE id = %s",
                (_hash_senha(senha_nova), user_id),
            )
        conn.commit()
    finally:
        conn.close()


def set_totp_secret(user_id: str, secret: str, ativar: bool) -> None:
    if not secret:
        raise ValueError("Secret vazio")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE smo.usuarios SET totp_secret = %s, totp_ativo = %s "
                "WHERE id = %s",
                (secret, ativar, user_id),
            )
        conn.commit()
    finally:
        conn.close()


def resetar_2fa(user_id: str) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE smo.usuarios SET totp_secret = NULL, totp_ativo = FALSE "
                "WHERE id = %s",
                (user_id,),
            )
        conn.commit()
    finally:
        conn.close()


def get_totp_secret(user_id: str) -> str | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT totp_secret FROM smo.usuarios WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return cast("str | None", row["totp_secret"])
    finally:
        conn.close()


def registrar_login(user_id: str) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE smo.usuarios SET ultimo_login = %s WHERE id = %s",
                (datetime.utcnow(), user_id),
            )
        conn.commit()
    finally:
        conn.close()


class UsuarioFiltro(TypedDict, total=False):
    role: Role
    unidade: str
    ativo: bool


def listar(filtro: UsuarioFiltro | None = None) -> list[User]:
    filtro = filtro or {}
    clausulas: list[str] = []
    valores: list[object] = []
    if "role" in filtro:
        clausulas.append("role = %s")
        valores.append(filtro["role"])
    if "unidade" in filtro:
        clausulas.append("unidade = %s")
        valores.append(filtro["unidade"])
    if "ativo" in filtro:
        clausulas.append("ativo = %s")
        valores.append(filtro["ativo"])
    where = f"WHERE {' AND '.join(clausulas)}" if clausulas else ""

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, nome, email, role, unidade, totp_ativo, ativo "
                f"FROM smo.usuarios {where} ORDER BY nome",
                tuple(valores),
            )
            return [_row_to_user(dict(row)) for row in cur.fetchall()]
    finally:
        conn.close()
