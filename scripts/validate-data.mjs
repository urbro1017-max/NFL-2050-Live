import fs from 'node:fs/promises';
const path='public/fantasy-data.json';
let data;
try {data=JSON.parse(await fs.readFile(path,'utf8'));}catch(e){console.error(`DATA CHECK: ${path} missing or invalid: ${e.message}`);process.exit(1)}
if(!Number.isInteger(data.season)||!Array.isArray(data.players)||!data.players.length||!Number.isInteger(data.gamesCollected)||data.gamesCollected<1)throw Error('Missing season, completed games or players');
const ids=new Set();let games=0;
for(const p of data.players){if(!p.id||!p.name||!['QB','RB','WR','TE'].includes(p.position)||!Array.isArray(p.games)||!p.games.length)throw Error('Invalid player row');if(ids.has(p.id))throw Error('Duplicate player '+p.id);ids.add(p.id);for(const g of p.games){if(!g.eventId||!Number.isInteger(g.week)||!g.stats||Object.values(g.stats).some(v=>!Number.isFinite(v)))throw Error('Invalid game stats for '+p.name);games++}}
if(data.completeness?.failedGames>0)console.warn(`DATA CHECK WARNING: ${data.completeness.failedGames} games failed; rankings are incomplete`);
console.log(`DATA CHECK OK: ${data.players.length} players, ${games} player-game rows, ${data.gamesCollected} completed games, season ${data.season}`);
