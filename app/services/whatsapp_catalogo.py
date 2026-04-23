"""Enriquecimento de fracoes com catalogos SMO (Fase 6.3).

Responsabilidades:
  1. Resolver `missao_id` / `municipio_id` / `bpm_id` em cada vertice de
     `FracaoRow.missoes`.
  2. Manter `FracaoRow.missao_id` / `FracaoRow.municipio_id` em sincronia
     com a PRIMEIRA missao — backcompat com fluxo 1:1 ate 6.5.
  3. Emitir avisos textuais em `avisos: list[str]` para apoio ao operador
     AREI no preview (municipio sem catalogo, POA sem BPM fora de quartel).

Degradacao segura: se DB nao configurado ou falha de IO, ids ficam None e
um aviso e acrescentado. Parser continua produzindo o preview editavel.
"""
from __future__ import annotations

from app.validators.xlsx_validator import FracaoRow, MissaoVertice

# Flag CPC = sigla do CRPM de Porto Alegre (seeded em 003). Serve pra decidir
# se o municipio e POA e, portanto, exige BPM quando nao em quartel.
_SIGLA_CPC: str = "CPC"


def enriquecer_com_catalogo(
    fracoes: list[FracaoRow], avisos: list[str]
) -> None:
    """Enriquece in-place: popula ids nos vertices e sincroniza legado.

    Side effects:
      - Cada MissaoVertice ganha `missao_id`, `municipio_id`, `bpm_ids`.
      - FracaoRow ganha `missao_id`, `municipio_id` a partir da 1a missao.
      - `avisos` recebe strings descritivas para cada caso nao resolvido.
    """
    try:
        from app.services import bpm_service, catalogo_service, unidade_service
    except Exception:
        return

    # Caches locais evitam N consultas ao DB quando muitas fracoes repetem
    # o mesmo municipio/missao. Custo minimo de memoria (~500 municipios).
    try:
        municipios: list = catalogo_service.listar_municipios(
            somente_ativos=True, limite=2000,
        )
    except Exception as exc:
        avisos.append(f"Lookup de municipio falhou: {exc}")
        return
    cache_muni: dict[str, object] = _montar_cache_municipios(municipios)
    cache_muni_por_id: dict[str, object] = {str(getattr(m, "id", "")): m for m in municipios}

    try:
        bpms = bpm_service.listar_bpms()
    except Exception as exc:
        avisos.append(f"Lookup de BPM falhou: {exc}")
        return
    cache_bpm: dict[str, str] = {
        bpm_service.normalizar_codigo_bpm(b.codigo): b.id for b in bpms
    }

    # Fase 6.4.1: cache de unidades {nome_normalizado: Unidade} — serve de
    # fallback para missoes em quartel sem municipio na linha. Tolera DB
    # sem tabela (rollout parcial) — cache fica vazio e fallback e no-op.
    cache_uni: dict[str, object] = {}
    try:
        unidades = unidade_service.listar_unidades(somente_ativas=True)
        cache_uni = {u.nome_normalizado: u for u in unidades}
    except Exception as exc:
        avisos.append(f"Lookup de unidades falhou: {exc}")

    for fr in fracoes:
        missoes: list[MissaoVertice] = fr.get("missoes") or []
        unidade_raw: str = fr.get("unidade", "") or ""
        for m in missoes:
            _resolver_vertice(
                m,
                titulo_fracao=fr.get("fracao", "") or fr.get("comandante", ""),
                unidade_raw=unidade_raw,
                cache_muni=cache_muni,
                cache_muni_por_id=cache_muni_por_id,
                cache_bpm=cache_bpm,
                cache_uni=cache_uni,
                avisos=avisos,
                catalogo_service=catalogo_service,
                unidade_service=unidade_service,
            )

        if missoes:
            primeira: MissaoVertice = missoes[0]
            fr["missao_id"] = primeira.get("missao_id")
            fr["municipio_id"] = primeira.get("municipio_id")
            # municipio_nome_raw espelha a 1a missao se ainda vazio
            if not fr.get("municipio_nome_raw"):
                fr["municipio_nome_raw"] = primeira.get("municipio_nome_raw", "")


