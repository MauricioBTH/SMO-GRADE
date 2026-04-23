"""Agregacoes sobre smo.fracao_missoes (vertices N:N) — Fase 6.3.

Tres camadas de leitura, na ordem de maior-para-menor fidelidade:

  1. **Deterministica** (`agregar_por_missao`, `agregar_por_municipio`):
     agrupa por missao_id / municipio_id quando presentes. E a camada usada
     pelos rankings principais.

  2. **Normalizada** (`agregar_normalizado_por_missao`): agrupa por forma
     canonica do texto livre (`NFD+upper+trim`). Util enquanto o catalogo
     nao esta 100% coberto — mostra "PRONTIDAO" junto com "Prontidão" e
     "prontidao,". Nao depende de missao_id.

  3. **Catalogada pura** (`agregar_apenas_catalogadas`): filtra vertices
     com missao_id IS NOT NULL e retorna o agregado — versao "limpa" para
     painel comparar contra a deterministica.

Alem das 3, `saude_catalogacao` devolve o `%` de vertices com missao_id
e com municipio_id — serve de indicador para o operador saber quanto da
triagem ainda falta. Entrada em todas: list[dict] vinda de
`db_service.fetch_vertices_by_range`.
"""
from __future__ import annotations

from collections import defaultdict
from typing import TypedDict, cast

from app.services.catalogo_types import normalizar


class AgregadoMissao(TypedDict):
    missao_id: str | None
    missao_nome: str
    total_fracoes: int
    total_equipes: int
    total_pms: int
    unidades: list[str]


class AgregadoMunicipio(TypedDict):
    municipio_id: str | None
    municipio_nome: str
    crpm_sigla: str
    total_fracoes: int
    total_equipes: int
    total_pms: int


class AgregadoNormalizado(TypedDict):
    chave_normalizada: str
    textos_agrupados: list[str]
    total_vertices: int
    total_pms: int
    pct_catalogado: float  # % daqueles com missao_id != None


class SaudeCatalogacao(TypedDict):
    total_vertices: int
    com_missao_id: int
    com_municipio_id: int
    pct_missao: float
    pct_municipio: float


def _safe_int(v: object) -> int:
    try:
        return int(v) if v is not None else 0
    except (TypeError, ValueError):
        return 0


def _nome_raw(v: dict) -> str:
    """Extrai o texto bruto de missao do vertice (ou do registro legado)."""
    return cast(str, v.get("missao_nome_raw") or v.get("missao") or "").strip()


def agregar_por_missao(vertices: list[dict]) -> list[AgregadoMissao]:
    """Camada deterministica: agrupa por missao_id quando existe; sem id,
    colapsa por texto normalizado em "SEM CATALOGO: <texto>". Ordena por
    total_pms DESC, total_fracoes DESC.
    """
    buckets: dict[tuple[str | None, str], dict] = defaultdict(
        lambda: {
            "total_fracoes": 0, "total_equipes": 0, "total_pms": 0,
            "unidades": set(),
        }
    )

    for vt in vertices:
        mid_val = vt.get("missao_id")
        mid: str | None = str(mid_val) if mid_val else None
        if mid:
            nome: str = cast(str, vt.get("missao_nome") or "").strip()
            if not nome:
                nome = _nome_raw(vt).upper()
        else:
            bruto: str = _nome_raw(vt).upper()
            nome = f"SEM CATALOGO: {bruto}" if bruto else "SEM CATALOGO"

        key: tuple[str | None, str] = (mid, nome)
        b = buckets[key]
        b["total_fracoes"] += 1
        b["total_equipes"] += _safe_int(vt.get("equipes"))
        b["total_pms"] += _safe_int(vt.get("pms"))
        uni: str = cast(str, vt.get("unidade") or "")
        if uni:
            cast("set[str]", b["unidades"]).add(uni)

    saida: list[AgregadoMissao] = []
    for (mid, nome), b in buckets.items():
        saida.append(AgregadoMissao(
            missao_id=mid,
            missao_nome=nome,
            total_fracoes=int(b["total_fracoes"]),
            total_equipes=int(b["total_equipes"]),
            total_pms=int(b["total_pms"]),
            unidades=sorted(cast("set[str]", b["unidades"])),
        ))
    saida.sort(key=lambda x: (x["total_pms"], x["total_fracoes"]), reverse=True)
    return saida


