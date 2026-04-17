"""
Importação em lote de arquivos .txt WhatsApp para o banco Supabase.

Uso:
    python scripts/importar_lote.py SMO_JAN_26.txt
    python scripts/importar_lote.py SMO_JAN_26.txt SMO_FEV_26.txt SMO_MAR_26.txt SMO_ABR_26.txt
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from app.services.whatsapp_parser import parse_texto_whatsapp
from app.services.supabase_service import save_fracoes, save_cabecalho


def importar_arquivo(caminho: str) -> dict:
    """Parseia um .txt e insere no banco. Retorna relatório."""
    nome = os.path.basename(caminho)
    print(f"\n{'='*60}")
    print(f"  IMPORTANDO: {nome}")
    print(f"{'='*60}")

    with open(caminho, "r", encoding="utf-8") as f:
        texto = f.read()

    print(f"  Arquivo lido: {len(texto):,} caracteres")

    resultado = parse_texto_whatsapp(texto)
    cab_list = [dict(c) for c in resultado["cabecalhos"]]
    frac_list = [dict(f) for f in resultado["fracoes"]]

    # Relatório do parse
    unidades_cab = set()
    datas_cab = set()
    for c in cab_list:
        unidades_cab.add(c.get("unidade", "?"))
        datas_cab.add(c.get("data", "?"))

    unidades_frac = set()
    datas_frac = set()
    for f in frac_list:
        unidades_frac.add(f.get("unidade", "?"))
        datas_frac.add(f.get("data", "?"))

    print(f"\n  PARSE:")
    print(f"    Cabecalhos: {len(cab_list)}")
    print(f"    Fracoes:    {len(frac_list)}")
    print(f"    Unidades:   {sorted(unidades_cab)}")
    print(f"    Datas:      {len(datas_cab)} dias")
    if resultado["avisos"]:
        print(f"    Avisos:     {len(resultado['avisos'])}")
        for av in resultado["avisos"][:10]:
            print(f"      - {av}")
        if len(resultado["avisos"]) > 10:
            print(f"      ... +{len(resultado['avisos']) - 10} avisos")

    # Resumo por unidade
    print(f"\n  RESUMO POR UNIDADE (cabecalho):")
    por_unidade = {}
    for c in cab_list:
        u = c.get("unidade", "?")
        if u not in por_unidade:
            por_unidade[u] = {"dias": set(), "efetivo_total": 0, "vtrs": 0}
        por_unidade[u]["dias"].add(c.get("data", "?"))
        por_unidade[u]["efetivo_total"] += c.get("efetivo_total", 0) or 0
        por_unidade[u]["vtrs"] += c.get("vtrs", 0) or 0

    for u in sorted(por_unidade.keys()):
        info = por_unidade[u]
        print(f"    {u}: {len(info['dias'])} dias | efetivo={info['efetivo_total']} | vtrs={info['vtrs']}")

    # Filtrar registros sem unidade ou sem data (dados orfaos)
    cab_validos = [c for c in cab_list if c.get("unidade") and c.get("data")]
    frac_validos = [f for f in frac_list if f.get("unidade") and f.get("data")]
    descartados_cab = len(cab_list) - len(cab_validos)
    descartados_frac = len(frac_list) - len(frac_validos)
    if descartados_cab or descartados_frac:
        print(f"\n  DESCARTADOS (sem unidade): {descartados_cab} cab + {descartados_frac} frac")

    # Inserir no banco
    print(f"\n  INSERINDO NO BANCO...")
    inserted_cab = save_cabecalho(cab_validos)
    inserted_frac = save_fracoes(frac_validos)
    print(f"    Cabecalhos inseridos: {inserted_cab}")
    print(f"    Fracoes inseridas:    {inserted_frac}")

    return {
        "arquivo": nome,
        "cabecalhos": len(cab_list),
        "fracoes": len(frac_list),
        "cab_inseridos": inserted_cab,
        "frac_inseridos": inserted_frac,
        "unidades": sorted(unidades_cab),
        "dias": len(datas_cab),
        "avisos": len(resultado["avisos"]),
    }


def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/importar_lote.py <arquivo1.txt> [arquivo2.txt ...]")
        sys.exit(1)

    arquivos = sys.argv[1:]
    for arq in arquivos:
        if not os.path.exists(arq):
            print(f"ERRO: arquivo nao encontrado: {arq}")
            sys.exit(1)

    app = create_app()
    with app.app_context():
        relatorios = []
        for arq in arquivos:
            try:
                rel = importar_arquivo(arq)
                relatorios.append(rel)
            except Exception as e:
                print(f"\n  ERRO ao importar {arq}: {e}")
                relatorios.append({"arquivo": arq, "erro": str(e)})

        # Resumo final
        print(f"\n{'='*60}")
        print(f"  RESUMO FINAL")
        print(f"{'='*60}")
        total_cab = 0
        total_frac = 0
        for r in relatorios:
            if "erro" in r:
                print(f"  {r['arquivo']}: ERRO — {r['erro']}")
            else:
                print(f"  {r['arquivo']}: {r['cab_inseridos']} cab + {r['frac_inseridos']} frac | {r['dias']} dias | {r['avisos']} avisos")
                total_cab += r["cab_inseridos"]
                total_frac += r["frac_inseridos"]
        print(f"\n  TOTAL: {total_cab} cabecalhos + {total_frac} fracoes inseridos")


if __name__ == "__main__":
    main()
