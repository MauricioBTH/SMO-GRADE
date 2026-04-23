"""Seed das unidades operacionais do CPChq + RPMon (Fase 6.4.1).

Uso:
    python -m scripts.seed_unidades

Popula o catalogo smo.unidades com os 6 batalhoes do CPChq + 4 RPMon. Usado
pelo resolver de catalogo para derivar o municipio-sede quando uma missao
em quartel (Prontidao/Pernoite/Retorno) nao traz municipio na linha.

Dependencia: seed_catalogos.py aplicado (precisa dos municipios base).
Idempotente via ON CONFLICT (nome_normalizado).
"""
from __future__ import annotations

import sys

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402
from app.models.database import get_connection  # noqa: E402
from app.services import catalogo_service  # noqa: E402
from app.services.unidade_service import normalizar_codigo_unidade  # noqa: E402


# Lista oficial fornecida pelo cliente (CPChq-CMDT).
UNIDADES_SEDE: list[tuple[str, str]] = [
    ("1° BPChq", "Porto Alegre"),
    ("2° BPChq", "Santa Maria"),
    ("3° BPChq", "Passo Fundo"),
    ("4° BPChq", "Caxias do Sul"),
    ("5° BPChq", "Pelotas"),
    ("6° BPChq", "Uruguaiana"),
    ("4° RPMon", "Porto Alegre"),
]


def _resolver_municipio_id(nome: str) -> str:
    """Retorna o UUID do municipio-sede ou levanta RuntimeError amigavel."""
    achado = catalogo_service.lookup_municipio_por_nome(nome)
    if not achado:
        raise RuntimeError(
            f"Municipio '{nome}' nao encontrado no catalogo — "
            f"rode seed_catalogos.py antes."
        )
    return achado.id


def seed_unidades() -> int:
    criados: int = 0
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for nome, muni_nome in UNIDADES_SEDE:
                muni_id: str = _resolver_municipio_id(muni_nome)
                normalizado: str = normalizar_codigo_unidade(nome)
                cur.execute(
                    "INSERT INTO smo.unidades "
                    "(nome, nome_normalizado, municipio_sede_id) "
                    "VALUES (%s, %s, %s) "
                    "ON CONFLICT (nome_normalizado) DO NOTHING RETURNING id",
                    (nome, normalizado, muni_id),
                )
                if cur.fetchone() is not None:
                    criados += 1
                    print(f"  + {nome} ({muni_nome})")
        conn.commit()
    finally:
        conn.close()
    return criados


def main() -> int:
    app = create_app()
    with app.app_context():
        print(f"Semeando {len(UNIDADES_SEDE)} unidades...")
        try:
            n = seed_unidades()
        except RuntimeError as exc:
            print(f"Erro: {exc}", file=sys.stderr)
            return 1
        print(f"  {n} novas unidades cadastradas")
    print("Seed concluido.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
