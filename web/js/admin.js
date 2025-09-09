window.API_BASE = (window.API_BASE ?? window.location.origin).replace(/\/$/, "");
// Persistencia de filtros/estado
const EMP_STATE_KEY = "vacaciones.admin.empleados";
const VAC_STATE_KEY = "vacaciones.admin.vacaciones";

// No redeclarar API_BASE si ya viene de api.js
//window.API_BASE = window.API_BASE || "http://localhost:5000";

// ---- Parachoques global contra submits no deseados en editores ----
document.addEventListener("submit", (e)=>{
  const okIds = new Set(["form-import","form-manual"]);
  if (!e.target || !okIds.has(e.target.id)) {
    e.preventDefault(); // bloquea submits accidentales (editores)
  }
}, true);

// Helper fetch JSON con manejo de error
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
  } finally { clearTimeout(t); }
}

const msg = document.getElementById("admin_msg");
function setMsg(text){ msg.textContent = text || ""; }

// ----- Tabs
const tabEmp = document.getElementById("tabEmp");
const tabVac = document.getElementById("tabVac");
const boxEmp = document.getElementById("boxEmp");
const boxVac = document.getElementById("boxVac");
const editorEmp = document.getElementById("editorEmp");
const editorVac = document.getElementById("editorVac");

tabEmp.onclick = (ev)=>{ 
  ev.preventDefault();
  tabEmp.classList.add("active"); 
  tabVac.classList.remove("active"); 
  boxEmp.style.display="block"; 
  boxVac.style.display="none"; 
  editorEmp.style.display="block"; 
  editorVac.style.display="none"; 
  saveEmpState();
};
tabVac.onclick = (ev)=>{ 
  ev.preventDefault();
  tabVac.classList.add("active"); 
  tabEmp.classList.remove("active"); 
  boxVac.style.display="block"; 
  boxEmp.style.display="none"; 
  editorVac.style.display="block"; 
  editorEmp.style.display="none"; 
  saveVacState();
};

// ----- Empleados: listado/búsqueda/paginación
const emp_q = document.getElementById("emp_q");
const emp_planta = document.getElementById("emp_planta");
const emp_turno = document.getElementById("emp_turno");
const emp_buscar = document.getElementById("emp_buscar");
const emp_prev = document.getElementById("emp_prev");
const emp_next = document.getElementById("emp_next");
const emp_page = document.getElementById("emp_page");
const emp_tbody = document.getElementById("emp_tbody");

let empPage = 1, empSize = 20, empTotal = 0;

function saveEmpState(){
  try{
    localStorage.setItem(EMP_STATE_KEY, JSON.stringify({
      q: emp_q.value || "",
      planta: emp_planta.value || "",
      turno: emp_turno.value || "",
      page: empPage,
      size: empSize
    }));
  }catch{}
}
function loadEmpState(){
  try{
    const raw = localStorage.getItem(EMP_STATE_KEY);
    if(!raw) return;
    const st = JSON.parse(raw);
    if (st.q != null) emp_q.value = st.q;
    if (st.planta != null) emp_planta.value = st.planta;
    if (st.turno != null) emp_turno.value = st.turno;
    if (st.page) empPage = Math.max(1, parseInt(st.page,10)||1);
    if (st.size) empSize = Math.max(1, Math.min(100, parseInt(st.size,10)||20));
  }catch{}
}

