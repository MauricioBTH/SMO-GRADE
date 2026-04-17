"""Debug: mostra registros com unidade vazia ou dados suspeitos."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from app.services.whatsapp_parser import parse_texto_whatsapp

app = create_app()
with app.app_context():
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        texto = f.read()
    resultado = parse_texto_whatsapp(texto)

    # Cabecalhos sem unidade
    print("=== CABECALHOS SEM UNIDADE ===\n")
    for i, c in enumerate(resultado["cabecalhos"]):
        if not c.get("unidade"):
            print(f"  [{i}] data={c.get('data','')} turno={c.get('turno','')}")
            print(f"       efetivo={c.get('efetivo_total',0)} vtrs={c.get('vtrs',0)}")
            print(f"       oficial_sup={c.get('oficial_superior','')}")
            print(f"       local={c.get('locais_atuacao','')}")
            print()

    # Fracoes sem unidade
    print("=== FRACOES SEM UNIDADE ===\n")
    for i, f in enumerate(resultado["fracoes"]):
        if not f.get("unidade"):
            print(f"  [{i}] data={f.get('data','')} fracao={f.get('fracao','')}")
            print(f"       cmt={f.get('comandante','')} missao={f.get('missao','')}")
            print()

    # Fracoes sem data
    print("=== FRACOES SEM DATA ===\n")
    for i, f in enumerate(resultado["fracoes"]):
        if not f.get("data"):
            print(f"  [{i}] unidade={f.get('unidade','')} fracao={f.get('fracao','')}")
            print(f"       cmt={f.get('comandante','')} missao={f.get('missao','')}")
            print()

    # Avisos completos
    print(f"=== TODOS OS AVISOS ({len(resultado['avisos'])}) ===\n")
    for av in resultado["avisos"]:
        print(f"  - {av}")
