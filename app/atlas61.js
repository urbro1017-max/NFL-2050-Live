
/* ATLAS 6.1 — Integration & Reliability */
window.ATLAS61=window.ATLAS61||(()=>{
 let lastError=0;
 function status(kind,msg){
   let n=document.getElementById("atlasNet61");
   if(!n){n=document.createElement("div");n.id="atlasNet61";n.className="net61";document.body.appendChild(n)}
   n.className="net61 "+kind;n.textContent=msg;
   if(kind==="ok")setTimeout(()=>{if(n.textContent===msg)n.classList.add("hide")},1800)
 }
 addEventListener("offline",()=>status("bad","ATLAS OFFLINE · SHOWING AVAILABLE DATA"));
 addEventListener("online",()=>status("ok","CONNECTION RESTORED"));
 addEventListener("error",e=>{let now=Date.now();if(now-lastError>2500){lastError=now;status("bad","A PANEL HIT AN ERROR · ATLAS IS STILL RUNNING")}});
 addEventListener("unhandledrejection",e=>{let now=Date.now();if(now-lastError>2500){lastError=now;status("bad","A DATA REQUEST FAILED · OTHER PANELS REMAIN ACTIVE")}});
 function cleanup(){try{ATLAS54.stopAll()}catch{}}
 addEventListener("pagehide",cleanup);
 function ask(prompt,button){
   let sport=location.pathname.split("/").filter(Boolean)[0]||"atlas";
   document.dispatchEvent(new CustomEvent("atlas:ask",{detail:{sport,prompt,button}}));
   // Route to the sport AI area when no page-specific listener handles it.
   try{
     if(sport==="nfl"&&typeof go==="function"){go("ai");setTimeout(()=>prefill(prompt),80);return}
     if(sport==="mlb"&&typeof go==="function"){go("ai");setTimeout(()=>prefill(prompt),80);return}
   }catch{}
   ATLAS52.toast("ATLAS AI context prepared","good");
   sessionStorage.setItem("atlasAsk61",prompt);
 }
 function prefill(prompt){
   let q=document.querySelector('textarea,input[placeholder*="Ask"],input[placeholder*="ask"],#aiq,#ask');
   if(q){q.value=prompt;q.dispatchEvent(new Event("input",{bubbles:true}));q.focus()}
 }
 document.addEventListener("click",e=>{let b=e.target.closest?.("[data-atlas-prompt]");if(b)ask(b.dataset.atlasPrompt,b)});
 document.addEventListener("DOMContentLoaded",()=>{let p=sessionStorage.getItem("atlasAsk61");if(p){sessionStorage.removeItem("atlasAsk61");setTimeout(()=>prefill(p),150)}});
 return {status,cleanup,ask,prefill}
})();