async function loadEmpleados() {
  setMsg("Cargando empleados...");
  const qs = new URLSearchParams({
    q: emp_q.value || "",
    planta: emp_planta.value || "",
    turno: emp_turno.value || "",
    page: empPage, size: empSize
  });
  try {
    const data = await fetchJSON(`${window.API_BASE}/api/empleados?` + qs.toString());
    empTotal = data.total || 0;
    const maxp = Math.max(1, Math.ceil(empTotal/empSize));
    if (empPage > maxp) { empPage = maxp; saveEmpState(); return loadEmpleados(); }

    emp_page.textContent = `Página ${data.page} / ${maxp}`;
    emp_tbody.innerHTML = "";
    (data.items || []).forEach(e => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${e.numero_emp}</td><td>${e.nombre}</td><td>${e.planta||""}</td><td>${e.turno||""}</td>
        <td><button data-id="${e.id}" class="emp_edit" type="button">Editar</button></td>`;
      emp_tbody.appendChild(tr);
    });
    setMsg("");
    saveEmpState();
  } catch (err) {
    setMsg("Error: " + err.message);
    console.error(err);
  }
}
emp_buscar.onclick = (ev)=>{ ev.preventDefault(); empPage = 1; saveEmpState(); loadEmpleados(); };
emp_prev.onclick = (ev)=>{ ev.preventDefault(); if(empPage>1){ empPage--; saveEmpState(); loadEmpleados(); } };
emp_next.onclick = (ev)=>{ ev.preventDefault(); const maxp = Math.max(1, Math.ceil(empTotal/empSize)); if(empPage<maxp){ empPage++; saveEmpState(); loadEmpleados(); } };
emp_q.addEventListener("input", ()=>{ saveEmpState(); });
emp_planta.addEventListener("change", ()=>{ saveEmpState(); });
emp_turno.addEventListener("change", ()=>{ saveEmpState(); });

emp_tbody.addEventListener("click", (e)=>{
  const btn = e.target.closest(".emp_edit"); if(!btn) return;
  const tr = btn.closest("tr"); const tds = tr.querySelectorAll("td");
  document.getElementById("e_emp_id").value = btn.dataset.id;
  document.getElementById("e_emp_num").value = tds[0].textContent || "";
  document.getElementById("e_emp_nombre").value = tds[1].textContent || "";
  document.getElementById("e_emp_planta").value = tds[2].textContent || "Planta 1";
  document.getElementById("e_emp_turno").value = tds[3].textContent || "";
  setMsg("Empleado cargado en editor.");
});

// Guardar / Borrar Empleado
document.getElementById("e_emp_save").onclick = async (ev)=>{
  ev.preventDefault();
  try{
    const id = document.getElementById("e_emp_id").value;
    if(!id) throw new Error("Selecciona un empleado de la lista.");
    const payload = {
      numero_emp: document.getElementById("e_emp_num").value,
      nombre: document.getElementById("e_emp_nombre").value,
      nombre_corto: document.getElementById("e_emp_corto").value || null,
      planta: document.getElementById("e_emp_planta").value,
      turno: document.getElementById("e_emp_turno").value || null,
      area: document.getElementById("e_emp_area").value || null,
      foto_url: document.getElementById("e_emp_foto").value || null,
    };
    await fetchJSON(`${window.API_BASE}/api/empleados/${id}`, {
      method:"PUT", headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)
    });
    setMsg("Empleado guardado.");
    await loadEmpleados();
  }catch(err){ setMsg("Error: " + err.message); }
};
document.getElementById("e_emp_delete").onclick = async (ev)=>{
  ev.preventDefault();
  try{
    const id = document.getElementById("e_emp_id").value;
    if(!id) throw new Error("Selecciona un empleado de la lista.");
    if(!confirm("¿Borrar (inactivar) empleado?")) return;
    await fetchJSON(`${window.API_BASE}/api/empleados/${id}`, { method:"DELETE" });
    setMsg("Empleado borrado (inactivado).");
    await loadEmpleados();
  }catch(err){ setMsg("Error: " + err.message); }
};

// ----- Vacaciones: listado/búsqueda/paginación
const vac_q = document.getElementById("vac_q");
const vac_planta = document.getElementById("vac_planta");
const vac_start = document.getElementById("vac_start");
const vac_end = document.getElementById("vac_end");
const vac_buscar = document.getElementById("vac_buscar");
const vac_prev = document.getElementById("vac_prev");
const vac_next = document.getElementById("vac_next");
const vac_page = document.getElementById("vac_page");
const vac_tbody = document.getElementById("vac_tbody");

let vacPage = 1, vacSize = 20, vacTotal = 0;

function saveVacState(){
  try{
    localStorage.setItem(VAC_STATE_KEY, JSON.stringify({
      q: vac_q.value || "",
      planta: vac_planta.value || "",
      start: vac_start.value || "",
      end: vac_end.value || "",
      page: vacPage,
      size: vacSize
    }));
  }catch{}
}
function loadVacState(){
  try{
    const raw = localStorage.getItem(VAC_STATE_KEY);
    if(!raw) return;
    const st = JSON.parse(raw);
    if (st.q != null) vac_q.value = st.q;
    if (st.planta != null) vac_planta.value = st.planta;
    if (st.start) vac_start.value = st.start;
    if (st.end) vac_end.value = st.end;
    if (st.page) vacPage = Math.max(1, parseInt(st.page,10)||1);
    if (st.size) vacSize = Math.max(1, Math.min(100, parseInt(st.size,10)||20));
  }catch{}
}
function defaultVacRangeIfEmpty(){
  if (!vac_start.value || !vac_end.value){
    const today = new Date();
    const y = today.toISOString().slice(0,10);
    const d15 = new Date(today); d15.setDate(d15.getDate()+14);
    const z = d15.toISOString().slice(0,10);
    if(!vac_start.value) vac_start.value = y;
    if(!vac_end.value) vac_end.value = z;
  }
}

// Añade esta función utilitaria
function weekRangeJS(d=new Date()){
  const x = new Date(d);
  const dow = x.getDay(); // 0=Dom
  const start = new Date(x); start.setDate(x.getDate() - ((dow+6)%7)); start.setHours(0,0,0,0);
  const end = new Date(start); end.setDate(start.getDate()+6); end.setHours(0,0,0,0);
  const fmt = (u)=>u.toISOString().slice(0,10);
  return { start: fmt(start), end: fmt(end) };
}



// Botón “Semana actual” en Vacaciones (admin)
document.getElementById("vac_today").onclick = (ev)=>{
  ev.preventDefault();
  const r = weekRangeJS(new Date());
  vac_start.value = r.start;
  vac_end.value = r.end;
  saveVacState();
  loadVacaciones();
};


async function loadVacaciones(){
  setMsg("Cargando vacaciones...");
  defaultVacRangeIfEmpty();
  const qs = new URLSearchParams({
    q: vac_q.value || "",
    planta: vac_planta.value || "",
    start: vac_start.value,
    end: vac_end.value,
    page: vacPage, size: vacSize
  });
  try{
    const data = await fetchJSON(`${window.API_BASE}/api/vacaciones?` + qs.toString());
    vacTotal = data.total || 0;
    const maxp = Math.max(1, Math.ceil(vacTotal/vacSize));
    if (vacPage > maxp) { vacPage = maxp; saveVacState(); return loadVacaciones(); }

    vac_page.textContent = `Página ${data.page} / ${maxp}`;
    vac_tbody.innerHTML = "";
    (data.items || []).forEach(v => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${v.id}</td><td>${v.numero_emp}</td><td>${v.nombre}</td>
        <td>${v.fecha_inicial}</td><td>${v.fecha_final}</td>
        <td>${v.tipo||""}</td><td>${v.gozo??""}</td>
        <td><button data-id="${v.id}" class="vac_edit" type="button">Editar</button></td>`;
      vac_tbody.appendChild(tr);
    });
    setMsg("");
    saveVacState();
  }catch(err){ setMsg("Error: " + err.message); console.error(err); }
}
vac_buscar.onclick = (ev)=>{ ev.preventDefault(); vacPage=1; saveVacState(); loadVacaciones(); };
vac_prev.onclick = (ev)=>{ ev.preventDefault(); if(vacPage>1){ vacPage--; saveVacState(); loadVacaciones(); } };
vac_next.onclick = (ev)=>{ ev.preventDefault(); const maxp = Math.max(1, Math.ceil(vacTotal/vacSize)); if(vacPage<maxp){ vacPage++; saveVacState(); loadVacaciones(); } };
[vac_q, vac_planta, vac_start, vac_end].forEach(el=>{
  el.addEventListener("input", saveVacState);
  el.addEventListener("change", saveVacState);
});

