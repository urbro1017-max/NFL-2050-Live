let deferredPrompt=null;
const btn=document.getElementById('install');
window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();deferredPrompt=e;btn.hidden=false});
btn.addEventListener('click',async()=>{if(!deferredPrompt)return;deferredPrompt.prompt();await deferredPrompt.userChoice;deferredPrompt=null;btn.hidden=true});
window.addEventListener('appinstalled',()=>{btn.hidden=true});
if('serviceWorker' in navigator)window.addEventListener('load',()=>navigator.serviceWorker.register('/sw.js').catch(()=>{}));