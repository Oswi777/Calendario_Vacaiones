// web/js/api.js
// Base de API: usa window.API_BASE si está definida ANTES de cargar este archivo.
const API_BASE = (window.API_BASE || "http://localhost:5000").replace(/\/$/, "");

// Helper fetch sin caché
async function fetchNoCache(url) {
  const r = await fetch(url, {
    method: "GET",
    cache: "no-store",
    headers: {
      "Cache-Control": "no-cache, no-store, must-revalidate",
      "Pragma": "no-cache",
      "Expires": "0",
    }
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

const API = {
  async calendario(start, end, params = {}) {
    // cache-buster
    const qs = new URLSearchParams({ start, end, ...params, _ts: Date.now() });
    const url = `${API_BASE}/api/calendario?` + qs.toString();
    return fetchNoCache(url);
  },
  async importar(file) {
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch(`${API_BASE}/api/importar/excel?_ts=${Date.now()}`, {
      method: "POST",
      body: fd,
      cache: "no-store",
      headers: {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
      }
    });
    if (!r.ok) { let t = ""; try { t = await r.text(); } catch {} ; throw new Error(`API importar: HTTP ${r.status} ${t}`); }
    return r.json();
  },
  async altaEmpleado(payload) {
    const r = await fetch(`${API_BASE}/api/empleados?_ts=${Date.now()}`, {
      method: "POST",
      headers: {'Content-Type':'application/json', "Cache-Control":"no-cache"},
      body: JSON.stringify(payload),
      cache: "no-store",
    });
    if (!r.ok) { let t = ""; try { t = await r.text(); } catch {} ; throw new Error(`API altaEmpleado: HTTP ${r.status} ${t}`); }
    return r.json();
  },
  async altaVacacion(payload) {
    const r = await fetch(`${API_BASE}/api/vacaciones?_ts=${Date.now()}`, {
      method: "POST",
      headers: {'Content-Type':'application/json', "Cache-Control":"no-cache"},
      body: JSON.stringify(payload),
      cache: "no-store",
    });
    if (!r.ok) { let t = ""; try { t = await r.text(); } catch {} ; throw new Error(`API altaVacacion: HTTP ${r.status} ${t}`); }
    return r.json();
  }
};
