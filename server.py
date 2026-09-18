import json,os,time,sqlite3,csv,io,threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from urllib.request import Request,urlopen
from urllib.parse import urlparse,parse_qs
from pathlib import Path

HOST="0.0.0.0"; PORT=int(os.environ.get("PORT","10000")); ROOT=Path(__file__).parent/"app"
DEFAULT_GAME_ID=os.environ.get("DEFAULT_GAME_ID","401872932")
DATABASE_URL=os.environ.get("DATABASE_URL","")
COLLECT_SECONDS=max(15,int(os.environ.get("COLLECT_SECONDS","30")))
DBFILE=Path(os.environ.get("GRIDIRON_DB",str(Path(__file__).parent/"gridiron_atlas.db")))
PROVIDER="ESPN_MULTI_SOURCE_FUSION"
LIVE_CACHE={}
LIVE_CACHE_LOCK=threading.Lock()
LIVE_CACHE_SECONDS=2.0

def _load_verified_players():
    try:
        return json.loads((ROOT/"verified_players.json").read_text(encoding="utf-8"))
    except Exception:
        return []

VERIFIED_PLAYERS=_load_verified_players()

def baseline_players_for(teams):
    wanted={str(x).upper() for x in teams if x}
    return [{"name":p.get("name"),"team":p.get("team"),"position":p.get("pos"),"unit":p.get("unit"),"baseline":p.get("past"),"source":"EMBEDDED_VERIFIED_BASELINE"} for p in VERIFIED_PLAYERS if str(p.get("team","")).upper() in wanted]
LAST={"scoreboard":None,"collector":None,"error":None,"endpoint":None,"fallback":None}

def fetch(u,label="ESPN"):
    # ESPN's public CDN endpoints are the primary transport. A browser-like
    # header set avoids content-negotiation surprises while keeping credentials out.
    req=Request(u,headers={
        "User-Agent":"Mozilla/5.0 (compatible; GridironAtlas/3.2)",
        "Accept":"application/json,text/plain,*/*",
        "Accept-Language":"en-US,en;q=0.9",
        "Referer":"https://www.espn.com/",
    })
    try:
        with urlopen(req,timeout=12) as r:
            LAST["endpoint"]=label
            return json.loads(r.read().decode())
    except Exception as e:
        LAST["endpoint"]=label
        LAST["error"]=f"{label}: {type(e).__name__}: {e}"
        raise

class Store:
    def __init__(self):
        self.pg=None
        if DATABASE_URL:
            try:
                import psycopg
                self.pg=psycopg
                with self.conn() as c:
                    c.execute("""CREATE TABLE IF NOT EXISTS games(game_id TEXT PRIMARY KEY,payload JSONB,status TEXT,updated BIGINT);
                    CREATE TABLE IF NOT EXISTS snapshots(id BIGSERIAL PRIMARY KEY,game_id TEXT,ts BIGINT,payload JSONB);
                    CREATE INDEX IF NOT EXISTS ix_snap_game ON snapshots(game_id,ts);""")
            except Exception as e:
                LAST["error"]="Postgres fallback: "+str(e); self.pg=None
        if not self.pg:
            c=sqlite3.connect(DBFILE); c.executescript("""CREATE TABLE IF NOT EXISTS games(game_id TEXT PRIMARY KEY,payload TEXT,status TEXT,updated INTEGER);
            CREATE TABLE IF NOT EXISTS snapshots(id INTEGER PRIMARY KEY AUTOINCREMENT,game_id TEXT,ts INTEGER,payload TEXT);
            CREATE INDEX IF NOT EXISTS ix_snap_game ON snapshots(game_id,ts);"""); c.commit(); c.close()
    def conn(self):
        if self.pg:return self.pg.connect(DATABASE_URL,autocommit=True)
        c=sqlite3.connect(DBFILE);c.row_factory=sqlite3.Row;return c
    @property
    def kind(self):return "POSTGRES" if self.pg else "SQLITE"
    def save(self,g):
        if not g.get("available"):return
        now=int(time.time()); payload=json.dumps(g)
        c=self.conn()
        if self.pg:c.execute("INSERT INTO games VALUES(%s,%s::jsonb,%s,%s) ON CONFLICT(game_id) DO UPDATE SET payload=excluded.payload,status=excluded.status,updated=excluded.updated",(g["id"],payload,g.get("status",""),now))
        else:c.execute("INSERT INTO games VALUES(?,?,?,?) ON CONFLICT(game_id) DO UPDATE SET payload=excluded.payload,status=excluded.status,updated=excluded.updated",(g["id"],payload,g.get("status",""),now))
        snap={"t":now,"status":g.get("status"),"scores":{x["abbr"]:x["score"] for x in g.get("teams",[])},"team_stats":g.get("team_stats",{}),"players":g.get("players",[])}
        rows=self.snaps(g["id"]); prev=rows[-1] if rows else None
        if not prev or prev.get("scores")!=snap["scores"] or prev.get("team_stats")!=snap["team_stats"]:
            if self.pg:c.execute("INSERT INTO snapshots(game_id,ts,payload) VALUES(%s,%s,%s::jsonb)",(g["id"],now,json.dumps(snap)))
            else:c.execute("INSERT INTO snapshots(game_id,ts,payload) VALUES(?,?,?)",(g["id"],now,json.dumps(snap)))
        if not self.pg:c.commit()
        c.close()
    def games(self):
        c=self.conn(); rows=c.execute("SELECT game_id,status,updated,payload FROM games ORDER BY updated DESC").fetchall();c.close()
        out=[]
        for r in rows:
            p=r[3] if self.pg else json.loads(r["payload"])
            if self.pg and isinstance(p,str):p=json.loads(p)
            out.append({"id":r[0] if self.pg else r["game_id"],"status":r[1] if self.pg else r["status"],"updated":r[2] if self.pg else r["updated"],"teams":p.get("teams",[])})
        return out
    def game(self,gid):
        c=self.conn()
        r=c.execute("SELECT payload FROM games WHERE game_id="+("%s" if self.pg else "?"),(gid,)).fetchone();c.close()
        if not r:return None
        p=r[0] if self.pg else r["payload"];return json.loads(p) if isinstance(p,str) else p
    def snaps(self,gid):
        c=self.conn(); rows=c.execute("SELECT payload FROM snapshots WHERE game_id="+("%s" if self.pg else "?")+" ORDER BY ts,id",(gid,)).fetchall();c.close()
        out=[]
        for r in rows:
            p=r[0] if self.pg else r["payload"];out.append(json.loads(p) if isinstance(p,str) else p)
        return out
