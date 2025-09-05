function fmtISO(d){ return d.toISOString().slice(0,10); }
function addDays(d,days){ const x=new Date(d); x.setDate(x.getDate()+days); return x; }
function weekRange(d){
  const x = new Date(d); const dow = x.getDay(); // 0=Dom
  const start = addDays(x, -((dow+6)%7)); // lunes
  const end = addDays(start, 6);
  start.setHours(0,0,0,0); end.setHours(0,0,0,0);
  return {start, end};
}
function nextWeekRange(d){ const {end}=weekRange(d); const start=addDays(end,1); return {start, end:addDays(start,6)}; }

async function toggleFullscreen(){
  if (!document.fullscreenElement){
    await document.documentElement.requestFullscreen().catch(()=>{});
  }else{
    await document.exitFullscreen().catch(()=>{});
  }
}
