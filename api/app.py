import os, datetime, io, traceback
from datetime import date, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from sqlalchemy import select, and_
from sqlalchemy.exc import IntegrityError
import pandas as pd
import random

from models import SessionLocal, init_db, Empleado, Vacacion

load_dotenv()
init_db()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ---------- Util ----------
def parse_date(s:str)->date:
    if not s: return None
    s = str(s)
    if "T" in s:
        return datetime.date.fromisoformat(s[:10])
    return datetime.date.fromisoformat(s)

def json_error(msg, code=500):
    return jsonify({"ok": False, "error": msg}), code

# ---------- Error handler global ----------
@app.errorhandler(Exception)
def on_exception(e):
    traceback.print_exc()
    return json_error(f"Server error: {type(e).__name__}: {e}", 500)

# ---------- Health ----------
@app.get("/api/health")
def health():
    return {"ok": True, "engine": os.getenv("DATABASE_URL", "sqlite")}

# ---------- Calendario ----------
@app.get("/api/calendario")
def calendario():
    qstart = request.args.get("start")
    qend = request.args.get("end")
    planta = request.args.get("planta")
    q = request.args.get("q")

    start = parse_date(qstart) if qstart else date.today()
    end = parse_date(qend) if qend else (start + timedelta(days=13))

    db = SessionLocal()
    from sqlalchemy import or_
    stmt = select(Vacacion).join(Empleado).where(
        and_(Vacacion.fecha_inicial <= end, Vacacion.fecha_final >= start,
             Empleado.activo == True)
    )
    if planta:
        stmt = stmt.where(Empleado.planta == planta)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Empleado.nombre.ilike(like),
                              Empleado.numero_emp.ilike(like)))

    items = []
    for v in db.execute(stmt).scalars():
        e = v.empleado
        items.append({
            "id": v.id,
            "rango": {"ini": v.fecha_inicial.isoformat(), "fin": v.fecha_final.isoformat()},
            "tipo": v.tipo, "gozo": float(v.gozo) if v.gozo is not None else None,
            "empleado": {
                "id": e.id, "numero": e.numero_emp, "nombre": e.nombre,
                "nombre_corto": e.nombre_corto or e.nombre.split(",")[0],
                "planta": e.planta, "turno": e.turno, "area": e.area,
                "foto_url": e.foto_url or "/avatar.png"
            }
        })
    db.close()
    return jsonify({"ok": True, "start": start.isoformat(), "end": end.isoformat(), "items": items})

# ---------- Empleados ----------
@app.get("/api/empleados/find")
def empleados_find():
    """Buscar por numero_emp"""
    numero = request.args.get("numero")
    if not numero:
        return json_error("Parametro 'numero' requerido", 400)
    db = SessionLocal()
    e = db.execute(select(Empleado).where(Empleado.numero_emp == numero)).scalar_one_or_none()
    db.close()
    if not e:
        return jsonify({"ok": True, "found": False})
    return jsonify({"ok": True, "found": True, "empleado": {
        "id": e.id, "numero_emp": e.numero_emp, "nombre": e.nombre,
        "planta": e.planta, "turno": e.turno, "activo": e.activo
    }})

@app.post("/api/empleados")
def alta_empleado():
    """Upsert por numero_emp: si ya existe, lo regresa; si no, lo crea."""
    data = request.get_json() or {}
    if not data.get("numero_emp") or not data.get("nombre"):
        return json_error("numero_emp y nombre son requeridos", 400)

    db = SessionLocal()
    e = db.execute(select(Empleado).where(Empleado.numero_emp == data["numero_emp"])).scalar_one_or_none()
    if e:
        # actualizar campos no nulos que vengan
        e.nombre = data.get("nombre", e.nombre)
        e.nombre_corto = data.get("nombre_corto", e.nombre_corto)
        e.area = data.get("area", e.area)
        e.turno = data.get("turno", e.turno)
        e.planta = data.get("planta", e.planta)
        e.foto_url = data.get("foto_url", e.foto_url)
        db.commit()
        emp_id = e.id
    else:
        e = Empleado(
            numero_emp=data["numero_emp"],
            nombre=data["nombre"],
            nombre_corto=data.get("nombre_corto"),
            area=data.get("area"),
            turno=data.get("turno"),
            planta=data.get("planta"),
            foto_url=data.get("foto_url"),
            activo=True
        )
        db.add(e)
        db.commit()
        emp_id = e.id

    db.close()
    return jsonify({"ok": True, "id": emp_id})