STORE=Store()
SCORE_CACHE={"key":None,"ts":0,"value":None}
SCORE_CACHE_SECONDS=20

def eastern_day():
    return datetime.now(ZoneInfo("America/New_York")).strftime("%Y%m%d")

def _event_id_from_ref(item):
    if not isinstance(item,dict):return None
    ref=item.get("$ref") or item.get("ref") or ""
    if ref:
        try:return ref.split("/events/",1)[1].split("?",1)[0].split("/",1)[0]
        except Exception:pass
    v=item.get("id")
    return str(v) if v is not None else None

def _team_logo(team):
    """Return a verified ESPN logo URL when the package omits the logo field."""
    if not isinstance(team,dict): return None
    logo=team.get("logo")
    if logo: return logo
    ab=(team.get("abbreviation") or "").strip().lower()
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{ab}.png" if ab else None

def _game_summary_from_package(gid):
    """Build a scoreboard row from the same CDN package used by Game HQ."""
    raw=fetch(f"https://cdn.espn.com/core/nfl/game?xhr=1&gameId={gid}","ESPN_CDN_GAME_DISCOVERY")
    d=raw.get("gamepackageJSON",raw)
    comp=((d.get("header") or {}).get("competitions") or [{}])[0]
    teams=[]
    for c in comp.get("competitors") or []:
        t=c.get("team") or {}
        teams.append({
            "side":c.get("homeAway"),
            "abbr":t.get("abbreviation"),
            "name":t.get("displayName") or t.get("shortDisplayName"),
            "logo":_team_logo(t),
            "score":c.get("score","0")
        })
    st=comp.get("status") or {}; typ=st.get("type") or {}
    return {
        "id":str(gid),
        "date":comp.get("date") or (d.get("header") or {}).get("date"),
        "status":typ.get("shortDetail") or typ.get("description") or "Scheduled",
        "state":typ.get("state") or "pre",
        "completed":bool(typ.get("completed")),
        "period":st.get("period") or 0,
        "teams":teams
    }

