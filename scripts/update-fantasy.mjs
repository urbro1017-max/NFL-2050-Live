import fs from 'node:fs/promises';

const season = Number(process.env.FANTASY_SEASON || new Date().getFullYear());
const root = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl';
const fallbackRoot = 'https://site.web.api.espn.com/apis/common/v3/sports/football/nfl';
const timeout = Number(process.env.DATA_TIMEOUT_MS || 20000);
async function json(url) {
  const response = await fetch(url, { headers: { Accept: 'application/json' }, signal: AbortSignal.timeout(timeout) });
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${url}`);
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('json')) throw new Error(`Non-JSON response: ${url}`);
  return response.json();
}
const names = {
  passingyards:'passingYards', passingtouchdowns:'passingTouchdowns', interceptions:'interceptions',
  rushingyards:'rushingYards', rushingtouchdowns:'rushingTouchdowns',
  receivingyards:'receivingYards', receivingtouchdowns:'receivingTouchdowns',
  receptions:'receptions', fumbleslost:'fumblesLost', twopointconversions:'twoPointConversions',
  passyds:'passingYards', passtd:'passingTouchdowns', rushyds:'rushingYards',
  rushtd:'rushingTouchdowns', recyds:'receivingYards', rectd:'receivingTouchdowns',
  rec:'receptions', int:'interceptions', twoPt:'twoPointConversions'
};
function norm(s) { return String(s ?? '').toLowerCase().replace(/[^a-z0-9]/g, ''); }
const shortNames = Object.fromEntries(Object.entries(names).map(([k,v])=>[norm(k),v]));
function numeric(v) {
  if (typeof v === 'number') return Number.isFinite(v) ? v : null;
  if (typeof v !== 'string') return null;
  const trimmed = v.trim().replaceAll(',','');
  if (!/^[-+]?\d+(\.\d+)?$/.test(trimmed)) return null;
  return Number(trimmed);
}
function extract(payload, week) {
  const box = payload?.boxscore ?? payload?.gamepackage?.boxscore ?? {};
  const teams = box.players ?? [];
  const result = [];
  for (const team of teams) {
    const byId = new Map();
    for (const category of team.statistics ?? []) {
      const keys = category.keys ?? [];
      const labels = category.labels ?? [];
      const athletes = category.athletes ?? [];
      for (const item of athletes) {
        const athlete = item.athlete ?? item;
        const positionValue = athlete.position ?? item.position ?? athlete.athlete?.position;
        const posRaw = typeof positionValue === 'string' ? positionValue : (positionValue?.abbreviation ?? positionValue?.name ?? positionValue?.displayName ?? '');
        const pos = String(posRaw).toUpperCase();
        // ESPN summary box scores frequently omit position on athlete records.
        // Keep offensive contributors rather than silently discarding every athlete.
        if (pos && !['QB','RB','WR','TE'].includes(pos)) continue;
        const id = String(athlete.id ?? '');
        if (!id) continue;
        let row = byId.get(id);
        if (!row) {
          row = { id, name: athlete.displayName ?? athlete.fullName ?? 'Unknown', position:pos,
            team:team.team?.abbreviation ?? '', headshot:athlete.headshot?.href ?? '', week, stats:{} };
          byId.set(id,row);
        }
        const values = item.stats ?? item.statistics ?? [];
        if (Array.isArray(values)) {
          for (let i=0;i<values.length;i++) {
            const key = (category.name === 'interceptions' || category.name === 'defensive') ? null : (shortNames[norm(keys[i])] ?? shortNames[norm(labels[i])]);
            const value = numeric(values[i]);
            if (key && value !== null) row.stats[key] = value;
          }
        } else if (values && typeof values === 'object') {
          for (const [raw, value] of Object.entries(values)) {
            const key = (category.name === 'interceptions' || category.name === 'defensive') ? null : shortNames[norm(raw)]; const n = numeric(value);
            if (key && n !== null) row.stats[key] = n;
          }
        }
      }
    }
    // Exclude defenders with no fantasy-relevant offensive statistics.
    // Unknown positions are retained and labeled accurately instead of guessed.
    result.push(...[...byId.values()].filter(r => Object.keys(r.stats).some(k =>
      ['passingYards','passingTouchdowns','rushingYards','rushingTouchdowns','receivingYards','receivingTouchdowns','receptions'].includes(k))));
  }
  return { rows: result.filter(p=>Object.keys(p.stats).length>0), diagnostics: {
    teamCount:teams.length, categories:teams.flatMap(t=>(t.statistics??[]).map(s=>({name:s.name,keys:s.keys,labels:s.labels,athletes:s.athletes?.length}))).slice(0,6),
    boxKeys:Object.keys(box), topKeys:Object.keys(payload??{}).slice(0,20)
  }};
}
async function summary(eventId) {
  const urls = [
    `${root}/summary?event=${encodeURIComponent(eventId)}`,
    `${fallbackRoot}/summary?event=${encodeURIComponent(eventId)}&region=us&lang=en&contentorigin=espn`
  ];
  let last;
  for (const url of urls) {
    try { const data=await json(url); if ((data.boxscore?.players??data.gamepackage?.boxscore?.players??[]).length) return data; last=data; }
    catch (e) { last=e; }
  }
  if (last instanceof Error) throw last;
  return last;
}
async function rosterPositions() {
  // Match verified ESPN athlete IDs to positions using official team roster responses.
  // Do not infer a position from game usage or statistics.
  const result = new Map();
  const teamsData = await json(`${root}/teams?limit=100`);
  const teams = (teamsData.sports?.[0]?.leagues?.[0]?.teams ?? []).map(t => t.team).filter(Boolean);
  let failures = 0;
  for (let i=0;i<teams.length;i+=6) {
    await Promise.all(teams.slice(i,i+6).map(async team => {
      try {
        const data = await json(`${root}/teams/${team.id}/roster`);
        for (const entry of data.athletes ?? []) {
          for (const a of (Array.isArray(entry.items) ? entry.items : [entry])) {
            const pos = a.position?.abbreviation?.toUpperCase();
            if (a.id && pos) result.set(String(a.id), {position:pos,team:team.abbreviation,headshot:a.headshot?.href||''});
          }
        }
      } catch(e) { failures++; console.warn(`Roster unavailable for ${team.abbreviation}: ${e.message}`); }
    }));
  }
  console.log(`Roster lookup: ${result.size} athlete IDs across ${teams.length-failures}/${teams.length} teams`);
  return {result, failures, total:teams.length};
}
async function main() {
  const schedule = await json(`${root}/scoreboard?dates=${season}&seasontype=2&limit=350`);
  const events = (schedule.events ?? []).filter(e=>e.status?.type?.completed && e.season?.type !== 3);
  console.log(`Found ${events.length} completed regular-season events for ${season}`);
  if (!events.length) throw Error('No completed games; check FANTASY_SEASON and provider schedule');
  const all = new Map(), failures=[], diagnostics=[];
  let processed=0;
  for (let i=0;i<events.length;i+=5) {
    await Promise.all(events.slice(i,i+5).map(async event=>{
      try {
        const data=await summary(event.id);
        const week=Number(event.week?.number ?? data.header?.competitions?.[0]?.week?.number ?? 0);
        const parsed=extract(data,week);
        if (!parsed.rows.length) {
          failures.push(String(event.id));
          if (diagnostics.length<3) diagnostics.push({eventId:event.id,...parsed.diagnostics});
          return;
        }
        processed++;
        for (const row of parsed.rows) {
          let player=all.get(row.id);
          if (!player) { player={id:row.id,name:row.name,position:row.position,team:row.team,headshot:row.headshot,games:[]}; all.set(row.id,player); }
          player.team=row.team;
          player.games.push({eventId:String(event.id),week:row.week,stats:row.stats});
        }
      } catch(e) { failures.push(String(event.id)); if(diagnostics.length<3) diagnostics.push({eventId:event.id,error:e.message}); }
    }));
  }
  if (diagnostics.length) console.error('Sample parsing diagnostics:',JSON.stringify(diagnostics,null,2));
  if (!all.size) throw Error('No player game statistics parsed. Review diagnostic boxKeys/categories above; ESPN may have changed its API. No fictional dataset will be published.');
  if (failures.length && process.env.ALLOW_PARTIAL_DATA !== '1') throw Error(`${failures.length}/${events.length} games missing parsable stats. Refusing incomplete rankings. Inspect diagnostics; ALLOW_PARTIAL_DATA=1 explicitly permits partial results.`);
  let positions = new Map(), rosterFailures=0, rosterTeams=0;
  try { const roster=await rosterPositions(); positions=roster.result; rosterFailures=roster.failures; rosterTeams=roster.total; }
  catch(e) { console.warn(`Roster enrichment unavailable: ${e.message}`); }
  for(const player of all.values()) {
    const seen=new Set();
    for(const game of player.games) {
      if(seen.has(game.eventId)) throw Error(`Duplicate player-game: ${player.id} event ${game.eventId}`);
      seen.add(game.eventId);
    }
  }
  const players=[...all.values()].map(p=>{
    const verified=positions.get(p.id);
    return {...p,position:verified?.position||p.position||'UNKNOWN',team:verified?.team||p.team,headshot:verified?.headshot||p.headshot,games:p.games.sort((a,b)=>a.week-b.week)};
  });
  // ESPN rosters include positions beyond QB/RB/WR/TE (FB, OL, DB, etc.).
  // Do not mislabel them UNKNOWN or let them invalidate the entire dataset.
  const eligible = new Set(['QB','RB','WR','TE','UNKNOWN']);
  const excluded = players.filter(p => !eligible.has(p.position));
  const fantasyPlayers = players.filter(p => eligible.has(p.position));
  console.log(`Excluded ${excluded.length} verified non-QB/RB/WR/TE players from offensive fantasy rankings (examples: ${[...new Set(excluded.map(p=>p.position))].slice(0,12).join(', ')})`);
  const unknownPositions=fantasyPlayers.filter(p=>p.position==='UNKNOWN').length;
  if(unknownPositions) console.warn(`${unknownPositions} offensive players have no position in ESPN box scores; displayed as UNKNOWN, not guessed.`);
  const out={season,completeness:{expectedCompletedGames:events.length,processedGames:processed,failedGames:failures.length,failedEventIds:failures,rosterTeams,rosterFailures,unknownPositions,excludedNonFantasyPlayers:excluded.length},source:'ESPN NFL box scores',generatedAt:new Date().toISOString(),gamesCollected:processed,players:fantasyPlayers,warning:failures.length?`${failures.length} completed games are missing; rankings incomplete.`:''};
  await fs.mkdir('public',{recursive:true});
  const tmp='public/fantasy-data.json.tmp';
  await fs.writeFile(tmp,JSON.stringify(out));
  await fs.rename(tmp,'public/fantasy-data.json');
  console.log(`Published ${fantasyPlayers.length} fantasy-eligible players from ${processed}/${events.length} games`);
}
main().catch(e=>{console.error('Fantasy refresh failed:',e.message);process.exitCode=1});
