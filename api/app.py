import os, datetime, io, traceback
from datetime import date, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from sqlalchemy import select, and_, or_
import pandas as pd
import random

from models import SessionLocal, init_db, Empleado, Vacacion

# -------- Config --------
MAX_CAL_DAYS = int(os.getenv("MAX_CAL_DAYS", "90"))
MAX_IMPORT_ROWS = int(os.getenv("MAX_IMPORT_ROWS", "5000"))
ALLOWED_IMPORT_EXT = {".xlsx", ".xls", ".csv"}
APP_VERSION = os.getenv("APP_VERSION", "1.1.0-admin-edit")

load_dotenv()
init_db()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ---------- Utils ----------
def parse_date(s: str):
    if not s:
        return None
    s = str(s).strip()
    if "T" in s:
        return datetime.date.fromisoformat(s[:10])
    return datetime.date.fromisoformat(s)

def json_ok(**data):
    out = {"ok": True}
    out.update(data)
    return jsonify(out)

def json_error(msg, code=400):
    return jsonify({"ok": False, "error": msg}), code

def normalize_planta(val: str) -> str:
    if not val: return "Planta 1"
    s = str(val).strip().lower()
    for tok in ["planta", "plant", "pl", "p", "#", " "]:
        s = s.replace(tok, "")
    s = s.strip().strip(".")
    if s in ("1","01","uno"): return "Planta 1"
    if s in ("3","03","tres"): return "Planta 3"
    return "Planta 1"

def clamp_cal_range(start: date, end: date):
    return (end - start).days <= MAX_CAL_DAYS

# ---------- Error handler global ----------
@app.errorhandler(Exception)
def on_exception(e):
    traceback.print_exc()
    return json_error(f"Server error: {type(e).__name__}: {e}", 500)

# ---------- Meta ----------
@app.get("/api/health")
def health():
    return json_ok(engine=os.getenv("DATABASE_URL", "sqlite"), version=APP_VERSION)

@app.get("/api/version")
def version():
    return json_ok(version=APP_VERSION)

# ---------- Calendario (para tablero) ----------
@app.get("/api/calendario")
def calendario():
    qstart = request.args.get("start")
    qend = request.args.get("end")
    planta = request.args.get("planta")
    q = (request.args.get("q") or "").strip()

    start = parse_date(qstart) if qstart else date.today()
    end = parse_date(qend) if qend else (start + timedelta(days=13))

    if not start or not end:
        return json_error("Parámetros de fecha inválidos: start/end", 400)
    if end < start:
        return json_error("end no puede ser menor que start", 400)
    if not clamp_cal_range(start, end):
        return json_error(f"Rango de calendario demasiado grande (máx {MAX_CAL_DAYS} días)", 400)

    db = SessionLocal()
    stmt = select(Vacacion).join(Empleado).where(
        and_(Vacacion.fecha_inicial <= end,
             Vacacion.fecha_final >= start,
             Empleado.activo == True)
    )
    if planta:
        stmt = stmt.where(Empleado.planta == normalize_planta(planta))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Empleado.nombre.ilike(like), Empleado.numero_emp.ilike(like)))

    items = []
    for v in db.execute(stmt).scalars():
        e = v.empleado
        items.append({
            "id": v.id,
            "rango": {"ini": v.fecha_inicial.isoformat(), "fin": v.fecha_final.isoformat()},
            "tipo": v.tipo,
            "gozo": float(v.gozo) if v.gozo is not None else None,
            "empleado": {
                "id": e.id,
                "numero": e.numero_emp,
                "nombre": e.nombre,
                "nombre_corto": e.nombre_corto or e.nombre.split(",")[0],
                "planta": e.planta,
                "turno": e.turno,
                "area": e.area,
                "foto_url": e.foto_url or "/avatar.png",
            },
        })
    db.close()
    return json_ok(start=start.isoformat(), end=end.isoformat(), items=items)