def scoreboard(date=None):
    """Discover NFL event IDs with ESPN Core, then hydrate rows from CDN game packages.

    Core's events endpoint returns reference objects rather than the site-scoreboard
    event shape. 3.1 incorrectly parsed those transports as interchangeable.
    """
    day=date or eastern_day()
    cache_key=str(day)
    now=time.time()
    if SCORE_CACHE.get("key")==cache_key and SCORE_CACHE.get("value") is not None and now-SCORE_CACHE.get("ts",0)<SCORE_CACHE_SECONDS:
        return SCORE_CACHE["value"]
    u=f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events?dates={day}&limit=32"
    try:
        raw=fetch(u,"ESPN_CORE_EVENTS")
        ids=[]
        for item in raw.get("items") or []:
            gid=_event_id_from_ref(item)
            if gid and gid not in ids:ids.append(gid)
        games=[]
        errors=[]
        for gid in ids:
            try:games.append(_game_summary_from_package(gid))
            except Exception as e:errors.append(f"{gid}: {type(e).__name__}: {e}")
        LAST["scoreboard"]=int(time.time()); LAST["fallback"]=None
        # A successful Core response with zero items is not a provider error.
        if errors and not games:LAST["error"]="Scoreboard hydration failed: "+errors[0]
        elif games:LAST["error"]=None
        result={"games":games,"source":PROVIDER,"date":day,"event_count":len(ids),"cached":False}
        SCORE_CACHE.update({"key":cache_key,"ts":now,"value":result})
        return result
    except Exception:
        # Preserve archive usability if discovery is temporarily unavailable.
        archived=[]
        for x in STORE.games():
            archived.append({"id":x["id"],"status":x.get("status","Archived"),"teams":x.get("teams",[]),"date":None})
        LAST["fallback"]="archive"
        return {"games":archived,"source":"ARCHIVE_FALLBACK","date":day,"event_count":len(archived)}

def _unwrap_espn(payload):
    if not isinstance(payload,dict): return {}
    return payload.get("gamepackageJSON") or payload.get("content") or payload

def _clock_seconds(v):
    try:
        m,s=str(v).strip().split(":",1); return int(m)*60+int(s)
    except Exception:return 900

def _provider_progress(d):
    """Higher tuple = later game state. Uses football state before HTTP arrival time."""
    comp=((d.get("header") or {}).get("competitions") or [{}])[0]
    st=comp.get("status") or {}; period=int(st.get("period") or 0)
    clock=st.get("displayClock") or (st.get("clock") or {}).get("displayValue") or "15:00"
    elapsed=max(0,900-_clock_seconds(clock))
    newest=0; count=0
    rows=[]
    rows.extend(d.get("plays") or [])
    db=d.get("drives") or {}
    if isinstance(db,dict):
        rows.extend(db.get("previous") or [])
        if isinstance(db.get("current"),dict): rows.append(db["current"])
    for row in rows:
        plays=row.get("plays") if isinstance(row,dict) else None
        candidates=plays if isinstance(plays,list) else [row]
        for play in candidates:
            if not isinstance(play,dict):continue
            if play.get("id"):count+=1
            for key in ("modified","wallclock"):
                val=play.get(key)
                if not val:continue
                try:newest=max(newest,int(datetime.fromisoformat(str(val).replace("Z","+00:00")).timestamp()))
                except Exception:pass
    return (period,elapsed,newest,count)

def _fetch_live_candidates(gid):
    urls={
      "CDN_GAME":f"https://cdn.espn.com/core/nfl/game?xhr=1&gameId={gid}",
      "CDN_PLAYBYPLAY":f"https://cdn.espn.com/core/nfl/playbyplay?xhr=1&gameId={gid}",
      "SITE_SUMMARY":f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={gid}",
    }
    found=[]
    def one(item):
        name,url=item
        raw=fetch(url,"ESPN_"+name)
        d=_unwrap_espn(raw)
        return name,d,_provider_progress(d)
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs=[ex.submit(one,x) for x in urls.items()]
        for f in as_completed(futs):
            try:found.append(f.result())
            except Exception:pass
    return found

