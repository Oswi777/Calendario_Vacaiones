const grid1 = document.getElementById("grid_w1");
const grid2 = document.getElementById("grid_w2");
const lbl1 = document.getElementById("lbl_w1");
const lbl2 = document.getElementById("lbl_w2");
const f_planta = document.getElementById("f_planta");
const q = document.getElementById("q");
const btnPrev = document.getElementById("btnPrev");
const btnNext = document.getElementById("btnNext");
const lblAnchor = document.getElementById("lblAnchor");

// Persistencia UI
const STATE_KEY = "vacaciones.ui";

// Paginación & rotación
const PAGE_SIZE = 4;      // 4 nombres a la vez
const ROTATE_MS = 30000;   // cambia cada 5 s
const FADE_MS = 450;      // duración del fade-out/in (ms)

// Estado
let anchor = new Date();
let itemsByDay1 = {};
let itemsByDay2 = {};
let offsets1 = {};
let offsets2 = {};
let rotateTimer = null;

// --------- Utils de fechas/estado ----------
function anchorLabel(d){ const {start,end}=weekRange(d); return `${fmtISO(start)} → ${fmtISO(end)}`; }

function saveState() {
  try {
    const state = {
      planta: f_planta.value || "",
      q: q.value || "",
      anchor: fmtISO(anchor),
    };
    localStorage.setItem(STATE_KEY, JSON.stringify(state));
  } catch {}
}

function loadState() {
  try {
    const raw = localStorage.getItem(STATE_KEY);
    if (!raw) return;
    const st = JSON.parse(raw);
    if (st.planta != null) f_planta.value = st.planta;
    if (st.q != null) q.value = st.q;
    if (st.anchor) {
      const d = new Date(st.anchor);
      if (!isNaN(d.getTime())) anchor = d;
    }
  } catch {}
}

function buildMap(data, startDate) {
  const map = {};
  for (let i = 0; i < 7; i++) map[fmtISO(addDays(startDate, i))] = [];
  for (const it of data.items) {
    const ini = new Date(it.rango.ini), fin = new Date(it.rango.fin);
    for (let d = new Date(ini); d <= fin; d = addDays(d, 1)) {
      const key = fmtISO(d); if (map[key]) map[key].push(it);
    }
  }
  return map;
}

// ---- Pintado sin animación (solo escribe DOM)
function paintGrid(container, startDate, itemsMap, offsetsMap) {
  container.innerHTML = "";
  for (let i = 0; i < 7; i++) {
    const day = addDays(startDate, i);
    const key = fmtISO(day);
    const all = itemsMap[key] || [];
    const off = (offsetsMap[key] || 0) % Math.max(1, all.length);

    const col = document.createElement("div");
    col.className = "day";
    col.innerHTML = `<h3>${day.toLocaleDateString('es-MX',{weekday:'short', day:'2-digit', month:'short'})}</h3>`;

    if (all.length) {
      const doubled = all.concat(all);
      const slice = doubled.slice(off, off + Math.min(PAGE_SIZE, all.length));
      slice.forEach(it=>{
        const el = document.createElement("div");
        el.className = "item";
        const nombre = it.empleado?.nombre_corto || it.empleado?.nombre || "—";
        const numero = it.empleado?.numero ? ` #${it.empleado.numero}` : "";
        const tagTurno = it.empleado?.turno ? `<span class="tag">${it.empleado.turno}</span>`:"";
        const half = it.gozo && (it.gozo%1)!==0 ? `<span class="badge">½</span>`:"";
        el.innerHTML = `<div class="txt">
            <div class="nm">${nombre}</div>
            <small class="meta">${numero}</small>
          </div>${tagTurno}${half}`;
        col.appendChild(el);
      });

      if (all.length > PAGE_SIZE) {
        const totalPages = Math.ceil(all.length / PAGE_SIZE);
        const pageIdx = Math.floor(off / PAGE_SIZE) + 1;
        const pi = document.createElement("div");
        pi.className = "page-indicator";
        pi.textContent = `${pageIdx}/${totalPages}`;
        col.appendChild(pi);
      }
    }

    container.appendChild(col);
  }
}

// ---- Animación: fade-out -> repintar -> fade-in
function animateRepaint(container, repaintFn) {
  container.classList.remove("fade-in");
  container.classList.add("fade-out");
  setTimeout(() => {
    repaintFn();                          // repinta con el nuevo contenido
    requestAnimationFrame(() => {
      container.classList.remove("fade-out");
      container.classList.add("fade-in");
      setTimeout(() => container.classList.remove("fade-in"), FADE_MS);
    });
  }, FADE_MS);
}

// Avanza offsets por “página”
function advanceOffsets(itemsMap, offsetsMap) {
  Object.keys(itemsMap).forEach(key => {
    const len = itemsMap[key]?.length || 0;
    if (len > PAGE_SIZE) offsetsMap[key] = ((offsetsMap[key] || 0) + PAGE_SIZE) % len;
  });
}

// Pide data y dibuja (primer render y al navegar/filtros)
async function fetchAndRender() {
  const w1 = weekRange(anchor);
  const w2 = nextWeekRange(anchor);

  lblAnchor.textContent = anchorLabel(anchor);
  lbl1.textContent = `Semana (${fmtISO(w1.start)} → ${fmtISO(w1.end)})`;
  lbl2.textContent = `Semana siguiente (${fmtISO(w2.start)} → ${fmtISO(w2.end)})`;

  // Usamos los valores actuales de UI (persistidos) sin resetear
  const params = { planta: f_planta.value, q: q.value };

  const [d1, d2] = await Promise.all([
    API.calendario(fmtISO(w1.start), fmtISO(w1.end), params),
    API.calendario(fmtISO(w2.start), fmtISO(w2.end), params)
  ]);

  itemsByDay1 = buildMap(d1, w1.start);
  itemsByDay2 = buildMap(d2, w2.start);
  // offsets se mantienen si quisieras, pero al recargar datos solemos resetear:
  offsets1 = {}; offsets2 = {};

  // Primer pintado (sin animación)
  paintGrid(grid1, w1.start, itemsByDay1, offsets1);
  paintGrid(grid2, w2.start, itemsByDay2, offsets2);
}

// Render principal
async function render(){ 
  await fetchAndRender(); 
  saveState(); // guarda al terminar cada render (mantiene anchor/planta/q)
}

// Navegación & filtros (guardamos estado al cambiar)
btnPrev.onclick = () => { anchor = addDays(anchor, -7); saveState(); render(); };
btnNext.onclick = () => { anchor = addDays(anchor,  7); saveState(); render(); };
[f_planta, q].forEach(el => el.addEventListener('input', () => { saveState(); render(); }));

// Rotación periódica (no resetea filtros/anchor)
function startRotation() {
  if (rotateTimer) clearInterval(rotateTimer);
  rotateTimer = setInterval(() => {
    const w1 = weekRange(anchor);
    const w2 = nextWeekRange(anchor);
    advanceOffsets(itemsByDay1, offsets1);
    advanceOffsets(itemsByDay2, offsets2);
    animateRepaint(grid1, () => paintGrid(grid1, w1.start, itemsByDay1, offsets1));
    animateRepaint(grid2, () => paintGrid(grid2, w2.start, itemsByDay2, offsets2));
  }, ROTATE_MS);
}

// Inicial: restaura estado y arranca
loadState();
render();
startRotation();

// Auto-refresh de datos cada 5 min (mantiene filtros/anchor)
setInterval(async () => {
  await fetchAndRender(); // no tocamos filtros ni anchor
  // no reiniciamos el intervalo de rotación; se mantiene
}, 5*60*1000);
