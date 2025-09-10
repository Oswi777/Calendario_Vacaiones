import os, datetime, io, traceback
from datetime import date, timedelta
from flask import Flask, jsonify, request, send_from_directory, abort
from flask_cors import CORS
from dotenv import load_dotenv
from sqlalchemy import select, and_, or_, desc, func
import pandas as pd
import random
import re
from werkzeug.exceptions import HTTPException

from models import SessionLocal, init_db, Empleado, Vacacion

# -------- Config --------
MAX_CAL_DAYS = int(os.getenv("MAX_CAL_DAYS", "90"))
MAX_IMPORT_ROWS = int(os.getenv("MAX_IMPORT_ROWS", "5000"))
ALLOWED_IMPORT_EXT = {".xlsx", ".xls", ".csv"}
APP_VERSION = os.getenv("APP_VERSION", "1.2.1-ordering+ui")

# Directorio del frontend (carpeta hermana a /api)
WEB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web"))

load_dotenv()
init_db()

app = Flask(__name__)
# Si sirves todo con Flask (mismo origen), CORS ya no es necesario para /api/*
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

# --------- Nombres canónicos ---------
def _clean_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def canonicalize_nombre(raw: str, apellidos: str = None, nombres: str = None) -> str:
    if apellidos is not None or nombres is not None:
        ap = _clean_spaces(apellidos or "")
        no = _clean_spaces(nombres or "")
        if ap and no: return f"{ap}, {no}"
        return _clean_spaces(no or ap)

    raw = _clean_spaces(raw or "")
    if not raw:
        return ""
    if "," in raw:
        parts = [p.strip() for p in raw.split(",", 1)]
        ap = _clean_spaces(parts[0])
        no = _clean_spaces(parts[1] if len(parts) > 1 else "")
        if ap and no: return f"{ap}, {no}"
        return _clean_spaces(no or ap)

    toks = raw.split(" ")
    if len(toks) >= 3:
        ap = " ".join(toks[-2:])
        no = " ".join(toks[:-2])
        return f"{_clean_spaces(ap)}, {_clean_spaces(no)}"
    if len(toks) == 2:
        no = toks[0]; ap = toks[1]
        return f"{_clean_spaces(ap)}, {_clean_spaces(no)}"
    return raw

def derive_nombre_corto(nombre_canonico: str) -> str:
    s = _clean_spaces(nombre_canonico)
    if not s:
        return ""
    if "," in s:
        ap, no = [p.strip() for p in s.split(",", 1)]
        primer_ap = ap.split(" ")[0] if ap else ""
        primer_no = no.split(" ")[0] if no else ""
        out = f"{primer_no} {primer_ap}".strip()
        return _clean_spaces(out)
    toks = s.split(" ")
    if len(toks) >= 2:
        return _clean_spaces(f"{toks[0]} {toks[1]}")
    return s