def game(gid,save=True):
    gid=str(gid)
    with LIVE_CACHE_LOCK:
        cached=LIVE_CACHE.get(gid)
        if cached and time.time()-cached["ts"]<LIVE_CACHE_SECONDS:
            return cached["value"]
    candidates=_fetch_live_candidates(gid)
    if not candidates:
        archived=STORE.game(gid)
        return archived or {"id":gid,"available":False,"status":"Unavailable","teams":[],"team_stats":{},"players":[],"plays":[],"drives":[],"linescores":{},"source":"ARCHIVE_OR_UNAVAILABLE"}
    # Choose by actual game progress (period + game clock), not by which HTTP request returned last.
    candidates.sort(key=lambda x:x[2],reverse=True)
    chosen_name,d,chosen_progress=candidates[0]
    provider_meta=[{"name":n,"progress":list(pr)} for n,_,pr in candidates]
    # Some specialized responses omit sections. Fill only missing sections from the
    # freshest candidate that contains them; never overwrite a newer live section.
    for key in ("boxscore","drives","plays","scoringPlays","header"):
        if d.get(key):continue
        for _,other,_ in candidates:
            if other.get(key):
                d[key]=other[key];break
    LAST["fallback"]=None
    comp=((d.get("header") or {}).get("competitions") or [{}])[0]
    teams=[]; lines={}; team_id_to_abbr={}
    for c in comp.get("competitors") or []:
        t=c.get("team") or {}; ab=(t.get("abbreviation") or "").upper()
        if t.get("id") is not None: team_id_to_abbr[str(t.get("id"))]=ab
        lines[ab]=[x.get("displayValue",x.get("value")) for x in c.get("linescores") or []]
        teams.append({"side":c.get("homeAway"),"abbr":ab,"name":t.get("displayName") or t.get("shortDisplayName") or ab,"logo":_team_logo(t),"score":c.get("score",0),"color":t.get("color"),"alternateColor":t.get("alternateColor")})
    st=comp.get("status") or {}; typ=st.get("type") or {}
    out={"id":gid,"available":True,"status":typ.get("shortDetail") or typ.get("description") or "Scheduled","state":typ.get("state") or "pre","completed":bool(typ.get("completed")),"period":st.get("period") or 0,"clock":st.get("displayClock") or (st.get("clock") or {}).get("displayValue") or "—","teams":teams,"team_stats":{},"players":[],"plays":[],"drives":[],"scoring_plays":[],"linescores":lines,"source":PROVIDER+":"+chosen_name,"fetched_at":int(time.time())}

    for t in ((d.get("boxscore") or {}).get("teams") or []):
        ab=((t.get("team") or {}).get("abbreviation") or "").upper()
        out["team_stats"][ab]={str(x.get("label") or x.get("name")):x.get("displayValue") for x in t.get("statistics") or []}
    for grp in ((d.get("boxscore") or {}).get("players") or []):
        ab=((grp.get("team") or {}).get("abbreviation") or "").upper()
        for cat in grp.get("statistics") or []:
            labels=cat.get("labels") or []; cname=cat.get("name") or cat.get("label") or "stats"
            for row in cat.get("athletes") or []:
                a=row.get("athlete") or {}
                out["players"].append({"id":a.get("id"),"team":ab,"name":a.get("displayName"),"position":((a.get("position") or {}).get("abbreviation")),"category":cname,"stats":dict(zip(labels,row.get("stats") or []))})

    def play_team(p):
        direct=((p.get("team") or {}).get("abbreviation"))
        if direct: return direct.upper()
        # CDN drive plays frequently omit play.team; teamParticipants identifies offense.
        for tp in p.get("teamParticipants") or []:
            if tp.get("type")=="offense":
                ab=team_id_to_abbr.get(str(tp.get("id")))
                if ab:return ab
        # After a kickoff, end.team is the receiving/possessing team.
        et=((p.get("end") or {}).get("team") or {}).get("id")
        return team_id_to_abbr.get(str(et)) if et is not None else None

    def norm_play(p):
        return {"id":p.get("id"),"clock":(p.get("clock") or {}).get("displayValue"),"period":(p.get("period") or {}).get("number"),"text":p.get("text"),"team":play_team(p),"start":p.get("start"),"end":p.get("end"),"type":((p.get("type") or {}).get("text")),"statYardage":p.get("statYardage"),"scoringPlay":bool(p.get("scoringPlay")),"awayScore":p.get("awayScore"),"homeScore":p.get("homeScore")}

    # ESPN CDN sometimes leaves top-level plays empty while embedding live plays in drives.
    # Merge both sources, deduplicate by play id, then order by sequence/id.
    play_map={}
    for p in d.get("plays") or []:
        if p.get("id"): play_map[str(p.get("id"))]=p

    drive_block=d.get("drives") or {}
    drive_rows=list(drive_block.get("previous") or [])
    current=drive_block.get("current")
    if isinstance(current,dict) and current.get("id") not in {x.get("id") for x in drive_rows}: drive_rows.append(current)
    for x in drive_rows:
        raw_plays=x.get("plays") or []
        if isinstance(raw_plays,list):
            for p in raw_plays:
                if isinstance(p,dict) and p.get("id"): play_map[str(p.get("id"))]=p
        time_raw=x.get("timeElapsed")
        if isinstance(time_raw,dict): drive_time=time_raw.get("displayValue") or time_raw.get("value")
        else: drive_time=time_raw
        play_count=x.get("offensivePlays")
        if play_count is None: play_count=len(raw_plays) if isinstance(raw_plays,list) else raw_plays
        out["drives"].append({"id":x.get("id"),"team":((x.get("team") or {}).get("abbreviation")) or "—","result":x.get("description") or x.get("displayResult") or x.get("result") or "Drive","yards":x.get("yards"),"time":drive_time,"start":x.get("start"),"end":x.get("end"),"plays":play_count})

    def play_order(p):
        seq=p.get("sequenceNumber")
        try:return int(seq)
        except Exception:
            try:return int(str(p.get("id") or "0")[-6:])
            except Exception:return 0
    for p in sorted(play_map.values(), key=play_order)[-400:]: out["plays"].append(norm_play(p))

    for sp in (d.get("scoringPlays") or []):
        out["scoring_plays"].append({"id":sp.get("id"),"clock":(sp.get("clock") or {}).get("displayValue"),"period":(sp.get("period") or {}).get("number"),"text":sp.get("text"),"team":((sp.get("team") or {}).get("abbreviation")),"scoreValue":sp.get("scoreValue"),"awayScore":sp.get("awayScore"),"homeScore":sp.get("homeScore")})

    latest=out["plays"][-1] if out["plays"] else {}
    start=latest.get("start") or {}; end=latest.get("end") or {}
    # End state describes the next live situation after the latest completed play.
    sit=end if end else start
    possession=None
    tid=((sit.get("team") or {}).get("id")) if isinstance(sit,dict) else None
    if tid is not None: possession=team_id_to_abbr.get(str(tid))
    if not possession and isinstance(current,dict): possession=((current.get("team") or {}).get("abbreviation"))
    if not possession: possession=latest.get("team")
    out["situation"]={
        "possession":possession or "—",
        "down":sit.get("down") if sit.get("down") is not None else "—",
        "distance":sit.get("distance") if sit.get("distance") is not None else "—",
        "yardLine":sit.get("possessionText") or sit.get("downDistanceText") or (sit.get("yardLine") if sit.get("yardLine") is not None else "—"),
        "downDistanceText":sit.get("downDistanceText") or sit.get("shortDownDistanceText") or "—",
        "latestPlayId":latest.get("id"),
        "latestPlay":latest.get("text") or "—"
    }
    out["roster_players"]=baseline_players_for([t.get("abbr") for t in teams])
    # Feed freshness is based on the newest provider play timestamp, not request time.
    newest_ts=0
    for rawp in play_map.values():
        for key in ("modified","wallclock"):
            val=rawp.get(key)
            if not val: continue
            try:
                ts=int(datetime.fromisoformat(str(val).replace("Z","+00:00")).timestamp())
                newest_ts=max(newest_ts,ts)
            except Exception: pass
    out["feed_timestamp"]=newest_ts or None
    out["feed_age_seconds"]=max(0,int(time.time())-newest_ts) if newest_ts else None
    out["provider_candidates"]=provider_meta
    if save:STORE.save(out)
    with LIVE_CACHE_LOCK:
        LIVE_CACHE[str(gid)]={"ts":time.time(),"value":out}
    return out