# ---------- Empleados (CRUD) ----------
@app.get("/api/empleados")
def empleados_list():
    """Listado con filtros y paginación simple."""
    q = (request.args.get("q") or "").strip()
    planta = request.args.get("planta")
    turno = request.args.get("turno")
    page = int(request.args.get("page", "1"))
    size = int(request.args.get("size", "20"))
    page = max(1, page); size = max(1, min(size, 100))

    db = SessionLocal()
    stmt = select(Empleado).where(Empleado.activo == True)
    if planta:
        stmt = stmt.where(Empleado.planta == normalize_planta(planta))
    if turno:
        stmt = stmt.where(Empleado.turno == turno)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Empleado.nombre.ilike(like),
                              Empleado.numero_emp.ilike(like)))

    total = len(db.execute(stmt).scalars().all())
    stmt = stmt.offset((page-1)*size).limit(size)
    rows = []
    for e in db.execute(stmt).scalars():
        rows.append({
            "id": e.id, "numero_emp": e.numero_emp, "nombre": e.nombre,
            "nombre_corto": e.nombre_corto, "planta": e.planta,
            "turno": e.turno, "area": e.area, "foto_url": e.foto_url, "activo": e.activo
        })
    db.close()
    return json_ok(items=rows, page=page, size=size, total=total)

@app.put("/api/empleados/<int:emp_id>")
def empleados_update(emp_id):
    data = request.get_json() or {}
    db = SessionLocal()
    e = db.get(Empleado, emp_id)
    if not e:
        db.close(); return json_error("Empleado no encontrado", 404)

    if "numero_emp" in data and data["numero_emp"]:
        e.numero_emp = str(data["numero_emp"]).strip()
    if "nombre" in data and data["nombre"]:
        e.nombre = data["nombre"]
    if "nombre_corto" in data:
        e.nombre_corto = data["nombre_corto"]
    if "planta" in data and data["planta"]:
        e.planta = normalize_planta(data["planta"])
    if "turno" in data:
        e.turno = data["turno"] or None
    if "area" in data:
        e.area = data["area"] or None
    if "foto_url" in data:
        e.foto_url = data["foto_url"] or None
    if "activo" in data:
        e.activo = bool(data["activo"])

    db.commit(); db.close()
    return json_ok(updated=True)

@app.delete("/api/empleados/<int:emp_id>")
def empleados_delete(emp_id):
    db = SessionLocal()
    e = db.get(Empleado, emp_id)
    if not e:
        db.close(); return json_error("Empleado no encontrado", 404)
    # Soft-delete: activo=False (para no romper FKs)
    e.activo = False
    db.commit(); db.close()
    return json_ok(deleted=True)

# ---------- Vacaciones (CRUD) ----------
@app.get("/api/vacaciones")
def vacaciones_list():
    """Lista vacaciones por rango (requerido) con filtros y paginación."""
    qstart = request.args.get("start")
    qend = request.args.get("end")
    planta = request.args.get("planta")
    q = (request.args.get("q") or "").strip()
    page = int(request.args.get("page", "1"))
    size = int(request.args.get("size", "20"))
    page = max(1, page); size = max(1, min(size, 100))

    start = parse_date(qstart) if qstart else None
    end = parse_date(qend) if qend else None
    if not start or not end:
        return json_error("start y end son requeridos", 400)

    db = SessionLocal()
    stmt = select(Vacacion).join(Empleado).where(
        and_(Vacacion.fecha_inicial <= end,
             Vacacion.fecha_final >= start,
             Empleado.activo == True)
    )
    if planta:
        stmt = stmt.where(Empleado.planta == normalize_planta(planta))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Empleado.nombre.ilike(like), Empleado.numero_emp.ilike(like)))

    total = len(db.execute(stmt).scalars().all())
    stmt = stmt.offset((page-1)*size).limit(size)
    rows = []
    for v in db.execute(stmt).scalars():
        e = v.empleado
        rows.append({
            "id": v.id,
            "empleado_id": e.id,
            "numero_emp": e.numero_emp,
            "nombre": e.nombre,
            "planta": e.planta,
            "turno": e.turno,
            "fecha_inicial": v.fecha_inicial.isoformat(),
            "fecha_final": v.fecha_final.isoformat(),
            "tipo": v.tipo,
            "gozo": float(v.gozo) if v.gozo is not None else None,
            "fuente": v.fuente
        })
    db.close()
    return json_ok(items=rows, page=page, size=size, total=total)