# ---------- Error handler global ----------
@app.errorhandler(Exception)
def on_exception(e):
    # Deja pasar errores HTTP (404, 405, etc.) como están
    if isinstance(e, HTTPException):
        return e
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
                "nombre_corto": e.nombre_corto or derive_nombre_corto(e.nombre),
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
    """Listado con filtros y paginación simple. Orden: nuevos primero (id DESC)."""
    q = (request.args.get("q") or "").strip()
    planta = request.args.get("planta")
    turno = request.args.get("turno")
    page = int(request.args.get("page", "1"))
    size = int(request.args.get("size", "20"))
    page = max(1, page); size = max(1, min(size, 100))

    db = SessionLocal()
    base = select(Empleado).where(Empleado.activo == True)
    if planta:
        base = base.where(Empleado.planta == normalize_planta(planta))
    if turno:
        base = base.where(Empleado.turno == turno)
    if q:
        like = f"%{q}%"
        base = base.where(or_(Empleado.nombre.ilike(like),
                              Empleado.numero_emp.ilike(like)))

    # total (COUNT(*))
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar() or 0

    # ORDEN NUEVOS PRIMERO
    stmt = base.order_by(desc(Empleado.id)).offset((page-1)*size).limit(size)

    rows = []
    for e in db.execute(stmt).scalars():
        rows.append({
            "id": e.id, "numero_emp": e.numero_emp, "nombre": e.nombre,
            "nombre_corto": e.nombre_corto or derive_nombre_corto(e.nombre),
            "planta": e.planta, "turno": e.turno, "area": e.area,
            "foto_url": e.foto_url, "activo": e.activo
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
        e.nombre = canonicalize_nombre(data["nombre"])
        if not data.get("nombre_corto"):
            e.nombre_corto = derive_nombre_corto(e.nombre)
    if "nombre_corto" in data:
        e.nombre_corto = _clean_spaces(data["nombre_corto"])
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
    e.activo = False
    db.commit(); db.close()
    return json_ok(deleted=True)

# ---------- Helper: traslapes ----------
def _hay_traslape(db, empleado_id: int, fi: date, ff: date, ignore_id: int=None) -> bool:
    stmt = select(Vacacion).where(
        Vacacion.empleado_id==empleado_id,
        Vacacion.fecha_inicial <= ff,
        Vacacion.fecha_final >= fi,
    )
    if ignore_id:
        stmt = stmt.where(Vacacion.id != ignore_id)
    return db.execute(stmt).first() is not None

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
    base = select(Vacacion).join(Empleado).where(
        and_(Vacacion.fecha_inicial <= end,
             Vacacion.fecha_final >= start,
             Empleado.activo == True)
    )
    if planta:
        base = base.where(Empleado.planta == normalize_planta(planta))
    if q:
        like = f"%{q}%"
        base = base.where(or_(Empleado.nombre.ilike(like), Empleado.numero_emp.ilike(like)))

    total = db.execute(select(func.count()).select_from(base.subquery())).scalar() or 0
    stmt = base.order_by(desc(Vacacion.fecha_inicial), desc(Vacacion.id))\
               .offset((page-1)*size).limit(size)

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

@app.post("/api/vacaciones")
def vacaciones_create():
    d = request.get_json() or {}
    reqs = ("empleado_id","fecha_inicial","fecha_final")
    falt = [k for k in reqs if not (str(d.get(k) or "").strip())]
    if falt: return json_error(f"Campos requeridos: {', '.join(falt)}", 400)

    fi = parse_date(d["fecha_inicial"]); ff = parse_date(d["fecha_final"])
    if not fi or not ff: return json_error("Fechas inválidas", 400)
    if ff < fi: return json_error("fecha_final no puede ser menor que fecha_inicial", 400)

    db = SessionLocal()
    try:
        emp = db.get(Empleado, int(d["empleado_id"]))
        if not emp or not emp.activo:
            return json_error("Empleado no encontrado o inactivo", 404)

        # chequeo traslape
        if _hay_traslape(db, emp.id, fi, ff):
            return json_error("Rango traslapa con otra vacación del empleado", 400)

        v = Vacacion(
            empleado_id=emp.id,
            fecha_inicial=fi,
            fecha_final=ff,
            tipo=d.get("tipo","Gozo de Vacaciones"),
            gozo=d.get("gozo"),
            fuente=d.get("fuente","manual"),
        )
        db.add(v); db.commit()
        return json_ok(id=v.id)
    except Exception:
        db.rollback(); raise
    finally:
        db.close()

@app.put("/api/vacaciones/<int:vac_id>")
def vacaciones_update(vac_id):
    d = request.get_json() or {}
    db = SessionLocal()
    v = db.get(Vacacion, vac_id)
    if not v:
        db.close(); return json_error("Vacación no encontrada", 404)

    if "empleado_id" in d and d["empleado_id"]:
        emp = db.get(Empleado, int(d["empleado_id"]))
        if not emp or not emp.activo:
            db.close(); return json_error("Empleado destino no encontrado o inactivo", 400)
        v.empleado_id = int(d["empleado_id"])
    if "fecha_inicial" in d and d["fecha_inicial"]:
        fi = parse_date(d["fecha_inicial"])
        if not fi: db.close(); return json_error("fecha_inicial inválida", 400)
        v.fecha_inicial = fi
    if "fecha_final" in d and d["fecha_final"]:
        ff = parse_date(d["fecha_final"])
        if not ff: db.close(); return json_error("fecha_final inválida", 400)
        v.fecha_final = ff
    if v.fecha_final < v.fecha_inicial:
        db.close(); return json_error("fecha_final no puede ser menor que fecha_inicial", 400)

    # chequeo traslape ignorando la propia vacación
    if _hay_traslape(db, v.empleado_id, v.fecha_inicial, v.fecha_final, ignore_id=v.id):
        db.close(); return json_error("Rango traslapa con otra vacación del empleado", 400)

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

# ---------- Empleados: upsert ----------
@app.post("/api/empleados")
def alta_empleado():
    data = request.get_json() or {}
    if not data.get("numero_emp") or not (data.get("nombre") or (data.get("apellidos") or data.get("nombres"))):
        return json_error("numero_emp y nombre/apellidos+nombres son requeridos", 400)

    nombre_canon = canonicalize_nombre(
        data.get("nombre"),
        data.get("apellidos"),
        data.get("nombres")
    )
    if data.get("planta") is not None:
        data["planta"] = normalize_planta(data["planta"])

    db = SessionLocal()
    try:
        e = db.execute(select(Empleado).where(Empleado.numero_emp == str(data["numero_emp"]).strip())).scalar_one_or_none()
        if e:
            e.nombre = nombre_canon or e.nombre
            if not data.get("nombre_corto"):
                e.nombre_corto = derive_nombre_corto(e.nombre)
            else:
                e.nombre_corto = _clean_spaces(data["nombre_corto"])
            e.area = data.get("area", e.area)
            e.turno = data.get("turno", e.turno)
            e.planta = data.get("planta", e.planta)
            e.foto_url = data.get("foto_url", e.foto_url)
            e.activo = True if data.get("activo", True) else False
            db.commit()
            emp_id = e.id
        else:
            e = Empleado(
                numero_emp=str(data["numero_emp"]).strip(),
                nombre=nombre_canon,
                nombre_corto=_clean_spaces(data.get("nombre_corto") or derive_nombre_corto(nombre_canon)),
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

# ---------- Alta atómica empleado+vacación ----------
@app.post("/api/alta/empleado-vacacion")
def alta_empleado_vacacion():
    d = request.get_json() or {}

    reqs = ("numero_emp", "fecha_inicial", "fecha_final")
    faltantes = [k for k in reqs if not (str(d.get(k) or "").strip())]

    nombre_canon = canonicalize_nombre(
        d.get("nombre"),
        d.get("apellidos"),
        d.get("nombres"),
    ).strip()

    if not nombre_canon:
        faltantes.append("nombre (o apellidos+nombres)")

    if faltantes:
        return json_error(f"Campos requeridos: {', '.join(faltantes)}", 400)

    fi = parse_date(d["fecha_inicial"])
    ff = parse_date(d["fecha_final"])
    if not fi or not ff:
        return json_error("Fechas inválidas", 400)
    if ff < fi:
        return json_error("fecha_final no puede ser menor que fecha_inicial", 400)

    if d.get("planta") is not None:
        d["planta"] = normalize_planta(d["planta"])

    db = SessionLocal()
    try:
        numero_emp = str(d["numero_emp"]).strip()
        e = db.execute(select(Empleado).where(Empleado.numero_emp == numero_emp)).scalar_one_or_none()
        if e:
            e.nombre = nombre_canon or e.nombre
            e.nombre_corto = _clean_spaces(d.get("nombre_corto") or derive_nombre_corto(e.nombre))
            e.area = d.get("area", e.area)
            e.turno = d.get("turno", e.turno)
            e.planta = d.get("planta", e.planta)
            e.foto_url = d.get("foto_url", e.foto_url)
            e.activo = True
        else:
            e = Empleado(
                numero_emp=numero_emp,
                nombre=nombre_canon,
                nombre_corto=_clean_spaces(d.get("nombre_corto") or derive_nombre_corto(nombre_canon)),
                area=d.get("area"),
                turno=d.get("turno"),
                planta=d.get("planta"),
                foto_url=d.get("foto_url"),
                activo=True,
            )
            db.add(e)
            db.flush()

        # chequeo traslape antes de insertar
        if _hay_traslape(db, e.id, fi, ff):
            db.rollback()
            return json_error("Rango traslapa con otra vacación del empleado", 400)

        v = Vacacion(
            empleado_id=e.id,
            fecha_inicial=fi,
            fecha_final=ff,
            tipo=d.get("tipo", "Gozo de Vacaciones"),
            gozo=d.get("gozo"),
            fuente=d.get("fuente", "manual"),
        )
        db.add(v)

        db.commit()
        return json_ok(empleado_id=e.id, vacacion_id=v.id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

# ---------- Frontend (sirve /, /admin y archivos estáticos) ----------
@app.route("/")
def serve_index():
    return send_from_directory(WEB_DIR, "index.html")

@app.route("/admin")
def serve_admin():
    return send_from_directory(WEB_DIR, "admin.html")

@app.route("/<path:path>")
def serve_static_files(path):
    # No interceptar /api/*
    if path.startswith("api/"):
        abort(404)
    return send_from_directory(WEB_DIR, path)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
    
