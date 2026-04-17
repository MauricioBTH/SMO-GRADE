"""
Conferência dos dados no banco Supabase.
Mostra totais por unidade/mês e identifica gaps (dias faltantes).

Uso:
    python scripts/conferir_banco.py
    python scripts/conferir_banco.py --mes 01/2026
"""
import sys
import os
from collections import defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from app.models.database import get_connection


def conferir():
    mes_filtro = None
    if "--mes" in sys.argv:
        idx = sys.argv.index("--mes")
        if idx + 1 < len(sys.argv):
            mes_filtro = sys.argv[idx + 1]

    app = create_app()
    with app.app_context():
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                # Cabecalho: totais por unidade e mês
                cur.execute("""
                    SELECT
                        unidade,
                        data,
                        efetivo_total,
                        vtrs
                    FROM cabecalho
                    ORDER BY unidade, data
                """)
                cab_rows = cur.fetchall()

                # Fracoes: totais por unidade e mês
                cur.execute("""
                    SELECT
                        unidade,
                        data,
                        COUNT(*) as total_fracoes,
                        SUM(pms) as total_pms,
                        SUM(equipes) as total_equipes
                    FROM fracoes
                    GROUP BY unidade, data
                    ORDER BY unidade, data
                """)
                frac_rows = cur.fetchall()

        finally:
            conn.close()

        # Organizar cabecalho por unidade → mês
        cab_por_unidade = defaultdict(lambda: defaultdict(list))
        for r in cab_rows:
            u = r["unidade"]
            data_str = r["data"]
            try:
                dt = datetime.strptime(data_str, "%d/%m/%Y")
                mes_key = dt.strftime("%m/%Y")
            except ValueError:
                mes_key = "???"
            cab_por_unidade[u][mes_key].append({
                "data": data_str,
                "efetivo": r["efetivo_total"] or 0,
                "vtrs": r["vtrs"] or 0,
            })

        # Organizar frações por unidade → mês
        frac_por_unidade = defaultdict(lambda: defaultdict(list))
        for r in frac_rows:
            u = r["unidade"]
            data_str = r["data"]
            try:
                dt = datetime.strptime(data_str, "%d/%m/%Y")
                mes_key = dt.strftime("%m/%Y")
            except ValueError:
                mes_key = "???"
            frac_por_unidade[u][mes_key].append({
                "data": data_str,
                "fracoes": r["total_fracoes"],
                "pms": r["total_pms"] or 0,
            })

        # Relatório
        todas_unidades = sorted(set(list(cab_por_unidade.keys()) + list(frac_por_unidade.keys())))
        todos_meses = sorted(set(
            m for u in cab_por_unidade for m in cab_por_unidade[u]
        ))

        if mes_filtro:
            todos_meses = [m for m in todos_meses if m == mes_filtro]

        print(f"\n{'='*70}")
        print(f"  CONFERENCIA DO BANCO DE DADOS")
        print(f"{'='*70}")
        print(f"  Unidades encontradas: {len(todas_unidades)}")
        print(f"  Meses com dados:      {todos_meses}")

        for mes in todos_meses:
            print(f"\n{'-'*70}")
            print(f"  MES: {mes}")
            print(f"{'-'*70}")
            print(f"  {'UNIDADE':<20} {'DIAS CAB':>8} {'EFETIVO':>8} {'VTRS':>6} {'DIAS FRAC':>9} {'FRACOES':>8} {'PMs':>6}")
            print(f"  {'-'*20} {'-'*8} {'-'*8} {'-'*6} {'-'*9} {'-'*8} {'-'*6}")

            for u in todas_unidades:
                cabs = cab_por_unidade[u].get(mes, [])
                fracs = frac_por_unidade[u].get(mes, [])

                dias_cab = len(cabs)
                soma_efetivo = sum(c["efetivo"] for c in cabs)
                soma_vtrs = sum(c["vtrs"] for c in cabs)

                dias_frac = len(fracs)
                soma_fracoes = sum(f["fracoes"] for f in fracs)
                soma_pms = sum(f["pms"] for f in fracs)

                if dias_cab == 0 and dias_frac == 0:
                    continue

                print(f"  {u:<20} {dias_cab:>8} {soma_efetivo:>8} {soma_vtrs:>6} {dias_frac:>9} {soma_fracoes:>8} {soma_pms:>6}")

            # Detectar gaps (dias sem dados)
            print(f"\n  GAPS (dias sem cabecalho):")
            try:
                m, y = mes.split("/")
                primeiro = datetime(int(y), int(m), 1)
                if int(m) == 12:
                    ultimo = datetime(int(y) + 1, 1, 1) - timedelta(days=1)
                else:
                    ultimo = datetime(int(y), int(m) + 1, 1) - timedelta(days=1)
            except ValueError:
                continue

            for u in todas_unidades:
                cabs = cab_por_unidade[u].get(mes, [])
                datas_presentes = set()
                for c in cabs:
                    try:
                        datas_presentes.add(datetime.strptime(c["data"], "%d/%m/%Y").date())
                    except ValueError:
                        pass

                gaps = []
                dia = primeiro.date()
                while dia <= ultimo.date():
                    if dia not in datas_presentes:
                        gaps.append(dia.strftime("%d/%m"))
                    dia += timedelta(days=1)

                if gaps and len(cabs) > 0:
                    print(f"    {u}: {len(gaps)} dias faltantes — {', '.join(gaps[:15])}")
                    if len(gaps) > 15:
                        print(f"      ... +{len(gaps) - 15} dias")
                elif len(cabs) == 0:
                    print(f"    {u}: sem dados neste mes")

        # Total geral
        print(f"\n{'='*70}")
        print(f"  TOTAIS GERAIS")
        print(f"{'='*70}")
        print(f"  Cabecalhos: {len(cab_rows)}")
        print(f"  Dias com fracoes: {len(frac_rows)}")
        total_fracoes = sum(r["total_fracoes"] for r in frac_rows)
        total_pms = sum((r["total_pms"] or 0) for r in frac_rows)
        print(f"  Total fracoes: {total_fracoes}")
        print(f"  Total PMs: {total_pms}")


if __name__ == "__main__":
    conferir()