def collect_once():
    sb=scoreboard()
    for g in sb.get("games",[]):
        # Hydrate every discovered game. This avoids a provider-state parsing mismatch
        # preventing live collection when ESPN changes status wording/shape.
        try: game(g["id"], True)
        except Exception as e: LAST["error"]=str(e)
    LAST["collector"]=int(time.time())
def collector():
    while True:
        try:collect_once()
        except Exception as e:LAST["error"]=str(e)
        time.sleep(COLLECT_SECONDS)

def player_index():
    # Start with the verified embedded matchup roster so the Players page is useful
    # before kickoff and even before a game has been archived. Live/archive lines are
    # merged on top without pretending baseline data is live.
    out={}
    for p in VERIFIED_PLAYERS:
        n=p.get("name")
        if not n: continue
        out[n]={"id":None,"name":n,"team":p.get("team"),"position":p.get("pos"),"unit":p.get("unit"),"baseline":p.get("past"),"source":"EMBEDDED_VERIFIED_BASELINE","games":[]}
    for gm in STORE.games():
        g=STORE.game(gm["id"]) or {}
        for p in g.get("players",[]):
            n=p.get("name")
            if not n:continue
            row=out.setdefault(n,{"id":p.get("id"),"name":n,"team":p.get("team"),"position":p.get("position"),"unit":None,"baseline":None,"source":"ARCHIVED_FEED","games":[]})
            if p.get("id"): row["id"]=p.get("id")
            if p.get("team"): row["team"]=p.get("team")
            if p.get("position"): row["position"]=p.get("position")
            row["games"].append({"game_id":g["id"],"status":g.get("status"),"team":p.get("team"),"category":p.get("category"),"stats":p.get("stats")})
    return sorted(out.values(),key=lambda x:(x.get("team") or "",x.get("position") or "",x.get("name") or ""))

