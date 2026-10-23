import {nbaFantasy} from './nba-fantasy.mjs';
import http from 'node:http';
import {readFile, stat} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root=path.join(path.dirname(fileURLToPath(import.meta.url)),'dist');
const port=Number(process.env.PORT||10000);
const cache=new Map();
const MIME={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8','.svg':'image/svg+xml','.png':'image/png','.jpg':'image/jpeg','.webp':'image/webp','.ico':'image/x-icon'};
const send=(res,status,body,type='application/json; charset=utf-8')=>{res.writeHead(status,{'Content-Type':type,'Cache-Control':'no-store'});res.end(body)};
http.createServer(async(req,res)=>{
 try{
  const u=new URL(req.url,'http://localhost');
  if(u.pathname==='/api/fantasy/nba'){
   if(req.method!=='GET')return send(res,405,JSON.stringify({error:'Method not allowed'}));
   const date=u.searchParams.get('date')||new Date().toISOString().slice(0,10).replaceAll('-','');
   if(!/^\d{8}$/.test(date))return send(res,400,JSON.stringify({error:'Date must be YYYYMMDD'}));
   const key='nba-fantasy:'+date,hit=cache.get(key);
   if(hit&&hit.until>Date.now())return send(res,200,hit.body);
   try{const result=await nbaFantasy(date);const body=JSON.stringify(result);cache.set(key,{body,until:Date.now()+300000});return send(res,200,body)}
   catch(e){return send(res,502,JSON.stringify({error:'NBA fantasy data unavailable',detail:e.message}))}
  }
  if(u.pathname==='/api/health'){
   let fantasy={available:false};
   try { const f=JSON.parse(await readFile(path.join(root,'fantasy-data.json'),'utf8')); fantasy={available:true,season:f.season,players:f.players?.length||0,gamesCollected:f.gamesCollected||0,generatedAt:f.generatedAt,failedGames:f.completeness?.failedGames||0,unknownPositions:f.completeness?.unknownPositions||0}; } catch {}
   return send(res,200,JSON.stringify({ok:true,service:'cams-stats',fantasy}));
  }
  if(u.pathname.startsWith('/api/espn/')){
   if(req.method!=='GET')return send(res,405,JSON.stringify({error:'Method not allowed'}));
   const parts=u.pathname.match(/^\/api\/espn\/(site|web)\/(.+)$/);
   if(!parts||!/^apis\/(site\/v2|common\/v3)\/sports\/(football\/nfl|basketball\/nba)\/[a-zA-Z0-9/_-]+$/.test(parts[2]) || (parts[1]==='site'&&!parts[2].startsWith('apis/site/v2/')) || (parts[1]==='web'&&!parts[2].startsWith('apis/common/v3/')))return send(res,400,JSON.stringify({error:'Unsupported sports API route'}));
   const host=parts[1]==='web'?'site.web.api.espn.com':'site.api.espn.com';
   const target=`https://${host}/${parts[2]}${u.search}`;
   const cached=cache.get(target);if(cached&&cached.until>Date.now()){res.writeHead(200,{'Content-Type':'application/json; charset=utf-8','X-Cache':'HIT'});return res.end(cached.body)}
   let upstream;try{upstream=await fetch(target,{headers:{Accept:'application/json','User-Agent':'CamsStats/1.0 (sports statistics viewer)'},signal:AbortSignal.timeout(14000)})}catch(e){return send(res,502,JSON.stringify({error:'Upstream connection failed',detail:e.message}))}
   if(!upstream.ok)return send(res,502,JSON.stringify({error:'Sports data provider unavailable',upstreamStatus:upstream.status}));
   const type=upstream.headers.get('content-type')||'';
   if(!type.includes('json'))return send(res,502,JSON.stringify({error:'Sports data provider returned non-JSON response'}));
   const body=await upstream.text();try{JSON.parse(body)}catch{return send(res,502,JSON.stringify({error:'Sports data provider returned invalid JSON'}))}
   if(body.length<3_000_000){cache.set(target,{body,until:Date.now()+(/scoreboard/.test(target)?30000:180000)});if(cache.size>500)cache.delete(cache.keys().next().value)}
   res.writeHead(200,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'public, max-age=30','X-Cache':'MISS'});return res.end(body);
  }
  if(req.method!=='GET'&&req.method!=='HEAD')return send(res,405,JSON.stringify({error:'Method not allowed'}));
  let requested=decodeURIComponent(u.pathname);if(requested.includes('\0'))return send(res,400,'Bad path','text/plain');
  let filename=path.resolve(root,'.'+requested);if(!filename.startsWith(root+path.sep)&&filename!==root)return send(res,403,'Forbidden','text/plain');
  let info;try{info=await stat(filename)}catch{}
  if(!info?.isFile()){if(path.extname(requested))return send(res,404,JSON.stringify({error:'Asset not found'}));filename=path.join(root,'index.html')}
  const content=await readFile(filename);res.writeHead(200,{'Content-Type':MIME[path.extname(filename)]||'application/octet-stream','Cache-Control':filename.endsWith('index.html')?'no-cache':'public, max-age=300'});res.end(req.method==='HEAD'?undefined:content);
 }catch(e){send(res,500,JSON.stringify({error:'Server error',detail:e.message}))}
}).listen(port,'0.0.0.0',()=>console.log(`CAM'S STATS listening on ${port}`));