vac_tbody.addEventListener("click", (e)=>{
  const btn = e.target.closest(".vac_edit"); if(!btn) return;
  const tr = btn.closest("tr"); const tds = tr.querySelectorAll("td");
  document.getElementById("e_vac_id").value = tds[0].textContent;
  document.getElementById("e_vac_empid").value = ""; // opcional: reasignar empleado
  document.getElementById("e_vac_ini").value = tds[3].textContent.slice(0,10);
  document.getElementById("e_vac_fin").value = tds[4].textContent.slice(0,10);
  document.getElementById("e_vac_tipo").value = tds[5].textContent || "Gozo de Vacaciones";
  document.getElementById("e_vac_gozo").value = tds[6].textContent || "";
  setMsg("Vacación cargada en editor.");
});

// Guardar / Borrar Vacación
document.getElementById("e_vac_save").onclick = async (ev)=>{
  ev.preventDefault();
  try{
    const id = document.getElementById("e_vac_id").value;
    if(!id) throw new Error("Selecciona una vacación de la lista.");
    const payload = {
      empleado_id: document.getElementById("e_vac_empid").value ? Number(document.getElementById("e_vac_empid").value) : undefined,
      fecha_inicial: document.getElementById("e_vac_ini").value,
      fecha_final: document.getElementById("e_vac_fin").value,
      tipo: document.getElementById("e_vac_tipo").value || "Gozo de Vacaciones",
      gozo: document.getElementById("e_vac_gozo").value ? Number(document.getElementById("e_vac_gozo").value) : null
    };
    await fetchJSON(`${window.API_BASE}/api/vacaciones/${id}`, {
      method:"PUT", headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)
    });
    setMsg("Vacación guardada.");
    await loadVacaciones();
  }catch(err){ setMsg("Error: " + err.message); }
};
document.getElementById("e_vac_delete").onclick = async (ev)=>{
  ev.preventDefault();
  try{
    const id = document.getElementById("e_vac_id").value;
    if(!id) throw new Error("Selecciona una vacación de la lista.");
    if(!confirm("¿Borrar vacación definitivamente?")) return;
    await fetchJSON(`${window.API_BASE}/api/vacaciones/${id}`, { method:"DELETE" });
    setMsg("Vacación borrada.");
    await loadVacaciones();
  }catch(err){ setMsg("Error: " + err.message); }
};

