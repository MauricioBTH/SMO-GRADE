from __future__ import annotations

from typing import cast

import psycopg2

from app.models.database import get_connection
from app.validators.xlsx_validator import CabecalhoRow, FracaoRow


def save_fracoes(fracoes: list[FracaoRow]) -> int:
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
                cur.execute(
                    """
                    INSERT INTO smo.fracoes (
                        unidade, data, turno, fracao, comandante,
                        telefone, equipes, pms, horario_inicio, horario_fim, missao
                    ) VALUES (
                        %(unidade)s, %(data)s, %(turno)s, %(fracao)s,
                        %(comandante)s, %(telefone)s, %(equipes)s, %(pms)s,
                        %(horario_inicio)s, %(horario_fim)s, %(missao)s
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
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if unidades:
                cur.execute(
                    """SELECT * FROM smo.fracoes
                       WHERE TO_DATE(data, 'DD/MM/YYYY')
                             BETWEEN TO_DATE(%s, 'DD/MM/YYYY')
                                 AND TO_DATE(%s, 'DD/MM/YYYY')
                         AND unidade = ANY(%s)
                       ORDER BY TO_DATE(data, 'DD/MM/YYYY'),
                                unidade, horario_inicio""",
                    (data_inicio, data_fim, unidades),
                )
            else:
                cur.execute(
                    """SELECT * FROM smo.fracoes
                       WHERE TO_DATE(data, 'DD/MM/YYYY')
                             BETWEEN TO_DATE(%s, 'DD/MM/YYYY')
                                 AND TO_DATE(%s, 'DD/MM/YYYY')
                       ORDER BY TO_DATE(data, 'DD/MM/YYYY'),
                                unidade, horario_inicio""",
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
