"""Cria o primeiro Gestor do sistema (seed bootstrap).

Uso:
    python -m scripts.seed_gestor

Pede nome, e-mail e senha via prompt interativo. Rodar 1x apos aplicar
as migrations. Se ja existe algum Gestor ativo, aborta para nao criar
duplicata acidental.
"""
from __future__ import annotations

import getpass
import sys

from app import create_app
from app.services import user_service
from app.services.user_service import UsuarioCreate


def _prompt_nao_vazio(titulo: str) -> str:
    valor: str = input(titulo).strip()
    if not valor:
        raise ValueError(f"{titulo.rstrip(': ')} nao pode estar vazio")
    return valor


def _prompt_senha() -> str:
    senha: str = getpass.getpass("Senha (min 10 caracteres): ")
    senha_conf: str = getpass.getpass("Repita a senha: ")
    if senha != senha_conf:
        raise ValueError("Senhas nao conferem")
    return senha


def main() -> int:
    app = create_app()
    with app.app_context():
        existentes = user_service.listar({"role": "gestor", "ativo": True})
        if existentes:
            print(
                f"Ja existe(m) {len(existentes)} Gestor(es) ativo(s). "
                "Nada a fazer.",
                file=sys.stderr,
            )
            return 1

        try:
            nome: str = _prompt_nao_vazio("Nome do Gestor: ")
            email: str = _prompt_nao_vazio("E-mail: ")
            senha: str = _prompt_senha()
        except (EOFError, KeyboardInterrupt):
            print("\nAbortado.", file=sys.stderr)
            return 2
        except ValueError as exc:
            print(f"Erro: {exc}", file=sys.stderr)
            return 3

        payload: UsuarioCreate = {
            "nome": nome,
            "email": email,
            "senha": senha,
            "role": "gestor",
            "unidade": None,
        }
        try:
            user = user_service.create(payload)
        except ValueError as exc:
            print(f"Erro de validacao: {exc}", file=sys.stderr)
            return 4

        print(f"Gestor criado: {user.nome} <{user.email}>")
        print("No primeiro login sera solicitada a configuracao do 2FA.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
