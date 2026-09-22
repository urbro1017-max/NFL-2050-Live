
/* ATLAS 5.3 cinematic visualization engine */
window.ATLAS53=window.ATLAS53||(()=>{
 const num=v=>{let n=Number(v);return Number.isFinite(n)?n:null};
 function spark(values,{label="Trend",suffix=""}={}){
   let a=(values||[]).map(num).filter(v=>v!==null);
   if(a.length<2)return `<div class="empty">Trend builds when more verified data arrives.</div>`;
   let W=720,H=180,P=18,mn=Math.min(...a),mx=Math.max(...a);if(mx===mn){mn-=1;mx+=1}
   let X=i=>P+i*(W-P*2)/(a.length-1),Y=v=>H-P-(v-mn)*(H-P*2)/(mx-mn);
   let pts=a.map((v,i)=>`${X(i)},${Y(v)}`).join(" "),area=`${P},${H-P} ${pts} ${W-P},${H-P}`;
   return `<div class="viz53"><div class="vizhead"><b>${label}</b><span>${a.length} VERIFIED POINTS</span></div><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${label}"><defs><linearGradient id="g53" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="currentColor" stop-opacity=".25"/><stop offset="1" stop-color="currentColor" stop-opacity="0"/></linearGradient></defs><polygon class="varea" points="${area}"/><polyline class="vline" points="${pts}"/>${a.map((v,i)=>`<circle class="vdot" cx="${X(i)}" cy="${Y(v)}" r="4"><title>${v}${suffix}</title></circle>`).join("")}</svg><div class="vizrange"><span>${mn}${suffix}</span><span>${mx}${suffix}</span></div></div>`
 }
 function bars(rows,{label="Comparison",name="name",value="value",suffix=""}={}){
   let a=(rows||[]).map(r=>({n:r?.[name],v:num(r?.[value])})).filter(r=>r.n&&r.v!==null).slice(0,12);
   if(!a.length)return `<div class="empty">No verified comparison data available.</div>`;
   let mx=Math.max(...a.map(x=>Math.abs(x.v)),1);
   return `<div class="viz53"><div class="vizhead"><b>${label}</b><span>VERIFIED DATA</span></div><div class="vbars">${a.map(x=>`<div class="vbar"><span>${x.n}</span><div><i style="width:${Math.max(2,Math.abs(x.v)/mx*100)}%"></i></div><b>${x.v}${suffix}</b></div>`).join("")}</div></div>`
 }
 function animateNumber(el,to,duration=650){
   if(!el||ATLAS52.reduced())return;
   let end=num(to);if(end===null)return;let start=0,t0=performance.now();
   const tick=t=>{let p=Math.min(1,(t-t0)/duration),e=1-Math.pow(1-p,3);el.textContent=(start+(end-start)*e).toFixed(Number.isInteger(end)?0:1);if(p<1)requestAnimationFrame(tick)};requestAnimationFrame(tick)
 }
 function morph(container,html){if(!container)return;container.classList.add("morphing53");requestAnimationFrame(()=>{container.innerHTML=html;requestAnimationFrame(()=>container.classList.remove("morphing53"))})}
 return {spark,bars,animateNumber,morph}
})();
