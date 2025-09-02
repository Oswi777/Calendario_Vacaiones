from models import init_db, SessionLocal, Empleado, Vacacion
from datetime import date, timedelta
init_db()
db = SessionLocal()
e = Empleado(numero_emp="119397", nombre="Valdez Vazquez, Jorge Andres", planta="Planta 1", turno="T1")
db.add(e); db.commit()
v = Vacacion(empleado_id=e.id, fecha_inicial=date.today(), fecha_final=date.today()+timedelta(days=2), tipo="Gozo de Vacaciones")
db.add(v); db.commit()
print("seed listo")
