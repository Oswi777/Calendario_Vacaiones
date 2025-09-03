const grid1 = document.getElementById("grid_w1");
const grid2 = document.getElementById("grid_w2");
const lbl1 = document.getElementById("lbl_w1");
const lbl2 = document.getElementById("lbl_w2");
const f_planta = document.getElementById("f_planta");
const q = document.getElementById("q");
const btnPrev = document.getElementById("btnPrev");
const btnNext = document.getElementById("btnNext");
const lblAnchor = document.getElementById("lblAnchor");

// "anchor" es la fecha base para la fila 1 (semana ancla).
let anchor = new Date();

function anchorLabel(d){
  const {start, end} = weekRange(d);
  return `${fmtISO(start)} → ${fmtISO(end)}`;
}

async function renderWeekGrid(container, start){
  const end = addDays(start,6);
  const data = await API.calendario(fmtISO(start), fmtISO(end), {planta:f_planta.value, q:q.value});
  const map = {};
  for(let i=0;i<7;i++){ const d=fmtISO(addDays(start,i)); map[d]=[]; }
  for(const it of data.items){
    const ini = new Date(it.rango.ini), fin = new Date(it.rango.fin);
    for(let d=new Date(ini); d<=fin; d=addDays(d,1)){
      const key = fmtISO(d);
      if(map[key]) map[key].push(it);
    }
  }
  container.innerHTML="";
  for(let i=0;i<7;i++){
    const day = addDays(start,i);
    const col = document.createElement("div");
    col.className="day";
    col.innerHTML = `<h3>${day.toLocaleDateString('es-MX',{weekday:'short', day:'2-digit', month:'short'})}</h3>`;
    (map[fmtISO(day)]).forEach(it=>{
      const half = (it.gozo && (it.gozo%1)!==0) ? '<span class="badge">½</span>':'';
      const tagTurno = it.empleado.turno ? `<span class="tag">${it.empleado.turno}</span>`:"";
      col.innerHTML += `<div class="item">
          <img src="${it.empleado.foto_url}">
          <div><div>${it.empleado.nombre_corto}</div><small>#${it.empleado.numero}</small></div>
          ${tagTurno}${half}
        </div>`;
    });
    container.appendChild(col);
  }
}

async function render(){
  const w1 = weekRange(anchor);
  const w2 = nextWeekRange(anchor);
  lblAnchor.textContent = anchorLabel(anchor);
  lbl1.textContent = `Semana (${fmtISO(w1.start)} → ${fmtISO(w1.end)})`;
  lbl2.textContent = `Semana siguiente (${fmtISO(w2.start)} → ${fmtISO(w2.end)})`;
  await renderWeekGrid(grid1, w1.start);
  await renderWeekGrid(grid2, w2.start);
}

btnPrev.onclick = () => { anchor = addDays(anchor, -7); render(); }
btnNext.onclick = () => { anchor = addDays(anchor, 7); render(); }
[f_planta,q].forEach(el=>el.addEventListener('input', ()=>render()));

render();
setInterval(render, 5*60*1000); // auto-refresh
