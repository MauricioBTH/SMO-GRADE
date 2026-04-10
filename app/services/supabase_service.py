import psycopg2
from app.models.database import get_connection
from app.validators.xlsx_validator import FracaoRow, CabecalhoRow


def save_fracoes(fracoes: list[FracaoRow]) -> int:
    if not fracoes:
        return 0

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            inserted = 0
            for row in fracoes:
                cur.execute(
                    """
                    INSERT INTO fracoes (
                        unidade, data, turno, fracao, tipo, comandante,
                        telefone, equipes, pms, horario_inicio, horario_fim, missao
                    ) VALUES (
                        %(unidade)s, %(data)s, %(turno)s, %(fracao)s, %(tipo)s,
                        %(comandante)s, %(telefone)s, %(equipes)s, %(pms)s,
                        %(horario_inicio)s, %(horario_fim)s, %(missao)s
                    )
                    ON CONFLICT (unidade, data, fracao, comandante)
                    DO UPDATE SET
                        turno = EXCLUDED.turno,
                        tipo = EXCLUDED.tipo,
                        telefone = EXCLUDED.telefone,
                        equipes = EXCLUDED.equipes,
                        pms = EXCLUDED.pms,
                        horario_inicio = EXCLUDED.horario_inicio,
                        horario_fim = EXCLUDED.horario_fim,
                        missao = EXCLUDED.missao
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

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            inserted = 0
            for row in cabecalho:
                cur.execute(
                    """
                    INSERT INTO cabecalho (
                        unidade, data, turno, oficial_superior, tel_oficial,
                        tel_copom, operador_diurno, tel_op_diurno, horario_op_diurno,
                        operador_noturno, tel_op_noturno, horario_op_noturno,
                        efetivo_total, oficiais, sargentos, soldados, vtrs,
                        motos, ef_motorizado, armas_ace, armas_portateis,
                        armas_longas, animais, locais_atuacao, missoes_osv
                    ) VALUES (
                        %(unidade)s, %(data)s, %(turno)s, %(oficial_superior)s,
                        %(tel_oficial)s, %(tel_copom)s, %(operador_diurno)s,
                        %(tel_op_diurno)s, %(horario_op_diurno)s, %(operador_noturno)s,
                        %(tel_op_noturno)s, %(horario_op_noturno)s,
                        %(efetivo_total)s, %(oficiais)s, %(sargentos)s, %(soldados)s,
                        %(vtrs)s, %(motos)s, %(ef_motorizado)s, %(armas_ace)s,
                        %(armas_portateis)s, %(armas_longas)s, %(animais)s,
                        %(locais_atuacao)s, %(missoes_osv)s
                    )
                    ON CONFLICT (unidade, data)
                    DO UPDATE SET
                        turno = EXCLUDED.turno,
                        oficial_superior = EXCLUDED.oficial_superior,
                        tel_oficial = EXCLUDED.tel_oficial,
                        tel_copom = EXCLUDED.tel_copom,
                        operador_diurno = EXCLUDED.operador_diurno,
                        tel_op_diurno = EXCLUDED.tel_op_diurno,
                        horario_op_diurno = EXCLUDED.horario_op_diurno,
                        operador_noturno = EXCLUDED.operador_noturno,
                        tel_op_noturno = EXCLUDED.tel_op_noturno,
                        horario_op_noturno = EXCLUDED.horario_op_noturno,
                        efetivo_total = EXCLUDED.efetivo_total,
                        oficiais = EXCLUDED.oficiais,
                        sargentos = EXCLUDED.sargentos,
                        soldados = EXCLUDED.soldados,
                        vtrs = EXCLUDED.vtrs,
                        motos = EXCLUDED.motos,
                        ef_motorizado = EXCLUDED.ef_motorizado,
                        armas_ace = EXCLUDED.armas_ace,
                        armas_portateis = EXCLUDED.armas_portateis,
                        armas_longas = EXCLUDED.armas_longas,
                        animais = EXCLUDED.animais,
                        locais_atuacao = EXCLUDED.locais_atuacao,
                        missoes_osv = EXCLUDED.missoes_osv
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
                "SELECT * FROM fracoes WHERE data = %s ORDER BY unidade, horario_inicio",
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
                "SELECT * FROM cabecalho WHERE data = %s ORDER BY unidade",
                (data,),
            )
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()