def team_index():
    out={}
    for gm in STORE.games():
        g=STORE.game(gm["id"]) or {}
        for t in g.get("teams",[]):
            ab=t.get("abbr");out.setdefault(ab,{"abbr":ab,"name":t.get("name"),"logo":_team_logo(t),"games":[]});out[ab]["games"].append({"game_id":g["id"],"status":g.get("status"),"score":t.get("score"),"team_stats":g.get("team_stats",{}).get(ab,{})})
    return list(out.values())


LEAGUE_CACHE={"ts":0,"value":None}
LEAGUE_CACHE_SECONDS=60

def _stat_value(stats,names):
    wanted={str(x).lower().replace(' ','').replace('-','') for x in names}
    for st in stats or []:
        key=str(st.get('name') or st.get('abbreviation') or st.get('displayName') or '').lower().replace(' ','').replace('-','')
        if key in wanted:return st.get('displayValue',st.get('value'))
    return None

def _standings_feed():
    raw=fetch('https://site.api.espn.com/apis/v2/sports/football/nfl/standings?season=2026','ESPN_STANDINGS')
    rows=[]
    def walk(x):
        if isinstance(x,dict):
            st=x.get('standings')
            if isinstance(st,dict) and isinstance(st.get('entries'),list):
                for e in st['entries']:
                    tm=e.get('team') or {}; stats=e.get('stats') or []
                    wins=_stat_value(stats,['wins']); losses=_stat_value(stats,['losses']); ties=_stat_value(stats,['ties'])
                    rec='—'
                    if wins is not None and losses is not None: rec=f"{wins}-{losses}"+(f"-{ties}" if str(ties) not in ('0','0.0','None') else '')
                    rows.append({'abbr':tm.get('abbreviation'),'name':tm.get('displayName') or tm.get('name'),'logo':_team_logo(tm),'record':rec,'winPct':_stat_value(stats,['winPercent','winpct']),'pointsFor':_stat_value(stats,['pointsFor','pointsfor']),'pointsAgainst':_stat_value(stats,['pointsAgainst','pointsagainst']),'diff':_stat_value(stats,['differential','pointDifferential']),'streak':_stat_value(stats,['streak']),'rank':_stat_value(stats,['playoffSeed','rank'])})
            for v in x.values(): walk(v)
        elif isinstance(x,list):
            for v in x: walk(v)
    walk(raw)
    seen={};
    for r in rows:
        if r.get('abbr'):seen[r['abbr']]=r
    return list(seen.values())

def _leaders_feed():
    raw=fetch('https://site.api.espn.com/apis/site/v3/sports/football/nfl/leaders?season=2026&seasontype=2','ESPN_LEADERS')
    groups=[]
    def athlete_name(x):
        a=x.get('athlete') or x.get('player') or {}
        return a.get('displayName') or a.get('fullName') or x.get('displayName') or x.get('name')
    def walk(x):
        if isinstance(x,dict):
            ls=x.get('leaders')
            if isinstance(ls,list) and ls and any(isinstance(z,dict) and (z.get('athlete') or z.get('player')) for z in ls):
                name=x.get('displayName') or x.get('name') or x.get('abbreviation') or 'Leaders'
                vals=[]
                for z in ls:
                    if not isinstance(z,dict):continue
                    a=z.get('athlete') or z.get('player') or {}; tm=z.get('team') or a.get('team') or {}
                    vals.append({'name':athlete_name(z),'team':tm.get('abbreviation') if isinstance(tm,dict) else tm,'value':z.get('displayValue',z.get('value'))})
                groups.append({'name':name,'leaders':vals})
            for v in x.values():walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(raw)
    # de-duplicate by category name, preserving feed order
    out=[]; seen=set()
    for g in groups:
        k=g['name']
        if k not in seen and g['leaders']:
            seen.add(k);out.append(g)
    return out

