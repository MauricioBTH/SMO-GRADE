"""Executa ALTER TABLE para ampliar colunas que excedem limites."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from app.models.database import get_connection

ALTERS = [
    "ALTER TABLE fracoes ALTER COLUMN turno TYPE VARCHAR(100)",
    "ALTER TABLE fracoes ALTER COLUMN horario_inicio TYPE VARCHAR(50)",
    "ALTER TABLE fracoes ALTER COLUMN horario_fim TYPE VARCHAR(50)",
    "ALTER TABLE cabecalho ALTER COLUMN turno TYPE VARCHAR(100)",
]

app = create_app()
with app.app_context():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for sql in ALTERS:
                print(f"  {sql}")
                cur.execute(sql)
        conn.commit()
        print("\nAlteracoes aplicadas com sucesso.")
    except Exception as e:
        conn.rollback()
        print(f"\nERRO: {e}")
    finally:
        conn.close()