// ----- Importar
const formImp = document.getElementById("form-import");
const logImp = document.getElementById("import-log");
formImp.addEventListener("submit", async (e)=>{
  e.preventDefault();
  logImp.textContent = "Importando...";
  try{
    const file = document.getElementById("file").files[0];
    if(!file) throw new Error("Selecciona un archivo");
    const fd = new FormData(); fd.append("file", file);
    const data = await fetchJSON(`${window.API_BASE}/api/importar/excel`, { method: "POST", body: fd }, 120000);
    logImp.textContent = JSON.stringify(data, null, 2);
    await Promise.all([loadEmpleados(), loadVacaciones()]);
  }catch(err){ logImp.textContent = `Error: ${err.message}`; }
});

// ----- Alta manual (ahora ATÓMICA)
const formMan = document.getElementById("form-manual");
const logMan = document.getElementById("manual-log");
formMan.addEventListener("submit", async (e)=>{
  e.preventDefault();
  logMan.textContent = "Guardando...";
  try{
    const fd = new FormData(formMan);
    const ini = fd.get("fecha_inicial");
    const fin = fd.get("fecha_final");
    if(!ini || !fin) throw new Error("Selecciona fechas");
    if(new Date(ini) > new Date(fin)) throw new Error("La fecha final no puede ser menor que la inicial");

    const apellidos = (fd.get("apellidos")||"").trim();
    const nombres = (fd.get("nombres")||"").trim();

    // Construye también el nombre canónico para el backend
    const nombreCanon = apellidos && nombres ? `${apellidos}, ${nombres}` : (apellidos || nombres);

    const payload = {
      numero_emp: (fd.get("numero_emp")||"").trim(),
      apellidos,
      nombres,
      nombre: nombreCanon,    // redundante pero útil
      planta: fd.get("planta"),
      turno: fd.get("turno") || null,
      fecha_inicial: ini,
      fecha_final: fin,
      tipo: "Gozo de Vacaciones",
      gozo: fd.get("gozo") ? parseFloat(fd.get("gozo")) : null,
      fuente: "manual"
    };

    const data = await fetchJSON(`${window.API_BASE}/api/alta/empleado-vacacion`, {
      method:"POST", headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)
    });

    logMan.textContent = JSON.stringify(data, null, 2);
    formMan.reset();

    // Ajusta filtros para ver lo recién creado
    vac_q.value = payload.numero_emp || nombreCanon || "";
    vac_start.value = ini;
    vac_end.value = fin;
    saveVacState();

    await loadVacaciones();
  }catch(err){
    logMan.textContent = `Error: ${err.message}`;
  }
});


// -------- Inicialización --------
loadEmpState();
loadVacState();
if (!vac_start.value || !vac_end.value) {
  const today = new Date();
  const y = today.toISOString().slice(0,10);
  const d15 = new Date(today); d15.setDate(d15.getDate()+14);
  const z = d15.toISOString().slice(0,10);
  if(!vac_start.value) vac_start.value = y;
  if(!vac_end.value) vac_end.value = z;
  saveVacState();
}
loadEmpleados();
loadVacaciones();
