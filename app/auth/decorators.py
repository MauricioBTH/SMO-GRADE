"""Decoradores de autorizacao por role e por unidade."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from functools import wraps
from typing import Any

from flask import abort, request
from flask_login import current_user

from app.models.user import ROLES_VALIDOS, Role


def role_required(
    roles: Iterable[Role],
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Exige que current_user tenha um dos roles listados.

    Retorna 401 se nao logado, 403 se role nao autorizado.
    """
    roles_set: frozenset[Role] = frozenset(roles)
    desconhecidos: set[str] = {r for r in roles_set if r not in ROLES_VALIDOS}
    if desconhecidos:
        raise ValueError(f"Roles invalidos: {sorted(desconhecidos)}")

    def decorator(view: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles_set:
                abort(403)
            return view(*args, **kwargs)

        return wrapper

    return decorator


def unidade_match_required(view: Callable[..., Any]) -> Callable[..., Any]:
    """Valida que operador ALEI so acessa dados da propria unidade.

    Gestor e AREI passam direto. Para ALEI, le `unidade` de:
      1. kwargs da rota (view param)
      2. request.form (POST)
      3. request.args (GET)
      4. JSON body (payload)

    Se a unidade requisitada for diferente de current_user.unidade -> 403.
    Se nao houver unidade no request, ALEI nao pode prosseguir -> 403.
    """

    @wraps(view)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not current_user.is_authenticated:
            abort(401)
        if current_user.role in ("gestor", "operador_arei"):
            return view(*args, **kwargs)
        if current_user.role != "operador_alei":
            abort(403)

        unidade_req: str | None = kwargs.get("unidade")
        if unidade_req is None and request.form:
            unidade_req = request.form.get("unidade")
        if unidade_req is None:
            unidade_req = request.args.get("unidade")
        if unidade_req is None:
            payload = request.get_json(silent=True) or {}
            if isinstance(payload, dict):
                valor = payload.get("unidade")
                if isinstance(valor, str):
                    unidade_req = valor

        if unidade_req is None:
            abort(403)
        if current_user.unidade is None:
            abort(403)
        if unidade_req.strip() != current_user.unidade.strip():
            abort(403)
        return view(*args, **kwargs)

    return wrapper
