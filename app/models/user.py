from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from flask_login import UserMixin

Role = Literal["gestor", "operador_arei"]

ROLES_VALIDOS: Final[frozenset[Role]] = frozenset(
    ("gestor", "operador_arei")
)
ROLES_COM_2FA_OBRIGATORIO: Final[frozenset[Role]] = ROLES_VALIDOS

UNIDADES_VALIDAS: Final[frozenset[str]] = frozenset(
    (f"{n} BPChq" for n in range(1, 7))
)


@dataclass(frozen=True)
class User(UserMixin):
    id: str
    nome: str
    email: str
    role: Role
    unidade: str | None
    totp_ativo: bool
    ativo: bool

    def get_id(self) -> str:
        return self.id

    @property
    def is_active(self) -> bool:
        return self.ativo

    def requer_2fa(self) -> bool:
        return self.role in ROLES_COM_2FA_OBRIGATORIO

    def eh_gestor(self) -> bool:
        return self.role == "gestor"

    def eh_arei(self) -> bool:
        return self.role == "operador_arei"
