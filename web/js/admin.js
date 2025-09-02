//const API_BASE = "http://localhost:5000"; // asegúrate que coincida con tu backend

// ---- Helpers de fetch con timeout y manejo de errores
async function fetchJSON(url, opts={}, timeoutMs=30000){
  const controller = new AbortController();
  const t = setTimeout(()=>controller.abort(), timeoutMs);
  try{
    const r = await fetch(url, {...opts, signal: controller.signal});
    let data = null;
    try{ data = await r.json(); } catch{}
    if(!r.ok){
      const msg = (data && data.error) ? data.error : `HTTP ${r.status}`;
      throw new Error(msg);
    }
    return data;
  } finally {
    clearTimeout(t);
  }
}

// ---- Importar
const formImp = document.getElementById("form-import");
const logImp = document.getElementById("import-log");
formImp.addEventListener("submit", async (e)=>{
  e.preventDefault();
  logImp.textContent = "Importando...";
  try{
    const file = document.getElementById("file").files[0];
    if(!file) throw new Error("Selecciona un archivo");
    const fd = new FormData();
    fd.append("file", file);
    const data = await fetchJSON(`${API_BASE}/api/importar/excel`, { method: "POST", body: fd }, 120000);
    logImp.textContent = JSON.stringify(data, null, 2);
  }catch(err){
    logImp.textContent = `Error: ${err.message}`;
  }
});

// ---- Alta manual (upsert + vacación)
const formMan = document.getElementById("form-manual");
const logMan = document.getElementById("manual-log");
formMan.addEventListener("submit", async (e)=>{
  e.preventDefault();
  logMan.textContent = "Guardando...";
  try{
    const fd = new FormData(formMan);
    // 1) upsert empleado
    const empPayload = {
      numero_emp: fd.get("numero_emp"),
      nombre: fd.get("nombre"),
      planta: fd.get("planta"),
      turno: fd.get("turno") || null
    };
    const rEmp = await fetchJSON(`${API_BASE}/api/empleados`, {
      method:"POST",
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(empPayload)
    });
    const empId = rEmp.id;

    // 2) crear vacación
    const vacPayload = {
      empleado_id: empId,
      fecha_inicial: fd.get("fecha_inicial"),
      fecha_final: fd.get("fecha_final"),
      tipo: "Gozo de Vacaciones",
      gozo: fd.get("gozo") ? parseFloat(fd.get("gozo")) : null
    };
    const rVac = await fetchJSON(`${API_BASE}/api/vacaciones`, {
      method:"POST",
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(vacPayload)
    });

    logMan.textContent = JSON.stringify({empleado:rEmp, vacacion:rVac}, null, 2);
    formMan.reset();
  }catch(err){
    logMan.textContent = `Error: ${err.message}`;
  }
});
