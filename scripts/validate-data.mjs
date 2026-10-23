import fs from 'node:fs/promises';
const path='public/fantasy-data.json';
let data;
try {data=JSON.parse(await fs.readFile(path,'utf8'));}catch(e){console.error(`DATA CHECK: ${path} missing or invalid: ${e.message}`);process.exit(1)}
if(!Number.isInteger(data.season)||!Array.isArray(data.players)||!data.players.length||!Number.isInteger(data.gamesCollected)||data.gamesCollected<1)throw Error('Missing season, completed games or players');
const ids=new Set();let games=0;const eventIds=new Set();const seenPlayerGames=new Set();
for(const p of data.players){if(!p.id||!p.name||!['QB','RB','WR','TE','UNKNOWN'].includes(p.position)||!Array.isArray(p.games)||!p.games.length)throw Error(`Invalid player row: id=${p.id}, name=${p.name}, position=${p.position}, games=${p.games?.length}`);if(ids.has(p.id))throw Error('Duplicate player '+p.id);ids.add(p.id);for(const g of p.games){if(!g.eventId||!Number.isInteger(g.week)||!g.stats||Object.values(g.stats).some(v=>typeof v!=='number'||!Number.isFinite(v)))throw Error(`Invalid game stats for ${p.name} (${p.id}) in event ${g.eventId}`);const key=`${p.id}:${g.eventId}`;if(seenPlayerGames.has(key))throw Error(`Duplicate player-game ${key}`);seenPlayerGames.add(key);games++;eventIds.add(g.eventId)}}
if(eventIds.size !== data.gamesCollected)throw Error(`Game coverage mismatch: ${eventIds.size} unique events vs ${data.gamesCollected} reported`);
if(data.completeness?.expectedCompletedGames !== data.gamesCollected + (data.completeness?.failedGames||0))throw Error('Completed game count mismatch');
if(data.completeness?.failedGames>0)console.warn(`DATA CHECK WARNING: ${data.completeness.failedGames} games failed; rankings are incomplete`);
const unknown=data.players.filter(p=>p.position==='UNKNOWN').length;
if(unknown)console.warn(`DATA CHECK: ${unknown} players have unverified positions; position-filtered rankings exclude them until roster positions are resolved.`);
console.log(`DATA CHECK OK: ${data.players.length} players, ${games} player-game rows, ${data.gamesCollected} completed games, season ${data.season}`);
