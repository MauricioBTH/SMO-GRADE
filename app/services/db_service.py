from __future__ import annotations

from typing import cast

import psycopg2

from app.models.database import get_connection
from app.validators.xlsx_validator import CabecalhoRow, FracaoRow, MissaoVertice


def save_fracoes(fracoes: list[FracaoRow]) -> int:
    """Grava fracoes + (Fase 6.3) seus vertices em smo.fracao_missoes.

    Estrategia:
      - DELETE/INSERT idempotente em smo.fracoes por (unidade, data). O
        CASCADE em fracao_missoes limpa vertices obsoletos automaticamente.
      - Para cada fracao, re-insere N vertices em fracao_missoes.
      - Vertices sem municipio_id sao PULADOS com erro amigavel — migration
        005 marca municipio como NOT NULL no vertice (regra 6.3).

    Transacional: qualquer erro em qualquer fracao faz rollback completo.
    """
    if not fracoes:
        return 0

    pares: set[tuple[str, str]] = {(r["unidade"], r["data"]) for r in fracoes}

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for unidade, data in pares:
                cur.execute(
                    "DELETE FROM smo.fracoes WHERE unidade = %s AND data = %s",
                    (unidade, data),
                )

            inserted: int = 0
            for row in fracoes:
                payload: dict = dict(row)
                payload.setdefault("missao_id", None)
                payload.setdefault("osv", None)
                payload.setdefault("municipio_id", None)
                payload.setdefault("municipio_nome_raw", None)
                cur.execute(
                    """
                    INSERT INTO smo.fracoes (
                        unidade, data, turno, fracao, comandante,
                        telefone, equipes, pms, horario_inicio, horario_fim,
                        missao, missao_id, osv, municipio_id, municipio_nome_raw,
                        atualizado_em
                    ) VALUES (
                        %(unidade)s, %(data)s, %(turno)s, %(fracao)s,
                        %(comandante)s, %(telefone)s, %(equipes)s, %(pms)s,
                        %(horario_inicio)s, %(horario_fim)s, %(missao)s,
                        %(missao_id)s, %(osv)s, %(municipio_id)s,
                        %(municipio_nome_raw)s, NOW()
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

    Fase 6.4: N:N BPMs. O 1o BPM vai como cache em smo.fracao_missoes.bpm_id
    (DEPRECATED mas ainda lido por analytics legadas); os N BPMs vao para
    smo.fracao_missao_bpms (fonte de verdade).
    """
    ordem_seq: int = 0
    for m in missoes:
        muni_id = m.get("municipio_id")
        if not muni_id:
            continue
        ordem_seq += 1
        em_quartel: bool = bool(m.get("em_quartel", False))
        bpm_ids: list[str] = [] if em_quartel else list(m.get("bpm_ids") or [])
        cache_bpm_id: str | None = bpm_ids[0] if bpm_ids else None
        cur.execute(
            """
            INSERT INTO smo.fracao_missoes (
                fracao_id, ordem, missao_id, missao_nome_raw,
                municipio_id, bpm_id, em_quartel
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                fracao_id,
                ordem_seq,
                m.get("missao_id"),
                m.get("missao_nome_raw") or "(sem missao)",
                muni_id,
                cache_bpm_id,
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


def save_cabecalho(cabecalho: list[CabecalhoRow]) -> int:
    if not cabecalho:
        return 0

    pares: set[tuple[str, str]] = {(r["unidade"], r["data"]) for r in cabecalho}

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for unidade, data in pares:
                cur.execute(
                    "DELETE FROM smo.cabecalho WHERE unidade = %s AND data = %s",
                    (unidade, data),
                )

            inserted: int = 0
            for row in cabecalho:
                cur.execute(
                    """
                    INSERT INTO smo.cabecalho (
                        unidade, data, turno, oficial_superior, tel_oficial,
                        tel_copom, operador_diurno, tel_op_diurno, horario_op_diurno,
                        operador_noturno, tel_op_noturno, horario_op_noturno,
                        efetivo_total, oficiais, sargentos, soldados, vtrs,
                        motos, ef_motorizado, armas_ace, armas_portateis,
                        armas_longas, animais, animais_tipo, locais_atuacao, missoes_osv
                    ) VALUES (
                        %(unidade)s, %(data)s, %(turno)s, %(oficial_superior)s,
                        %(tel_oficial)s, %(tel_copom)s, %(operador_diurno)s,
                        %(tel_op_diurno)s, %(horario_op_diurno)s, %(operador_noturno)s,
                        %(tel_op_noturno)s, %(horario_op_noturno)s,
                        %(efetivo_total)s, %(oficiais)s, %(sargentos)s, %(soldados)s,
                        %(vtrs)s, %(motos)s, %(ef_motorizado)s, %(armas_ace)s,
                        %(armas_portateis)s, %(armas_longas)s, %(animais)s,
                        %(animais_tipo)s, %(locais_atuacao)s, %(missoes_osv)s
                    )
                    """,
                    dict(row),
                )
                inserted += 1
        conn.commit()
        return inserted
    except psycopg2.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_fracoes_by_date(data: str) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM smo.fracoes WHERE data = %s "
                "ORDER BY unidade, horario_inicio",
                (data,),
            )
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_cabecalho_by_date(data: str) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM smo.cabecalho WHERE data = %s ORDER BY unidade",
                (data,),
            )
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_fracoes_by_range(
    data_inicio: str, data_fim: str, unidades: list[str]
) -> list[dict]:
    """Retorna fracoes no periodo, enriquecidas com missao_nome/municipio_nome
    a partir dos catalogos (via LEFT JOIN), mantendo a coluna textual `missao`
    para compatibilidade."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            base_select: str = """
                SELECT f.*,
                       mi.nome AS missao_nome,
                       mu.nome AS municipio_nome,
                       cr.sigla AS crpm_sigla
                FROM smo.fracoes f
                LEFT JOIN smo.missoes mi    ON mi.id = f.missao_id
                LEFT JOIN smo.municipios mu ON mu.id = f.municipio_id
                LEFT JOIN smo.crpms cr      ON cr.id = mu.crpm_id
            """
            if unidades:
                cur.execute(
                    base_select + """
                       WHERE TO_DATE(f.data, 'DD/MM/YYYY')
                             BETWEEN TO_DATE(%s, 'DD/MM/YYYY')
                                 AND TO_DATE(%s, 'DD/MM/YYYY')
                         AND f.unidade = ANY(%s)
                       ORDER BY TO_DATE(f.data, 'DD/MM/YYYY'),
                                f.unidade, f.horario_inicio""",
                    (data_inicio, data_fim, unidades),
                )
            else:
                cur.execute(
                    base_select + """
                       WHERE TO_DATE(f.data, 'DD/MM/YYYY')
                             BETWEEN TO_DATE(%s, 'DD/MM/YYYY')
                                 AND TO_DATE(%s, 'DD/MM/YYYY')
                       ORDER BY TO_DATE(f.data, 'DD/MM/YYYY'),
                                f.unidade, f.horario_inicio""",
                    (data_inicio, data_fim),
                )
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_vertices_by_range(
    data_inicio: str, data_fim: str, unidades: list[str]
) -> list[dict]:
    """Retorna vertices (smo.fracao_missoes) no periodo, enriquecidos com
    fracao (unidade/data/equipes/pms/horario_inicio) + joins de catalogo
    (missao_nome, municipio_nome, crpm_sigla, bpm_codigos[]).

    Alimenta analytics 6.3/6.4: 3 camadas + saude catalogacao. Desde 6.4,
    `bpm_codigos` e uma lista (N:N via smo.fracao_missao_bpms). O campo
    singular `bpm_codigo` e mantido como cache do 1o BPM para analytics
    legadas (DEPRECATED, remocao em 6.5).
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            base_select: str = """
                SELECT
                    fm.id AS fracao_missao_id,
                    fm.fracao_id, fm.ordem, fm.missao_id, fm.missao_nome_raw,
                    fm.municipio_id, fm.bpm_id, fm.em_quartel,
                    f.unidade, f.data, f.turno, f.fracao, f.equipes, f.pms,
                    f.horario_inicio, f.horario_fim,
                    mi.nome AS missao_nome,
                    mu.nome AS municipio_nome,
                    mu.nome AS municipio_nome_raw,
                    cr.sigla AS crpm_sigla,
                    bp.codigo AS bpm_codigo,
                    COALESCE(bpms_nn.codigos, ARRAY[]::text[]) AS bpm_codigos
                FROM smo.fracao_missoes fm
                JOIN smo.fracoes f         ON f.id = fm.fracao_id
                LEFT JOIN smo.missoes mi    ON mi.id = fm.missao_id
                LEFT JOIN smo.municipios mu ON mu.id = fm.municipio_id
                LEFT JOIN smo.crpms cr      ON cr.id = mu.crpm_id
                LEFT JOIN smo.bpms bp       ON bp.id = fm.bpm_id
                LEFT JOIN LATERAL (
                    SELECT ARRAY_AGG(b2.codigo ORDER BY b2.numero) AS codigos
                      FROM smo.fracao_missao_bpms fmb
                      JOIN smo.bpms b2 ON b2.id = fmb.bpm_id
                     WHERE fmb.fracao_missao_id = fm.id
                ) bpms_nn ON TRUE
            """
            if unidades:
                cur.execute(
                    base_select + """
                       WHERE TO_DATE(f.data, 'DD/MM/YYYY')
                             BETWEEN TO_DATE(%s, 'DD/MM/YYYY')
                                 AND TO_DATE(%s, 'DD/MM/YYYY')
                         AND f.unidade = ANY(%s)
                       ORDER BY TO_DATE(f.data, 'DD/MM/YYYY'),
                                f.unidade, f.horario_inicio, fm.ordem""",
                    (data_inicio, data_fim, unidades),
                )
            else:
                cur.execute(
                    base_select + """
                       WHERE TO_DATE(f.data, 'DD/MM/YYYY')
                             BETWEEN TO_DATE(%s, 'DD/MM/YYYY')
                                 AND TO_DATE(%s, 'DD/MM/YYYY')
                       ORDER BY TO_DATE(f.data, 'DD/MM/YYYY'),
                                f.unidade, f.horario_inicio, fm.ordem""",
                    (data_inicio, data_fim),
                )
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_cabecalho_by_range(
    data_inicio: str, data_fim: str, unidades: list[str]
) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if unidades:
                cur.execute(
                    """SELECT * FROM smo.cabecalho
                       WHERE TO_DATE(data, 'DD/MM/YYYY')
                             BETWEEN TO_DATE(%s, 'DD/MM/YYYY')
                                 AND TO_DATE(%s, 'DD/MM/YYYY')
                         AND unidade = ANY(%s)
                       ORDER BY TO_DATE(data, 'DD/MM/YYYY'), unidade""",
                    (data_inicio, data_fim, unidades),
                )
            else:
                cur.execute(
                    """SELECT * FROM smo.cabecalho
                       WHERE TO_DATE(data, 'DD/MM/YYYY')
                             BETWEEN TO_DATE(%s, 'DD/MM/YYYY')
                                 AND TO_DATE(%s, 'DD/MM/YYYY')
                       ORDER BY TO_DATE(data, 'DD/MM/YYYY'), unidade""",
                    (data_inicio, data_fim),
                )
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_datas_disponiveis() -> list[str]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT data, TO_DATE(data, 'DD/MM/YYYY') AS dt "
                "FROM smo.fracoes ORDER BY dt DESC"
            )
            return [cast(str, row["data"]) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_unidades_disponiveis() -> list[str]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT unidade FROM smo.fracoes ORDER BY unidade"
            )
            return [cast(str, row["unidade"]) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_resumo_por_unidade(
    data_inicio: str, data_fim: str, unidades: list[str]
) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if unidades:
                cur.execute(
                    """SELECT
                         unidade,
                         COUNT(DISTINCT data) AS total_dias,
                         SUM(efetivo_total) AS soma_efetivo,
                         SUM(oficiais) AS soma_oficiais,
                         SUM(sargentos) AS soma_sargentos,
                         SUM(soldados) AS soma_soldados,
                         SUM(vtrs) AS soma_vtrs,
                         SUM(motos) AS soma_motos,
                         SUM(armas_ace) AS soma_armas_ace,
                         SUM(armas_portateis) AS soma_armas_portateis,
                         SUM(armas_longas) AS soma_armas_longas,
                         SUM(animais) AS soma_animais
                       FROM smo.cabecalho
                       WHERE TO_DATE(data, 'DD/MM/YYYY')
                             BETWEEN TO_DATE(%s, 'DD/MM/YYYY')
                                 AND TO_DATE(%s, 'DD/MM/YYYY')
                         AND unidade = ANY(%s)
                       GROUP BY unidade
                       ORDER BY unidade""",
                    (data_inicio, data_fim, unidades),
                )
            else:
                cur.execute(
                    """SELECT
                         unidade,
                         COUNT(DISTINCT data) AS total_dias,
                         SUM(efetivo_total) AS soma_efetivo,
                         SUM(oficiais) AS soma_oficiais,
                         SUM(sargentos) AS soma_sargentos,
                         SUM(soldados) AS soma_soldados,
                         SUM(vtrs) AS soma_vtrs,
                         SUM(motos) AS soma_motos,
                         SUM(armas_ace) AS soma_armas_ace,
                         SUM(armas_portateis) AS soma_armas_portateis,
                         SUM(armas_longas) AS soma_armas_longas,
                         SUM(animais) AS soma_animais
                       FROM smo.cabecalho
                       WHERE TO_DATE(data, 'DD/MM/YYYY')
                             BETWEEN TO_DATE(%s, 'DD/MM/YYYY')
                                 AND TO_DATE(%s, 'DD/MM/YYYY')
                       GROUP BY unidade
                       ORDER BY unidade""",
                    (data_inicio, data_fim),
                )
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_serie_temporal(
    data_inicio: str, data_fim: str, unidades: list[str]
) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if unidades:
                cur.execute(
                    """SELECT
                         data, unidade,
                         efetivo_total, oficiais, sargentos, soldados,
                         vtrs, motos, armas_ace, armas_portateis,
                         armas_longas, animais
                       FROM smo.cabecalho
                       WHERE TO_DATE(data, 'DD/MM/YYYY')
                             BETWEEN TO_DATE(%s, 'DD/MM/YYYY')
                                 AND TO_DATE(%s, 'DD/MM/YYYY')
                         AND unidade = ANY(%s)
                       ORDER BY TO_DATE(data, 'DD/MM/YYYY'), unidade""",
                    (data_inicio, data_fim, unidades),
                )
            else:
                cur.execute(
                    """SELECT
                         data, unidade,
                         efetivo_total, oficiais, sargentos, soldados,
                         vtrs, motos, armas_ace, armas_portateis,
                         armas_longas, animais
                       FROM smo.cabecalho
                       WHERE TO_DATE(data, 'DD/MM/YYYY')
                             BETWEEN TO_DATE(%s, 'DD/MM/YYYY')
                                 AND TO_DATE(%s, 'DD/MM/YYYY')
                       ORDER BY TO_DATE(data, 'DD/MM/YYYY'), unidade""",
                    (data_inicio, data_fim),
                )
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()
