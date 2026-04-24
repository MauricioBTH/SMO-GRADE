"""Gravacao de fracoes/cabecalho versionados (Fase 6.5.b).

Extraido de db_service.py em 6.5.b pra manter cada arquivo <= 500 LOC. A
leitura (`fetch_*`) continua em `db_service.py`. Ambos compartilham a mesma
interface publica — ver `db_service.__init__` que re-exporta.
"""
from __future__ import annotations

import psycopg2
import psycopg2.extensions

from app.models.database import get_connection
from app.services import upload_service
from app.services.upload_service import OrigemUpload
from app.validators.xlsx_validator import CabecalhoRow, FracaoRow, MissaoVertice


def save_fracoes(
    fracoes: list[FracaoRow],
    *,
    usuario_id: str,
    texto_original: str | None = None,
    origem: OrigemUpload = "whatsapp",
) -> int:
    """Grava fracoes (+ vertices Fase 6.3) de forma versionada (Fase 6.5.b).

    Estrategia:
      - Para cada (unidade, data) no batch, chama upload_service para:
          (a) cancelar o upload ativo anterior (se houver) e soft-deletar
              as fracoes/cabecalho vinculadas;
          (b) criar um novo upload e retornar seu id.
      - Novas fracoes sao INSERT-adas com `upload_id` apontando para o
        upload recem-criado. A cadeia de `substitui_id` permite restaurar
        versoes anteriores pelo endpoint /api/uploads/<id>/restaurar.
      - Vertices sem municipio_id sao PULADOS (defesa — UI preview bloqueia).

    Transacional: qualquer erro em qualquer fracao faz rollback completo,
    incluindo a criacao dos uploads.
    """
    if not fracoes:
        return 0

    pares: set[tuple[str, str]] = {(r["unidade"], r["data"]) for r in fracoes}

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            upload_ids = upload_service.preparar_uploads_para_pares(
                cur,
                pares=pares,
                usuario_id=usuario_id,
                texto_original=texto_original,
                origem=origem,
            )
            inserted: int = 0
            for row in fracoes:
                payload: dict = dict(row)
                payload.setdefault("missao_id", None)
                payload.setdefault("osv", None)
                payload.setdefault("municipio_id", None)
                payload.setdefault("municipio_nome_raw", None)
                payload["upload_id"] = upload_ids[
                    (row["unidade"], row["data"])
                ]
                cur.execute(
                    """
                    INSERT INTO smo.fracoes (
                        unidade, data, turno, fracao, comandante,
                        telefone, equipes, pms, horario_inicio, horario_fim,
                        missao, missao_id, osv, municipio_id, municipio_nome_raw,
                        upload_id, atualizado_em
                    ) VALUES (
                        %(unidade)s, %(data)s, %(turno)s, %(fracao)s,
                        %(comandante)s, %(telefone)s, %(equipes)s, %(pms)s,
                        %(horario_inicio)s, %(horario_fim)s, %(missao)s,
                        %(missao_id)s, %(osv)s, %(municipio_id)s,
                        %(municipio_nome_raw)s, %(upload_id)s, NOW()
                    )
                    RETURNING id
                    """,
                    payload,
                )
                result = cur.fetchone()
                if result is None:
                    raise RuntimeError("INSERT smo.fracoes nao retornou id")
                fracao_id: str = str(result["id"])
                _inserir_vertices(cur, fracao_id, row.get("missoes") or [])
                inserted += 1
        conn.commit()
        return inserted
    except psycopg2.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def _inserir_vertices(
    cur: psycopg2.extensions.cursor,
    fracao_id: str,
    missoes: list[MissaoVertice],
) -> None:
    """Insere N vertices renumerando ordem 1..N (ignora gaps do parser).

    Pula vertices sem municipio_id — a UI do preview deve bloquear Salvar
    antes de chegar aqui, mas a defesa adicional evita integrity error se
    alguem chamar save_fracoes direto (importar_lote, testes).

    BPMs N:N vao integralmente para smo.fracao_missao_bpms (fonte de verdade).
    em_quartel=TRUE zera bpm_ids.
    """
    ordem_seq: int = 0
    for m in missoes:
        muni_id = m.get("municipio_id")
        if not muni_id:
            continue
        ordem_seq += 1
        em_quartel: bool = bool(m.get("em_quartel", False))
        bpm_ids: list[str] = [] if em_quartel else list(m.get("bpm_ids") or [])
        cur.execute(
            """
            INSERT INTO smo.fracao_missoes (
                fracao_id, ordem, missao_id, missao_nome_raw,
                municipio_id, em_quartel
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                fracao_id,
                ordem_seq,
                m.get("missao_id"),
                m.get("missao_nome_raw") or "(sem missao)",
                muni_id,
                em_quartel,
            ),
        )
        result = cur.fetchone()
        if result is None:
            raise RuntimeError("INSERT smo.fracao_missoes nao retornou id")
        fracao_missao_id: str = str(result["id"])
        for bid in bpm_ids:
            cur.execute(
                "INSERT INTO smo.fracao_missao_bpms "
                "(fracao_missao_id, bpm_id) VALUES (%s, %s) "
                "ON CONFLICT DO NOTHING",
                (fracao_missao_id, bid),
            )


def save_cabecalho(
    cabecalho: list[CabecalhoRow],
    *,
    usuario_id: str,
    texto_original: str | None = None,
    origem: OrigemUpload = "whatsapp",
) -> int:
    """Grava cabecalho de forma versionada (Fase 6.5.b).

    Reutiliza o upload ativo de cada (unidade, data) se ele ja foi criado
    no mesmo request pelo save_fracoes — evita duas versoes para o mesmo
    salvamento. Caso contrario cria um upload novo.
    """
    if not cabecalho:
        return 0

    pares: set[tuple[str, str]] = {
        (r["unidade"], r["data"]) for r in cabecalho
    }

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            upload_ids: dict[tuple[str, str], str] = {}
            pares_sem_ativo: set[tuple[str, str]] = set()
            for unidade, data in pares:
                ativo = upload_service._cur_upload_ativo(cur, unidade, data)
                if ativo is not None and ativo.usuario_id == usuario_id:
                    upload_ids[(unidade, data)] = ativo.id
                else:
                    pares_sem_ativo.add((unidade, data))
            if pares_sem_ativo:
                upload_ids.update(
                    upload_service.preparar_uploads_para_pares(
                        cur,
                        pares=pares_sem_ativo,
                        usuario_id=usuario_id,
                        texto_original=texto_original,
                        origem=origem,
                    )
                )

            inserted: int = 0
            for row in cabecalho:
                payload: dict = dict(row)
                payload["upload_id"] = upload_ids[
                    (row["unidade"], row["data"])
                ]
                cur.execute(
                    """
                    INSERT INTO smo.cabecalho (
                        unidade, data, turno, oficial_superior, tel_oficial,
                        tel_copom, operador_diurno, tel_op_diurno, horario_op_diurno,
                        operador_noturno, tel_op_noturno, horario_op_noturno,
                        efetivo_total, oficiais, sargentos, soldados, vtrs,
                        motos, ef_motorizado, armas_ace, armas_portateis,
                        armas_longas, animais, animais_tipo, locais_atuacao,
                        missoes_osv, upload_id
                    ) VALUES (
                        %(unidade)s, %(data)s, %(turno)s, %(oficial_superior)s,
                        %(tel_oficial)s, %(tel_copom)s, %(operador_diurno)s,
                        %(tel_op_diurno)s, %(horario_op_diurno)s, %(operador_noturno)s,
                        %(tel_op_noturno)s, %(horario_op_noturno)s,
                        %(efetivo_total)s, %(oficiais)s, %(sargentos)s, %(soldados)s,
                        %(vtrs)s, %(motos)s, %(ef_motorizado)s, %(armas_ace)s,
                        %(armas_portateis)s, %(armas_longas)s, %(animais)s,
                        %(animais_tipo)s, %(locais_atuacao)s, %(missoes_osv)s,
                        %(upload_id)s
                    )
                    """,
                    payload,
                )
                inserted += 1
        conn.commit()
        return inserted
    except psycopg2.Error:
        conn.rollback()
        raise
    finally:
        conn.close()
