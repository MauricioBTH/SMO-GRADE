"""Decoradores de autorizacao por role."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from functools import wraps
from typing import Any

from flask import abort
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
