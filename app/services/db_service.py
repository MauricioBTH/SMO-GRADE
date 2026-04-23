"""Leitura de fracoes/cabecalho (views *_atuais). Fase 6.5.b.

A gravacao versionada mora em `db_service_save.py` — os re-exports abaixo
preservam a interface publica `from app.services.db_service import save_*`
usada por `routes/api.py` e `scripts/importar_lote.py`.
"""
from __future__ import annotations

from typing import cast

from app.models.database import get_connection
from app.services.db_service_save import (  # noqa: F401  (backwards compat)
    save_cabecalho,
    save_fracoes,
)


def fetch_fracoes_by_date(data: str) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM smo.fracoes_atuais WHERE data = %s "
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
                "SELECT * FROM smo.cabecalho_atuais WHERE data = %s ORDER BY unidade",
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
                FROM smo.fracoes_atuais f
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
                JOIN smo.fracoes_atuais f  ON f.id = fm.fracao_id
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
                    """SELECT * FROM smo.cabecalho_atuais
                       WHERE TO_DATE(data, 'DD/MM/YYYY')
                             BETWEEN TO_DATE(%s, 'DD/MM/YYYY')
                                 AND TO_DATE(%s, 'DD/MM/YYYY')
                         AND unidade = ANY(%s)
                       ORDER BY TO_DATE(data, 'DD/MM/YYYY'), unidade""",
                    (data_inicio, data_fim, unidades),
                )
            else:
                cur.execute(
                    """SELECT * FROM smo.cabecalho_atuais
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
                "FROM smo.fracoes_atuais ORDER BY dt DESC"
            )
            return [cast(str, row["data"]) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_unidades_disponiveis() -> list[str]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT unidade FROM smo.fracoes_atuais ORDER BY unidade"
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
                       FROM smo.cabecalho_atuais
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
                       FROM smo.cabecalho_atuais
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
                       FROM smo.cabecalho_atuais
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
                       FROM smo.cabecalho_atuais
                       WHERE TO_DATE(data, 'DD/MM/YYYY')
                             BETWEEN TO_DATE(%s, 'DD/MM/YYYY')
                                 AND TO_DATE(%s, 'DD/MM/YYYY')
                       ORDER BY TO_DATE(data, 'DD/MM/YYYY'), unidade""",
                    (data_inicio, data_fim),
                )
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()
