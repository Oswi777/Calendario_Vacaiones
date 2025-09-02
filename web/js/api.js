const API_BASE = "http://localhost:5000";
const API = {
  async calendario(start,end,params={}){
    const qs = new URLSearchParams({start, end, ...params});
    const r = await fetch(`${API_BASE}/api/calendario?`+qs.toString());
    if(!r.ok) throw new Error("API calendario");
    return r.json();
  },
  async importar(file){
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch(`${API_BASE}/api/importar/excel`, { method: "POST", body: fd });
    return r.json();
  },
  async altaEmpleado(payload){
    const r = await fetch(`${API_BASE}/api/empleados`, { method:"POST", headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    return r.json();
  },
  async altaVacacion(payload){
    const r = await fetch(`${API_BASE}/api/vacaciones`, { method:"POST", headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    return r.json();
  }
}