@app.put("/api/vacaciones/<int:vac_id>")
def vacaciones_update(vac_id):
    d = request.get_json() or {}
    db = SessionLocal()
    v = db.get(Vacacion, vac_id)
    if not v:
        db.close(); return json_error("Vacación no encontrada", 404)

    if "empleado_id" in d and d["empleado_id"]:
        v.empleado_id = int(d["empleado_id"])
    if "fecha_inicial" in d and d["fecha_inicial"]:
        fi = parse_date(d["fecha_inicial"]); 
        if not fi: db.close(); return json_error("fecha_inicial inválida", 400)
        v.fecha_inicial = fi
    if "fecha_final" in d and d["fecha_final"]:
        ff = parse_date(d["fecha_final"]); 
        if not ff: db.close(); return json_error("fecha_final inválida", 400)
        v.fecha_final = ff
    if v.fecha_final < v.fecha_inicial:
        db.close(); return json_error("fecha_final no puede ser menor que fecha_inicial", 400)
    if "tipo" in d and d["tipo"]:
        v.tipo = d["tipo"]
    if "gozo" in d:
        v.gozo = d["gozo"]
    if "fuente" in d:
        v.fuente = d["fuente"]

    db.commit(); db.close()
    return json_ok(updated=True)

@app.delete("/api/vacaciones/<int:vac_id>")
def vacaciones_delete(vac_id):
    db = SessionLocal()
    v = db.get(Vacacion, vac_id)
    if not v:
        db.close(); return json_error("Vacación no encontrada", 404)
    db.delete(v)
    db.commit(); db.close()
    return json_ok(deleted=True)


# ---------- Empleados: upsert por numero_emp ----------
@app.post("/api/empleados")
def alta_empleado():
    data = request.get_json() or {}
    if not data.get("numero_emp") or not data.get("nombre"):
        return json_error("numero_emp y nombre son requeridos", 400)

    # normaliza planta si viene
    if data.get("planta") is not None:
        data["planta"] = normalize_planta(data["planta"])

    db = SessionLocal()
    try:
        e = db.execute(select(Empleado).where(Empleado.numero_emp == data["numero_emp"])).scalar_one_or_none()
        if e:
            # update
            e.nombre = data.get("nombre", e.nombre)
            e.nombre_corto = data.get("nombre_corto", e.nombre_corto)
            e.area = data.get("area", e.area)
            e.turno = data.get("turno", e.turno)
            e.planta = data.get("planta", e.planta)
            e.foto_url = data.get("foto_url", e.foto_url)
            e.activo = True if data.get("activo", True) else False
            db.commit()
            emp_id = e.id
        else:
            # insert
            e = Empleado(
                numero_emp=data["numero_emp"],
                nombre=data["nombre"],
                nombre_corto=data.get("nombre_corto"),
                area=data.get("area"),
                turno=data.get("turno"),
                planta=data.get("planta"),
                foto_url=data.get("foto_url"),
                activo=True,
            )
            db.add(e)
            db.commit()
            emp_id = e.id
        return json_ok(id=emp_id)
    finally:
        db.close()


