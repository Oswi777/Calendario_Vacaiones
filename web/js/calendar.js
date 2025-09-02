const grid1 = document.getElementById("grid_w1");
const grid2 = document.getElementById("grid_w2");
const lbl1 = document.getElementById("lbl_w1");
const lbl2 = document.getElementById("lbl_w2");
const f_planta = document.getElementById("f_planta");
const q = document.getElementById("q");

async function renderWeekGrid(container, start){
  const end = addDays(start,6);
  const data = await API.calendario(fmtISO(start), fmtISO(end), {planta:f_planta.value, q:q.value});
  // preparar map por día
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
  const today = new Date(); // al terminar la semana, esto reubica automáticamente las hileras
  const w1 = weekRange(today);
  const w2 = nextWeekRange(today);
  lbl1.textContent = `Semana actual (${fmtISO(w1.start)} → ${fmtISO(w1.end)})`;
  lbl2.textContent = `Semana siguiente (${fmtISO(w2.start)} → ${fmtISO(w2.end)})`;
  await renderWeekGrid(grid1, w1.start);
  await renderWeekGrid(grid2, w2.start);
}

[f_planta,q].forEach(el=>el.addEventListener('input', ()=>render()));
render();
setInterval(render, 5*60*1000); // auto-refresh cada 5 min
