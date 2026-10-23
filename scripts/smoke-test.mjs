import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {spawn} from 'node:child_process';
const pkg=JSON.parse(await readFile('package.json','utf8'));
assert.equal(pkg.scripts.start,'node server.mjs');
assert.match(pkg.scripts['build:with-data'],/data:update/);
assert.match(pkg.scripts['data:update'],/validate-data/);
const source=await readFile('server.mjs','utf8');
assert.match(source,/api\/health/);
assert.match(source,/upstreamStatus/);
for(const file of ['src/main.jsx','src/upgrade.jsx','src/realstats.jsx']) {
 const text=await readFile(file,'utf8');
 assert.match(text,/\/api\/espn\//,`${file} should use the backend proxy`);
}
const child=spawn(process.execPath,['server.mjs'],{env:{...process.env,PORT:'19381'},stdio:'pipe'});
try {
 let ready=false;
 for(let i=0;i<40;i++) { try { const res=await fetch('http://127.0.0.1:19381/api/health'); if(res.ok){const health=await res.json();assert.equal(health.ok,true);ready=true;break} }catch{} await new Promise(r=>setTimeout(r,100)); }
 assert.ok(ready,'Server did not start');
 const blocked=await fetch('http://127.0.0.1:19381/api/espn/site/apis/site/v2/sports/football/nfl/../../../../secret');
 assert.ok([400,403,404].includes(blocked.status));
 const missing=await fetch('http://127.0.0.1:19381/fantasy-data.json');
 assert.ok([200,404].includes(missing.status));
 if(missing.status===404)assert.match(missing.headers.get('content-type')||'',/json/);
 console.log('Smoke tests passed: server, health, route validation, missing data behavior.');
}finally{child.kill()}
