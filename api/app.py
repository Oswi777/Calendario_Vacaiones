import os, datetime, io, traceback
from datetime import date, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from sqlalchemy import select, and_
import pandas as pd
import random

from models import SessionLocal, init_db, Empleado, Vacacion

# -------- Config --------
MAX_CAL_DAYS = int(os.getenv("MAX_CAL_DAYS", "90"))
MAX_IMPORT_ROWS = int(os.getenv("MAX_IMPORT_ROWS", "5000"))
ALLOWED_IMPORT_EXT = {".xlsx", ".xls", ".csv"}
APP_VERSION = os.getenv("APP_VERSION", "1.0.0-tvui")

load_dotenv()
init_db()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ---------- Utils ----------
def parse_date(s: str):
    if not s:
        return None
    s = str(s).strip()
    # Acepta 'YYYY-MM-DD' o 'YYYY-MM-DDThh:mm:ss-zz:zz'
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
    """Normaliza ('1','Planta1','P-3', etc.) a 'Planta 1'/'Planta 3'."""
    if not val: return "Planta 1"
    s = str(val).strip().lower()
    for tok in ["planta", "plant", "pl", "p", "#", " "]:
        s = s.replace(tok, "")
    s = s.strip().strip(".")
    if s in ("1", "01", "uno"):
        return "Planta 1"
    if s in ("3", "03", "tres"):
        return "Planta 3"
    return "Planta 1"

def clamp_cal_range(start: date, end: date):
    """Evita range excesivo en /api/calendario."""
    if (end - start).days > MAX_CAL_DAYS:
        return False
    return True

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

# ---------- Calendario ----------
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
    from sqlalchemy import or_
    stmt = select(Vacacion).join(Empleado).where(
        and_(
            Vacacion.fecha_inicial <= end,
            Vacacion.fecha_final >= start,
            Empleado.activo == True,
        )
    )

    if planta:
        planta_norm = normalize_planta(planta)
        stmt = stmt.where(Empleado.planta == planta_norm)

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

# ---------- Empleados ----------
@app.get("/api/empleados/find")
def empleados_find():
    numero = request.args.get("numero")
    if not numero:
        return json_error("Parametro 'numero' requerido", 400)
    db = SessionLocal()
    e = db.execute(select(Empleado).where(Empleado.numero_emp == numero)).scalar_one_or_none()
    db.close()
    if not e:
        return json_ok(found=False)
    return json_ok(found=True, empleado={
        "id": e.id, "numero_emp": e.numero_emp, "nombre": e.nombre,
        "planta": e.planta, "turno": e.turno, "activo": e.activo
    })

@app.post("/api/empleados")
def alta_empleado():
    """Upsert por numero_emp: si existe, actualiza; si no, crea. Normaliza 'planta'."""
    data = request.get_json() or {}
    if not data.get("numero_emp") or not data.get("nombre"):
        return json_error("numero_emp y nombre son requeridos", 400)

    pl = data.get("planta")
    if pl is not None:
        data["planta"] = normalize_planta(pl)

    db = SessionLocal()
    e = db.execute(select(Empleado).where(Empleado.numero_emp == data["numero_emp"])).scalar_one_or_none()
    if e:
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
            activo=True,
        )
        db.add(e)
        db.commit()
        emp_id = e.id

    db.close()
    return json_ok(id=emp_id)

# ---------- Vacaciones ----------
@app.post("/api/vacaciones")
def alta_vacacion():
    d = request.get_json() or {}
    required = ["empleado_id", "fecha_inicial", "fecha_final"]
    for r in required:
        if r not in d or not d[r]:
            return json_error(f"Campo requerido: {r}", 400)

    fi = parse_date(d["fecha_inicial"])
    ff = parse_date(d["fecha_final"])
    if not fi or not ff:
        return json_error("Fechas inválidas en vacación", 400)
    if ff < fi:
        return json_error("fecha_final no puede ser menor que fecha_inicial", 400)

    db = SessionLocal()
    v = Vacacion(
        empleado_id=d["empleado_id"],
        fecha_inicial=fi,
        fecha_final=ff,
        tipo=d.get("tipo", "Gozo de Vacaciones"),
        gozo=d.get("gozo"),
        fuente=d.get("fuente", "manual"),
    )
    db.add(v)
    db.commit()
    vid = v.id
    db.close()
    return json_ok(id=vid)

# ---------- Importar Excel/CSV (solo columnas clave; ignora extras) ----------
@app.post("/api/importar/excel")
def importar_excel():
    """
    Lee ÚNICAMENTE:
      Inicial, Final, #, Nombre, Gozo (opcional), Planta (opcional)
    Ignora columnas extra. Tipo = 'Gozo de Vacaciones'. Turno aleatorio si el empleado no existe.
    Acepta .xlsx/.xls y .csv (prueba UTF-8 y, si falla, latin1).
    Límite de filas configurable vía MAX_IMPORT_ROWS.
    """
    f = request.files.get("file")
    if not f:
        return json_error("No file", 400)

    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in ALLOWED_IMPORT_EXT:
        return json_error(f"Extensión no permitida. Use: {', '.join(sorted(ALLOWED_IMPORT_EXT))}", 415)

    # Leer DataFrame
    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(f, engine="openpyxl")
    else:
        try:
            df = pd.read_csv(f, encoding="utf-8")
        except UnicodeDecodeError:
            f.seek(0)
            df = pd.read_csv(f, encoding="latin1")

    # Límite de filas
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
            ini = parse_date(str(row[c_inicial]))
            fin = parse_date(str(row[c_final]))
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
