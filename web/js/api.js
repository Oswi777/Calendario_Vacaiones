// web/js/api.js
// Base de API: usa window.API_BASE si está definida ANTES de cargar este archivo.
// De lo contrario, usa http://localhost:5000 (Flask por defecto).
const API_BASE = (window.API_BASE ?? window.location.origin).replace(/\/$/, "");

const API = {
  async calendario(start,end,params={}){
    const qs = new URLSearchParams({start, end, ...params});
    const r = await fetch(`${API_BASE}/api/calendario?`+qs.toString());
    if(!r.ok) throw new Error(`API calendario: HTTP ${r.status}`);
    return r.json();
  },
  async importar(file){
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch(`${API_BASE}/api/importar/excel`, { method: "POST", body: fd });
    if(!r.ok){ let t=""; try{t=await r.text();}catch{}; throw new Error(`API importar: HTTP ${r.status} ${t}`); }
    return r.json();
  },
  async altaEmpleado(payload){
    const r = await fetch(`${API_BASE}/api/empleados`, {
      method:"POST", headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)
    });
    if(!r.ok){ let t=""; try{t=await r.text();}catch{}; throw new Error(`API altaEmpleado: HTTP ${r.status} ${t}`); }
    return r.json();
  },
  async altaVacacion(payload){
    const r = await fetch(`${API_BASE}/api/vacaciones`, {
      method:"POST", headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)
    });
    if(!r.ok){ let t=""; try{t=await r.text();}catch{}; throw new Error(`API altaVacacion: HTTP ${r.status} ${t}`); }
    return r.json();
  }
};