def _montar_cache_municipios(
    municipios: list,
) -> dict[str, object]:
    """{nome_normalizado: Municipio}. Necessario pra casar via match exato
    sem mil consultas individuais ao banco."""
    from app.services.catalogo_types import normalizar
    return {normalizar(m.nome): m for m in municipios}


def _resolver_vertice(
    vertice: MissaoVertice,
    titulo_fracao: str,
    unidade_raw: str,
    cache_muni: dict[str, object],
    cache_muni_por_id: dict[str, object],
    cache_bpm: dict[str, str],
    cache_uni: dict[str, object],
    avisos: list[str],
    catalogo_service: object,
    unidade_service: object,
) -> None:
    """Resolve e atribui ids em um unico vertice; acumula avisos textuais."""
    from app.services.catalogo_types import normalizar

    # Missao
    missao_txt: str = vertice.get("missao_nome_raw", "") or ""
    if missao_txt:
        try:
            achada = catalogo_service.lookup_missao_por_nome(missao_txt)  # type: ignore[attr-defined]
        except Exception as exc:
            avisos.append(f"Lookup de missao falhou: {exc}")
            achada = None
        vertice["missao_id"] = achada.id if achada else None
    else:
        vertice["missao_id"] = None

    # Municipio (obrigatorio — regra 6.3). Fase 6.4.1: fallback para
    # municipio-sede da unidade quando em_quartel e municipio nao veio no texto.
    muni_txt: str = vertice.get("municipio_nome_raw", "") or ""
    em_quartel: bool = bool(vertice.get("em_quartel", False))
    muni_obj: object | None = None
    if muni_txt:
        muni_obj = cache_muni.get(normalizar(muni_txt))
        vertice["municipio_id"] = str(getattr(muni_obj, "id", "")) or None if muni_obj else None
    else:
        vertice["municipio_id"] = None

    if muni_txt and not vertice["municipio_id"]:
        avisos.append(
            f"[{titulo_fracao or 'fracao'}] Municipio '{muni_txt}' nao "
            f"encontrado no catalogo."
        )

    if em_quartel and not vertice["municipio_id"] and unidade_raw:
        chave_uni: str = unidade_service.normalizar_codigo_unidade(unidade_raw)  # type: ignore[attr-defined]
        uni_obj = cache_uni.get(chave_uni) if chave_uni else None
        if uni_obj is not None:
            sede_id: str = str(getattr(uni_obj, "municipio_sede_id", "")) or ""
            if sede_id:
                vertice["municipio_id"] = sede_id
                vertice["municipio_nome_raw"] = getattr(
                    cache_muni_por_id.get(sede_id), "nome", ""
                ) or vertice.get("municipio_nome_raw", "")
                muni_obj = cache_muni_por_id.get(sede_id)
        else:
            avisos.append(
                f"[{titulo_fracao or 'fracao'}] Unidade '{unidade_raw}' sem "
                f"municipio-sede cadastrado — missao em quartel ficara sem municipio."
            )

    # BPM (N:N desde 6.4 — lista de raws resolvida para lista de ids).
    bpm_raws: list[str] = list(vertice.get("bpm_raws") or [])
    eh_poa: bool = bool(muni_obj) and getattr(
        muni_obj, "crpm_sigla", ""
    ).upper() == _SIGLA_CPC

    if em_quartel:
        # Missao em quartel nunca tem BPM — parser ja descarta bpm_raws.
        vertice["bpm_ids"] = []
    elif bpm_raws:
        from app.services import bpm_service
        resolvidos: list[str] = []
        vistos: set[str] = set()
        for raw in bpm_raws:
            chave: str = bpm_service.normalizar_codigo_bpm(raw)
            bpm_id: str | None = cache_bpm.get(chave) if chave else None
            if bpm_id and bpm_id not in vistos:
                vistos.add(bpm_id)
                resolvidos.append(bpm_id)
            elif not bpm_id:
                avisos.append(
                    f"[{titulo_fracao or 'fracao'}] BPM '{raw}' nao "
                    f"encontrado no catalogo."
                )
        vertice["bpm_ids"] = resolvidos
    else:
        vertice["bpm_ids"] = []
        if eh_poa and not em_quartel:
            avisos.append(
                f"[{titulo_fracao or 'fracao'}] Bloco em Porto Alegre sem BPM "
                f"detectado — operador deve selecionar no preview."
            )
