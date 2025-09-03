// admin.js

// Helper: fetch con timeout y manejo de errores JSON
async function fetchJSON(url, opts = {}, timeoutMs = 30000) {
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const r = await fetch(url, { ...opts, signal: controller.signal });
    let data = null;
    try { data = await r.json(); } catch {}
    if (!r.ok) {
      const msg = (data && data.error) ? data.error : `HTTP ${r.status}`;
      throw new Error(msg);
    }
    return data;
  } finally {
    clearTimeout(t);
  }
}

// ---- Importar Excel/CSV
const formImp = document.getElementById("form-import");
const logImp = document.getElementById("import-log");
formImp.addEventListener("submit", async (e) => {
  e.preventDefault();
  logImp.textContent = "Importando...";
  try {
    const file = document.getElementById("file").files[0];
    if (!file) throw new Error("Selecciona un archivo");
    const fd = new FormData();
    fd.append("file", file);
    const data = await fetchJSON(`${API_BASE}/api/importar/excel`, {
      method: "POST",
      body: fd
    }, 120000);
    logImp.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    logImp.textContent = `Error: ${err.message}`;
  }
});

// ---- Alta manual (upsert empleado + crear vacación)
const formMan = document.getElementById("form-manual");
const logMan = document.getElementById("manual-log");
formMan.addEventListener("submit", async (e) => {
  e.preventDefault();
  logMan.textContent = "Guardando...";
  try {
    const fd = new FormData(formMan);

    const ini = fd.get("fecha_inicial");
    const fin = fd.get("fecha_final");
    if (!ini || !fin) {
      logMan.textContent = "Error: selecciona fechas inicial y final.";
      return;
    }
    if (new Date(ini) > new Date(fin)) {
      logMan.textContent = "Error: la fecha final no puede ser menor que la inicial.";
      return;
    }

    // 1) upsert empleado
    const rEmp = await fetchJSON(`${API_BASE}/api/empleados`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        numero_emp: fd.get("numero_emp"),
        nombre: fd.get("nombre"),
        planta: fd.get("planta"),
        turno: fd.get("turno") || null
      })
    });

    // 2) crear vacación
    const rVac = await fetchJSON(`${API_BASE}/api/vacaciones`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        empleado_id: rEmp.id,
        fecha_inicial: ini,
        fecha_final: fin,
        tipo: "Gozo de Vacaciones",
        gozo: fd.get("gozo") ? parseFloat(fd.get("gozo")) : null
      })
    });

    logMan.textContent = JSON.stringify({ empleado: rEmp, vacacion: rVac }, null, 2);
    formMan.reset();
  } catch (err) {
    logMan.textContent = `Error: ${err.message}`;
  }
});