def _atlas_team_profiles():
    acc={}
    for gm in STORE.games():
        g=STORE.game(gm['id']) or {}; teams=g.get('teams') or []
        if len(teams)<2:continue
        for t in teams:
            ab=t.get('abbr'); opp=next((x for x in teams if x.get('abbr')!=ab),{})
            if not ab:continue
            r=acc.setdefault(ab,{'abbr':ab,'name':t.get('name'),'logo':t.get('logo'),'games':0,'pf':0,'yards':0,'ya':0,'takeaways':0})
            r['games']+=1;r['pf']+=float(t.get('score') or 0)
            y=_stat_value([{'name':k,'displayValue':v} for k,v in (g.get('team_stats',{}).get(ab,{}) or {}).items()],['Total Yards'])
            oy=_stat_value([{'name':k,'displayValue':v} for k,v in (g.get('team_stats',{}).get(opp.get('abbr'),{}) or {}).items()],['Total Yards'])
            ot=_stat_value([{'name':k,'displayValue':v} for k,v in (g.get('team_stats',{}).get(opp.get('abbr'),{}) or {}).items()],['Turnovers'])
            try:r['yards']+=float(str(y).replace(',',''))
            except:pass
            try:r['ya']+=float(str(oy).replace(',',''))
            except:pass
            try:r['takeaways']+=int(float(str(ot)))
            except:pass
    out=[]
    for r in acc.values():
        n=r['games'] or 1;r['ppg']=r['pf']/n;r['ypg']=r['yards']/n if r['yards'] else None;r['yapg']=r['ya']/n if r['ya'] else None;out.append(r)
    return sorted(out,key=lambda x: (-(x.get('ppg') or 0),x['abbr']))


NFL_ALIGNMENT = {
'AFC East':['BUF','MIA','NE','NYJ'],'AFC North':['BAL','CIN','CLE','PIT'],'AFC South':['HOU','IND','JAX','TEN'],'AFC West':['DEN','KC','LV','LAC'],
'NFC East':['DAL','NYG','PHI','WAS'],'NFC North':['CHI','DET','GB','MIN'],'NFC South':['ATL','CAR','NO','TB'],'NFC West':['ARI','LA','SF','SEA']}
ALIGN_BY_TEAM={ab:{'conference':div.split()[0],'division':div} for div,teams in NFL_ALIGNMENT.items() for ab in teams}

def _num(v, default=0.0):
    try:return float(str(v).replace('%','').replace(',',''))
    except:return default

def _league_structure(standings, leaders, profiles):
    by={r.get('abbr'):dict(r) for r in standings if r.get('abbr')}
    prof={r.get('abbr'):r for r in profiles if r.get('abbr')}
    for ab,r in by.items():
        r.update(ALIGN_BY_TEAM.get(ab,{}))
        rec=str(r.get('record') or '0-0').split('-')
        w=_num(rec[0] if rec else 0); l=_num(rec[1] if len(rec)>1 else 0); t=_num(rec[2] if len(rec)>2 else 0)
        gp=max(1,w+l+t); pct=(w+.5*t)/gp
        diff=_num(r.get('diff')); p=prof.get(ab,{})
        # Transparent Atlas Index: record dominates; point differential and verified stored-game efficiency are modest modifiers.
        ypg=_num(p.get('ypg')); yapg=_num(p.get('yapg')); efficiency=(ypg-yapg) if ypg and yapg else 0
        r['atlasIndex']=round(100*pct + max(-15,min(15,diff/gp))*0.8 + max(-10,min(10,efficiency/25)),1)
    # ranks are descriptive Atlas calculations, not external predictions
    power=sorted(by.values(),key=lambda r:(-r.get('atlasIndex',0),-_num(r.get('diff')),r.get('abbr','')))
    for i,r in enumerate(power,1):r['atlasRank']=i
    conferences={}; divisions={}
    for conf in ('AFC','NFC'):
        rows=[r for r in by.values() if r.get('conference')==conf]
        rows.sort(key=lambda r:(-_num(r.get('winPct')),-_num(r.get('diff')),r.get('abbr','')))
        conferences[conf]=rows
    for div,teams in NFL_ALIGNMENT.items():
        rows=[by[x] for x in teams if x in by]
        rows.sort(key=lambda r:(-_num(r.get('winPct')),-_num(r.get('diff')),r.get('abbr','')))
        divisions[div]=rows
    # Team leaders from the season leader feed: preserve provider categories and entries, grouped by team.
    team_leaders={ab:[] for ab in by}
    for group in leaders or []:
        cat=group.get('name') or 'Leader'
        for x in group.get('leaders') or []:
            ab=x.get('team')
            if ab in team_leaders and len(team_leaders[ab])<16:
                team_leaders[ab].append({'category':cat,'name':x.get('name'),'value':x.get('value')})
    return {'alignment':NFL_ALIGNMENT,'conferences':conferences,'divisions':divisions,'power':power,'teamLeaders':team_leaders}

