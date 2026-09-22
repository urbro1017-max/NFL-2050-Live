
/* ATLAS 5.2 shared runtime */
window.ATLAS52=window.ATLAS52||(()=>{
 const inflight=new Map(),cache=new Map();
 async function getJSON(url,{ttl=12000,force=false}={}){
   const now=Date.now(),hit=cache.get(url);
   if(!force&&hit&&now-hit.t<ttl)return hit.v;
   if(inflight.has(url))return inflight.get(url);
   const p=fetch(url,{cache:"no-store"}).then(async r=>{let x=await r.json();if(!r.ok||x?.ok===false)throw Error(x?.error||`Request failed ${r.status}`);cache.set(url,{t:Date.now(),v:x});return x}).finally(()=>inflight.delete(url));
   inflight.set(url,p);return p
 }
 function clear(prefix=""){for(const k of cache.keys())if(!prefix||k.startsWith(prefix))cache.delete(k)}
 function toast(msg,type="info"){let h=document.getElementById("atlasToasts");if(!h){h=document.createElement("div");h.id="atlasToasts";h.className="atlas-toasts";document.body.appendChild(h)}let n=document.createElement("div");n.className="atlas-toast "+type;n.textContent=msg;h.appendChild(n);requestAnimationFrame(()=>n.classList.add("show"));setTimeout(()=>{n.classList.remove("show");setTimeout(()=>n.remove(),250)},2600)}
 function metric(v){if(v==null||v===""||Number.isNaN(Number(v)))return "—";return v}
 function reduced(){return matchMedia("(prefers-reduced-motion: reduce)").matches}
 return {getJSON,clear,toast,metric,reduced}
})();