def agregar_por_municipio(vertices: list[dict]) -> list[AgregadoMunicipio]:
    """Camada deterministica por municipio_id (fallback no raw em caixa alta)."""
    buckets: dict[tuple[str | None, str, str], dict] = defaultdict(
        lambda: {"total_fracoes": 0, "total_equipes": 0, "total_pms": 0}
    )

    for vt in vertices:
        mid_val = vt.get("municipio_id")
        mid: str | None = str(mid_val) if mid_val else None
        crpm: str = cast(str, vt.get("crpm_sigla") or "").strip()
        if mid:
            nome: str = cast(str, vt.get("municipio_nome") or "").strip()
            if not nome:
                nome = cast(str, vt.get("municipio_nome_raw") or "").strip().upper()
        else:
            nome = (
                cast(str, vt.get("municipio_nome_raw") or "")
                .strip().upper() or "SEM CATALOGO"
            )

        key: tuple[str | None, str, str] = (mid, nome, crpm)
        b = buckets[key]
        b["total_fracoes"] += 1
        b["total_equipes"] += _safe_int(vt.get("equipes"))
        b["total_pms"] += _safe_int(vt.get("pms"))

    saida: list[AgregadoMunicipio] = []
    for (mid, nome, crpm), b in buckets.items():
        saida.append(AgregadoMunicipio(
            municipio_id=mid,
            municipio_nome=nome,
            crpm_sigla=crpm,
            total_fracoes=int(b["total_fracoes"]),
            total_equipes=int(b["total_equipes"]),
            total_pms=int(b["total_pms"]),
        ))
    saida.sort(key=lambda x: (x["total_pms"], x["total_fracoes"]), reverse=True)
    return saida


def agregar_normalizado_por_missao(
    vertices: list[dict],
) -> list[AgregadoNormalizado]:
    """Camada normalizada: agrupa variantes textuais de `missao_nome_raw`
    pela chave `normalizar(...)` (NFD + upper + espaco colapsado). Usada
    para guiar a triagem: chaves com muitos `textos_agrupados` indicam
    necessidade de padronizacao no catalogo.
    """
    buckets: dict[str, dict] = defaultdict(
        lambda: {
            "textos": set(), "total_vertices": 0, "total_pms": 0,
            "catalogados": 0,
        }
    )
    for vt in vertices:
        bruto: str = _nome_raw(vt)
        chave: str = normalizar(bruto)
        if not chave:
            continue
        b = buckets[chave]
        cast("set[str]", b["textos"]).add(bruto)
        b["total_vertices"] += 1
        b["total_pms"] += _safe_int(vt.get("pms"))
        if vt.get("missao_id"):
            b["catalogados"] += 1

    saida: list[AgregadoNormalizado] = []
    for chave, b in buckets.items():
        tot: int = int(b["total_vertices"])
        cat: int = int(b["catalogados"])
        pct: float = round(100.0 * cat / tot, 1) if tot else 0.0
        saida.append(AgregadoNormalizado(
            chave_normalizada=chave,
            textos_agrupados=sorted(cast("set[str]", b["textos"])),
            total_vertices=tot,
            total_pms=int(b["total_pms"]),
            pct_catalogado=pct,
        ))
    saida.sort(key=lambda x: (x["total_vertices"], x["total_pms"]), reverse=True)
    return saida


def saude_catalogacao(vertices: list[dict]) -> SaudeCatalogacao:
    """Indicador de saude: `%` de vertices com missao_id e com municipio_id.

    Municipio e obrigatorio (regra 6.3 no preview), logo `pct_municipio` deve
    tender a 100 apos a fase 6.3 completa. `pct_missao` e o progresso da
    triagem humana.
    """
    total: int = len(vertices)
    com_m: int = sum(1 for v in vertices if v.get("missao_id"))
    com_u: int = sum(1 for v in vertices if v.get("municipio_id"))
    return SaudeCatalogacao(
        total_vertices=total,
        com_missao_id=com_m,
        com_municipio_id=com_u,
        pct_missao=round(100.0 * com_m / total, 1) if total else 0.0,
        pct_municipio=round(100.0 * com_u / total, 1) if total else 0.0,
    )