def league_hq():
    now=time.time()
    if LEAGUE_CACHE['value'] and now-LEAGUE_CACHE['ts']<LEAGUE_CACHE_SECONDS:return LEAGUE_CACHE['value']
    standings=[];leaders=[];errors=[]
    try:standings=_standings_feed()
    except Exception as e:errors.append('standings:'+type(e).__name__)
    try:leaders=_leaders_feed()
    except Exception as e:errors.append('leaders:'+type(e).__name__)
    profiles=_atlas_team_profiles(); structure=_league_structure(standings,leaders,profiles)
    out={'season':2026,'standings':standings,'leaders':leaders,'teams':profiles,**structure,'errors':errors,'source':'ESPN_PUBLIC_SEASON_FEEDS+ATLAS_VERIFIED_STORE','updated':int(now)}
    LEAGUE_CACHE.update(ts=now,value=out);return out

def legacy_live():
    g=game(DEFAULT_GAME_ID);out={"game":{"status":g.get("status","Pregame"),"detScore":0,"bufScore":0,"period":g.get("period",0),"clock":g.get("clock","—"),"possession":"—","downDistance":"—","ballSpot":"—"},"plays":g.get("plays",[])[-24:],"team_stats":g.get("team_stats",{}),"players":g.get("players",[]),"linescores":{"DET":g.get("linescores",{}).get("DET",[]),"BUF":g.get("linescores",{}).get("BUF",[])},"drives":g.get("drives",[])[-8:]}
    for t in g.get("teams",[]):
        if t["abbr"]=="DET":out["game"]["detScore"]=t["score"]
        if t["abbr"]=="BUF":out["game"]["bufScore"]=t["score"]
    sit=g.get("situation") or {}
    if out["plays"]:
        p=out["plays"][-1];out["game"]["downDistance"]=(f"{sit.get('down')} & {sit.get('distance')}" if sit.get("down") not in [None,"—"] else (p.get("text") or "")[:42]);out["game"]["ballSpot"]=sit.get("yardLine","—");out["game"]["possession"]=sit.get("possession") or p.get("team") or "—"
    return out

class H(SimpleHTTPRequestHandler):
    def __init__(self,*a,**k):super().__init__(*a,directory=str(ROOT),**k)
    def end_headers(self):
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Referrer-Policy","no-referrer")
        self.send_header("Permissions-Policy","camera=(), microphone=(), geolocation=()")
        self.send_header("X-Frame-Options","SAMEORIGIN")
        super().end_headers()
    def sendj(self,o,status=200):
        b=json.dumps(o).encode();self.send_response(status);self.send_header("Content-Type","application/json");self.send_header("Cache-Control","no-store");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
    def do_GET(self):
        u=urlparse(self.path);q=parse_qs(u.query)
        if u.path=="/api/games":return self.sendj(scoreboard((q.get("date") or [None])[0]))
        if u.path=="/api/game":return self.sendj(game((q.get("id") or [DEFAULT_GAME_ID])[0]))
        if u.path=="/api/archive":return self.sendj({"games":STORE.games(),"database":STORE.kind})
        if u.path in ["/api/history","/api/snapshots"]:
            gid=(q.get("id") or [DEFAULT_GAME_ID])[0];return self.sendj({"id":gid,"snapshots":STORE.snaps(gid)})
        if u.path=="/api/players":return self.sendj({"players":player_index()})
        if u.path=="/api/teams":return self.sendj({"teams":team_index()})
        if u.path=="/api/league":return self.sendj(league_hq())
        if u.path=="/api/health":return self.sendj({"ok":True,"version":"7.0","database":STORE.kind,"provider":PROVIDER,"collector_seconds":COLLECT_SECONDS,"last":LAST})
        if u.path=="/api/collect":return self.sendj({"ok":False,"error":"Manual collection by GET is disabled; collector runs automatically."},405)
        if u.path=="/api/export.csv":
            gid=(q.get("id") or [DEFAULT_GAME_ID])[0];g=game(gid);buf=io.StringIO();w=csv.writer(buf);w.writerow(["team","player","position","category","stat","value"])
            for p in g.get("players",[]):
                for k,v in (p.get("stats") or {}).items():w.writerow([p.get("team"),p.get("name"),p.get("position"),p.get("category"),k,v])
            b=buf.getvalue().encode();self.send_response(200);self.send_header("Content-Type","text/csv");self.send_header("Content-Disposition",f'attachment; filename="gridiron-{gid}.csv"');self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b);return
        if u.path=="/api/live":return self.sendj(legacy_live())
        if u.path=="/":self.path="/index.html"
        super().do_GET()

if __name__=="__main__":
    threading.Thread(target=collector,daemon=True).start()
    ThreadingHTTPServer((HOST,PORT),H).serve_forever()
