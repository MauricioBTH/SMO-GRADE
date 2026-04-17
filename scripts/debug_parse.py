"""Debug: mostra campos que excedem limites do banco."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from app.services.whatsapp_parser import parse_texto_whatsapp

LIMITES = {
    "unidade": 50, "data": 30, "turno": 30, "fracao": 100,
    "comandante": 120, "telefone": 30, "horario_inicio": 20,
    "horario_fim": 20, "missao": None, "oficial_superior": 120,
    "tel_oficial": 80, "tel_copom": 80, "operador_diurno": 120,
    "tel_op_diurno": 80, "horario_op_diurno": 50, "operador_noturno": 120,
    "tel_op_noturno": 80, "horario_op_noturno": 50, "animais_tipo": 50,
    "locais_atuacao": None, "missoes_osv": None,
}

app = create_app()
with app.app_context():
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        texto = f.read()
    resultado = parse_texto_whatsapp(texto)

    print("=== CAMPOS QUE EXCEDEM LIMITE ===\n")
    for tipo, registros in [("cabecalho", resultado["cabecalhos"]), ("fracao", resultado["fracoes"])]:
        for i, r in enumerate(registros):
            for campo, limite in LIMITES.items():
                if limite is None:
                    continue
                val = r.get(campo, "")
                if val and len(str(val)) > limite:
                    print(f"  {tipo}[{i}] {campo}: {len(str(val))} chars (limite {limite})")
                    print(f"    valor: {str(val)[:200]}")
                    print(f"    unidade={r.get('unidade','')} data={r.get('data','')}")
                    print()
