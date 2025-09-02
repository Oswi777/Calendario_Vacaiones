function fmtISO(d){ return d.toISOString().slice(0,10); }
function addDays(d,n){ const x=new Date(d); x.setDate(x.getDate()+n); return x; }
function weekRange(anchor){ // lunes-domingo
  const d=new Date(anchor); const day=(d.getDay()+6)%7;
  const start=addDays(d,-day); return {start, end:addDays(start,6)};
}
function nextWeekRange(anchor){
  const {start} = weekRange(anchor);
  const start2 = addDays(start,7);
  return {start:start2, end:addDays(start2,6)};
}