# ---------- Vacaciones: alta ----------
@app.post("/api/vacaciones")
def alta_vacacion():
    d = request.get_json() or {}
    for r in ("empleado_id", "fecha_inicial", "fecha_final"):
        if not d.get(r):
            return json_error(f"Campo requerido: {r}", 400)

    fi = parse_date(d["fecha_inicial"])
    ff = parse_date(d["fecha_final"])
    if not fi or not ff:
        return json_error("Fechas inválidas en vacación", 400)
    if ff < fi:
        return json_error("fecha_final no puede ser menor que fecha_inicial", 400)

    db = SessionLocal()
    try:
        v = Vacacion(
            empleado_id=int(d["empleado_id"]),
            fecha_inicial=fi,
            fecha_final=ff,
            tipo=d.get("tipo", "Gozo de Vacaciones"),
            gozo=d.get("gozo"),
            fuente=d.get("fuente", "manual"),
        )
        db.add(v)
        db.commit()
        return json_ok(id=v.id)
    finally:
        db.close()



# ---------- Importar Excel/CSV ----------
@app.post("/api/importar/excel")
def importar_excel():
    f = request.files.get("file")
    if not f:
        return json_error("No file", 400)

    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in ALLOWED_IMPORT_EXT:
        return json_error(f"Extensión no permitida. Use: {', '.join(sorted(ALLOWED_IMPORT_EXT))}", 415)

    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(f, engine="openpyxl")
    else:
        try:
            df = pd.read_csv(f, encoding="utf-8")
        except UnicodeDecodeError:
            f.seek(0)
            df = pd.read_csv(f, encoding="latin1")

    if len(df) > MAX_IMPORT_ROWS:
        return json_error(f"Archivo supera el máximo de filas permitidas ({MAX_IMPORT_ROWS})", 413)

    def norm(s):
        return (str(s).strip().lower()
                .replace("á","a").replace("é","e").replace("í","i")
                .replace("ó","o").replace("ú","u").replace("ü","u"))

    colmap = {norm(c): c for c in df.columns}
    wants = {
        "inicial": ["inicial","inicio","fecha inicial","start","startdate"],
        "final":   ["final","fin","fecha final","end","enddate"],
        "numero":  ["#","num","numero","no","id","employee id","empleado"],
        "nombre":  ["nombre","name","empleado nombre"],
        "gozo":    ["gozo","dias","dias gozo","days"],
        "planta":  ["planta","plant","site","sede"],
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

    missing = [lbl for lbl, col in [("Inicial", c_inicial), ("Final", c_final), ("#", c_num), ("Nombre", c_nombre)] if col is None]
    if missing:
        return json_error(f"Columnas requeridas faltantes: {', '.join(missing)}", 400)

    db = SessionLocal()
    creados_empleados = 0
    creadas_vac = 0
    rechazadas = 0
    errores = []

    for idx, row in df.iterrows():
        try:
            ini = parse_date(str(row[c_inicial])); fin = parse_date(str(row[c_final]))
            if not ini or not fin or fin < ini:
                rechazadas += 1; errores.append(f"Row {idx+1}: rango de fecha inválido"); continue

            numero = str(row[c_num]).strip()
            nombre = str(row[c_nombre]).strip()
            if not numero or not nombre:
                rechazadas += 1; errores.append(f"Row {idx+1}: número/nombre vacío"); continue

            gozo = None
            if c_gozo is not None and pd.notna(row[c_gozo]):
                try: gozo = float(row[c_gozo])
                except Exception: gozo = None

            if c_planta is not None and pd.notna(row[c_planta]):
                planta = normalize_planta(row[c_planta])
            else:
                planta = "Planta 1"

            e = db.execute(select(Empleado).where(Empleado.numero_emp == numero)).scalar_one_or_none()
            if not e:
                e = Empleado(
                    numero_emp=numero, nombre=nombre, nombre_corto=None,
                    planta=planta, turno=random.choice(["T1","T2","T3"]), activo=True
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
                fuente="excel",
            )
            db.add(v); creadas_vac += 1
        except Exception as ex:
            traceback.print_exc()
            rechazadas += 1
            errores.append(f"Row {idx+1}: {type(ex).__name__}")

    db.commit(); db.close()
    return json_ok(empleados_creados=creados_empleados, vacaciones_creadas=creadas_vac, rechazadas=rechazadas, errores=errores[:20])

if __name__ == "__main__":
    # Opcional: leer puerto de ENV, por defecto 5000
    import os
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