# ---------- Vacaciones ----------
@app.post("/api/vacaciones")
def alta_vacacion():
    d = request.get_json() or {}
    required = ["empleado_id","fecha_inicial","fecha_final"]
    for r in required:
        if r not in d or not d[r]:
            return json_error(f"Campo requerido: {r}", 400)

    db = SessionLocal()
    v = Vacacion(
        empleado_id=d["empleado_id"],
        fecha_inicial=parse_date(d["fecha_inicial"]),
        fecha_final=parse_date(d["fecha_final"]),
        tipo=d.get("tipo","Gozo de Vacaciones"),
        gozo=d.get("gozo"),
        fuente=d.get("fuente","manual")
    )
    db.add(v); db.commit()
    vid = v.id
    db.close()
    return jsonify({"ok": True, "id": vid})

# ---------- Importar Excel/CSV (solo columnas clave; ignora extras) ----------
@app.post("/api/importar/excel")
def importar_excel():
    """
    Lee ÚNICAMENTE:
      Inicial, Final, #, Nombre, Gozo (opcional), Planta (opcional)
    Ignora columnas extra. Tipo = 'Gozo de Vacaciones'. Turno se asigna aleatorio si no existe empleado.
    """
    f = request.files.get("file")
    if not f:
        return json_error("No file", 400)

    ext = os.path.splitext(f.filename)[1].lower()
    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(f, engine="openpyxl")
    else:
        data = f.read()
        df = pd.read_csv(io.BytesIO(data))

    def norm(s):
        return (str(s).strip().lower()
                .replace("á","a").replace("é","e").replace("í","i")
                .replace("ó","o").replace("ú","u").replace("ü","u"))

    colmap = { norm(c): c for c in df.columns }
    wants = {
        "inicial": ["inicial","inicio","fecha inicial","start","startdate"],
        "final":   ["final","fin","fecha final","end","enddate"],
        "numero":  ["#","num","numero","no","id","employee id","empleado"],
        "nombre":  ["nombre","name","empleado nombre"],
        "gozo":    ["gozo","dias","dias gozo","days"],
        "planta":  ["planta","plant","site","sede"]
    }

    def find_col(keys):
        for k in keys:
            k2 = norm(k)
            if k2 in colmap: return colmap[k2]
        for nk, orig in colmap.items():
            for k in keys:
                if nk.startswith(norm(k)): return orig
        return None

    c_inicial = find_col(wants["inicial"])
    c_final   = find_col(wants["final"])
    c_num     = find_col(wants["numero"])
    c_nombre  = find_col(wants["nombre"])
    c_gozo    = find_col(wants["gozo"])
    c_planta  = find_col(wants["planta"])

    missing = [lbl for lbl,col in [("Inicial",c_inicial),("Final",c_final),("#",c_num),("Nombre",c_nombre)] if col is None]
    if missing:
        return json_error(f"Columnas requeridas faltantes: {', '.join(missing)}", 400)

    db = SessionLocal()
    creados_empleados = 0
    creadas_vac = 0
    rechazadas = 0

    for _, row in df.iterrows():
        try:
            ini = parse_date(str(row[c_inicial]))
            fin = parse_date(str(row[c_final]))
            if not ini or not fin or ini > fin:
                rechazadas += 1
                continue

            numero = str(row[c_num]).strip()
            nombre = str(row[c_nombre]).strip()

            gozo = None
            if c_gozo and pd.notna(row[c_gozo]):
                try: gozo = float(row[c_gozo])
                except: gozo = None

            planta = None
            if c_planta and pd.notna(row[c_planta]):
                planta = str(row[c_planta]).strip() or None
            if not planta:
                planta = random.choice(["Planta 1","Planta 3"])

            e = db.execute(select(Empleado).where(Empleado.numero_emp == numero)).scalar_one_or_none()
            if not e:
                e = Empleado(
                    numero_emp=numero, nombre=nombre, planta=planta,
                    turno=random.choice(["T1","T2","T3"]), activo=True
                )
                db.add(e); db.flush()
                creados_empleados += 1
            else:
                if planta and planta != e.planta:
                    e.planta = planta

            v = Vacacion(
                empleado_id=e.id,
                fecha_inicial=ini,
                fecha_final=fin,
                tipo="Gozo de Vacaciones",
                gozo=gozo,
                fuente="excel"
            )
            db.add(v); creadas_vac += 1
        except Exception:
            traceback.print_exc()
            rechazadas += 1

    db.commit(); db.close()
    return jsonify({"ok": True, "empleados_creados": creados_empleados, "vacaciones_creadas": creadas_vac, "rechazadas": rechazadas})


if __name__ == "__main__":
    # Opcional: leer puerto de ENV, por defecto 5000
    import os
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
