# Ejecuta:  python tools/normalize_planta_db.py
from sqlalchemy import select
from models import SessionLocal, Empleado
from app import normalize_planta

db = SessionLocal()
changed = 0
for e in db.execute(select(Empleado)).scalars():
    target = normalize_planta(e.planta)
    if e.planta != target:
        e.planta = target
        changed += 1
db.commit()
db.close()
print(f"Plantas normalizadas: {changed}")
