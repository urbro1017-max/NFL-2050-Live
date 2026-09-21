import json,os,time,sqlite3,csv,io,threading,re
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
VERSION="68.0"
BUILD_NAME="ATLAS 68.0 NEON VISUAL INTELLIGENCE"
OPENAI_API_KEY=os.environ.get("OPENAI_API_KEY","").strip()
OPENAI_MODEL=os.environ.get("OPENAI_MODEL","gpt-5.4").strip()
OPENAI_TIMEOUT=max(5,int(os.environ.get("OPENAI_TIMEOUT","25")))
DBFILE=Path(os.environ.get("GRIDIRON_DB",str(Path(__file__).parent/"gridiron_atlas.db")))
PROVIDER="ESPN_MULTI_SOURCE_FUSION"
LIVE_CACHE={}
LIVE_CACHE_LOCK=threading.Lock()
LIVE_CACHE_SECONDS=2.0

# 10.1 PRIME — league-wide roster + player profile caches
ROSTER_CACHE={}
ROSTER_CACHE_LOCK=threading.Lock()
ROSTER_CACHE_SECONDS=21600
PROFILE_CACHE={}
PROFILE_CACHE_LOCK=threading.Lock()
PROFILE_CACHE_SECONDS=3600
TEAM_IDS={"ARI":"22","ATL":"1","BAL":"33","BUF":"2","CAR":"29","CHI":"3","CIN":"4","CLE":"5","DAL":"6","DEN":"7","DET":"8","GB":"9","HOU":"34","IND":"11","JAX":"30","KC":"12","LV":"13","LAC":"24","LA":"14","MIA":"15","MIN":"16","NE":"17","NO":"18","NYG":"19","NYJ":"20","PHI":"21","PIT":"23","SF":"25","SEA":"26","TB":"27","TEN":"10","WAS":"28"}
TEAM_ABBR_ALIASES={"LAR":"LA","WSH":"WAS"}
def norm_team_abbr(ab):
    ab=str(ab or "").upper().strip()
    return TEAM_ABBR_ALIASES.get(ab,ab)


def _load_verified_players():
    try:
        return json.loads((ROOT/"verified_players.json").read_text(encoding="utf-8"))
    except Exception:
        return []

VERIFIED_PLAYERS=_load_verified_players()

def baseline_players_for(teams):
    wanted={str(x).upper() for x in teams if x}
    return [{"name":p.get("name"),"team":p.get("team"),"position":p.get("pos"),"unit":p.get("unit"),"baseline":p.get("past"),"source":"EMBEDDED_VERIFIED_BASELINE"} for p in VERIFIED_PLAYERS if str(p.get("team","")).upper() in wanted]
LAST={"scoreboard":None,"collector":None,"error":None,"endpoint":None,"fallback":None,"backfill":None,"backfill_stats":{},"backfill_errors":[]}
BACKFILL_LOCK=threading.Lock()
BACKFILL_LAST_SCAN=0
BACKFILL_SCAN_SECONDS=max(60,int(os.environ.get("BACKFILL_SCAN_SECONDS","90")))
BACKFILL_BATCH=max(1,min(16,int(os.environ.get("BACKFILL_BATCH","12"))))
ARCHIVE_COVERAGE_CACHE={"ts":0,"value":None}
ARCHIVE_COVERAGE_CACHE_SECONDS=120

def fetch(u,label="ESPN"):
    # ESPN's public CDN endpoints are the primary transport. A browser-like
    # header set avoids content-negotiation surprises while keeping credentials out.
    req=Request(u,headers={
        "User-Agent":"Mozilla/5.0 (compatible; GridironAtlas/13.0)",
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
                    CREATE INDEX IF NOT EXISTS ix_snap_game ON snapshots(game_id,ts);
                    CREATE TABLE IF NOT EXISTS player_game_stats(game_id TEXT NOT NULL,player_key TEXT NOT NULL,player_id TEXT,name TEXT,team TEXT,position TEXT,stats JSONB,updated BIGINT,PRIMARY KEY(game_id,player_key));
                    CREATE INDEX IF NOT EXISTS ix_pgs_game ON player_game_stats(game_id);
                    CREATE INDEX IF NOT EXISTS ix_pgs_player ON player_game_stats(player_id);
                    CREATE TABLE IF NOT EXISTS team_game_stats(game_id TEXT NOT NULL,team TEXT NOT NULL,opponent TEXT,points_for INTEGER,points_against INTEGER,result TEXT,stats JSONB,updated BIGINT,PRIMARY KEY(game_id,team));
                    CREATE INDEX IF NOT EXISTS ix_tgs_team ON team_game_stats(team);
                    CREATE TABLE IF NOT EXISTS data_pipeline(game_id TEXT PRIMARY KEY,is_final BOOLEAN,teams_written INTEGER,players_written INTEGER,source TEXT,updated BIGINT,error TEXT);""")
            except Exception as e:
                LAST["error"]="Postgres fallback: "+str(e); self.pg=None
        if not self.pg:
            c=sqlite3.connect(DBFILE); c.executescript("""CREATE TABLE IF NOT EXISTS games(game_id TEXT PRIMARY KEY,payload TEXT,status TEXT,updated INTEGER);
            CREATE TABLE IF NOT EXISTS snapshots(id INTEGER PRIMARY KEY AUTOINCREMENT,game_id TEXT,ts INTEGER,payload TEXT);
            CREATE INDEX IF NOT EXISTS ix_snap_game ON snapshots(game_id,ts);
            CREATE TABLE IF NOT EXISTS player_game_stats(game_id TEXT NOT NULL,player_key TEXT NOT NULL,player_id TEXT,name TEXT,team TEXT,position TEXT,stats TEXT,updated INTEGER,PRIMARY KEY(game_id,player_key));
            CREATE INDEX IF NOT EXISTS ix_pgs_game ON player_game_stats(game_id);
            CREATE INDEX IF NOT EXISTS ix_pgs_player ON player_game_stats(player_id);
                    CREATE TABLE IF NOT EXISTS team_game_stats(game_id TEXT NOT NULL,team TEXT NOT NULL,opponent TEXT,points_for INTEGER,points_against INTEGER,result TEXT,stats JSONB,updated BIGINT,PRIMARY KEY(game_id,team));
                    CREATE INDEX IF NOT EXISTS ix_tgs_team ON team_game_stats(team);
                    CREATE TABLE IF NOT EXISTS data_pipeline(game_id TEXT PRIMARY KEY,is_final BOOLEAN,teams_written INTEGER,players_written INTEGER,source TEXT,updated BIGINT,error TEXT);"""); c.commit(); c.close()
    def conn(self):
        if self.pg:return self.pg.connect(DATABASE_URL,autocommit=True)
        c=sqlite3.connect(DBFILE);c.row_factory=sqlite3.Row;return c
    @property
    def kind(self):return "POSTGRES" if self.pg else "SQLITE"
    def save(self,g):
        if not g.get("available"):return
        # Never let a later sparse provider response destroy a richer archived final.
        # Final-game payloads are the canonical ATLAS database record used by projections.
        try:
            old=self.game(str(g.get("id"))) if g.get("id") else None
        except Exception:
            old=None
        def _final(x):
            return bool(x and (x.get("completed") or str(x.get("state") or "").lower()=="post" or str(x.get("status") or "").lower().startswith("final")))
        if old and _final(old) and _final(g):
            g=dict(g)
            for field in ("players","plays","drives","scoring_plays"):
                if len(old.get(field) or []) > len(g.get(field) or []): g[field]=old.get(field)
            if len(old.get("team_stats") or {}) > len(g.get("team_stats") or {}): g["team_stats"]=old.get("team_stats")
            if len(old.get("linescores") or {}) > len(g.get("linescores") or {}): g["linescores"]=old.get("linescores")
            if len(old.get("roster_players") or []) > len(g.get("roster_players") or []): g["roster_players"]=old.get("roster_players")
            g["archive_preserved_rich_fields"]=True
        now=int(time.time()); payload=json.dumps(g)
        c=self.conn()
        if self.pg:c.execute("INSERT INTO games VALUES(%s,%s::jsonb,%s,%s) ON CONFLICT(game_id) DO UPDATE SET payload=excluded.payload,status=excluded.status,updated=excluded.updated",(g["id"],payload,g.get("status",""),now))
        else:c.execute("INSERT INTO games VALUES(?,?,?,?) ON CONFLICT(game_id) DO UPDATE SET payload=excluded.payload,status=excluded.status,updated=excluded.updated",(g["id"],payload,g.get("status",""),now))
        if _final(g):
            if not self.pg: c.commit()
            try:self.ingest_final(g)
            except Exception as e: LAST["final_ingest_error"]=f"{type(e).__name__}: {e}"
        snap={"t":now,"status":g.get("status"),"scores":{x["abbr"]:x["score"] for x in g.get("teams",[])},"team_stats":g.get("team_stats",{}),"players":g.get("players",[])}
        rows=self.snaps(g["id"]); prev=rows[-1] if rows else None
        if not prev or prev.get("scores")!=snap["scores"] or prev.get("team_stats")!=snap["team_stats"]:
            if self.pg:c.execute("INSERT INTO snapshots(game_id,ts,payload) VALUES(%s,%s,%s::jsonb)",(g["id"],now,json.dumps(snap)))
            else:c.execute("INSERT INTO snapshots(game_id,ts,payload) VALUES(?,?,?)",(g["id"],now,json.dumps(snap)))
        if not self.pg:c.commit()
        c.close()
    def save_player_stats(self,g):
        if not g or not (g.get("completed") or str(g.get("state") or "").lower()=="post"): return 0
        merged={}
        roster={str(r.get("id")):r for r in (g.get("roster_players") or []) if r.get("id") is not None}
        for row in (g.get("players") or []):
            if not isinstance(row,dict): continue
            pid=str(row.get("id")) if row.get("id") is not None else ""
            rm=roster.get(pid) or {}
            name=row.get("name") or rm.get("name")
            team=norm_team_abbr(row.get("team") or rm.get("team"))
            pos=row.get("position") or rm.get("position")
            if not name: continue
            key=pid or (str(name).lower()+"|"+team)
            x=merged.setdefault(key,{"player_id":pid or None,"name":name,"team":team,"position":pos,"categories":{}})
            cat=str(row.get("category") or "Other")
            x["categories"].setdefault(cat,{}).update(row.get("stats") or {})
        if not merged:return 0
        now=int(time.time()); c=self.conn()
        for key,x in merged.items():
            payload=json.dumps(x["categories"])
            vals=(str(g.get("id")),key,x.get("player_id"),x.get("name"),x.get("team"),x.get("position"),payload,now)
            if self.pg:
                c.execute("INSERT INTO player_game_stats(game_id,player_key,player_id,name,team,position,stats,updated) VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s) ON CONFLICT(game_id,player_key) DO UPDATE SET player_id=excluded.player_id,name=excluded.name,team=excluded.team,position=excluded.position,stats=excluded.stats,updated=excluded.updated",vals)
            else:
                c.execute("INSERT INTO player_game_stats(game_id,player_key,player_id,name,team,position,stats,updated) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(game_id,player_key) DO UPDATE SET player_id=excluded.player_id,name=excluded.name,team=excluded.team,position=excluded.position,stats=excluded.stats,updated=excluded.updated",vals)
        if not self.pg:c.commit()
        c.close(); return len(merged)
    def ingest_final(self,g):
        """Single write path for every completed game. Raw provider JSON remains archived,
        while all product features read these normalized rows."""
        if not g or not (g.get("completed") or str(g.get("state") or "").lower()=="post"): return {"teams":0,"players":0}
        gid=str(g.get("id") or ""); now=int(time.time()); teams=g.get("teams") or []
        if not gid or len(teams)<2: return {"teams":0,"players":0}
        c=self.conn(); tw=0
        try:
            for t in teams:
                ab=norm_team_abbr(t.get("abbr")); opp=next((norm_team_abbr(x.get("abbr")) for x in teams if x is not t),"")
                if not ab: continue
                try: pf=int(float(t.get("score") or 0))
                except: pf=0
                ot=next((x for x in teams if x is not t),{})
                try: pa=int(float(ot.get("score") or 0))
                except: pa=0
                result="W" if pf>pa else "L" if pf<pa else "T"
                stats=(g.get("team_stats") or {}).get(ab) or {}
                vals=(gid,ab,opp,pf,pa,result,json.dumps(stats),now)
                if self.pg:c.execute("INSERT INTO team_game_stats(game_id,team,opponent,points_for,points_against,result,stats,updated) VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s) ON CONFLICT(game_id,team) DO UPDATE SET opponent=excluded.opponent,points_for=excluded.points_for,points_against=excluded.points_against,result=excluded.result,stats=excluded.stats,updated=excluded.updated",vals)
                else:c.execute("INSERT INTO team_game_stats(game_id,team,opponent,points_for,points_against,result,stats,updated) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(game_id,team) DO UPDATE SET opponent=excluded.opponent,points_for=excluded.points_for,points_against=excluded.points_against,result=excluded.result,stats=excluded.stats,updated=excluded.updated",vals)
                tw+=1
            if not self.pg:c.commit()
        finally:c.close()
        pw=self.save_player_stats(g)
        c=self.conn(); vals=(gid,True if self.pg else 1,tw,pw,g.get("source"),now,None)
        if self.pg:c.execute("INSERT INTO data_pipeline(game_id,is_final,teams_written,players_written,source,updated,error) VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(game_id) DO UPDATE SET is_final=excluded.is_final,teams_written=excluded.teams_written,players_written=excluded.players_written,source=excluded.source,updated=excluded.updated,error=excluded.error",vals)
        else:c.execute("INSERT INTO data_pipeline(game_id,is_final,teams_written,players_written,source,updated,error) VALUES(?,?,?,?,?,?,?) ON CONFLICT(game_id) DO UPDATE SET is_final=excluded.is_final,teams_written=excluded.teams_written,players_written=excluded.players_written,source=excluded.source,updated=excluded.updated,error=excluded.error",vals);c.commit()
        c.close(); return {"teams":tw,"players":pw}
    def team_game_rows(self,team=None):
        c=self.conn(); sql="SELECT game_id,team,opponent,points_for,points_against,result,stats,updated FROM team_game_stats"; args=()
        if team: sql += " WHERE team="+("%s" if self.pg else "?"); args=(norm_team_abbr(team),)
        sql += " ORDER BY updated,game_id"; rows=c.execute(sql,args).fetchall(); c.close(); out=[]
        for r in rows:
            v=list(r) if self.pg else [r[k] for k in ("game_id","team","opponent","points_for","points_against","result","stats","updated")]
            st=v[6]; st=json.loads(st) if isinstance(st,str) else (st or {})
            out.append({"game_id":v[0],"team":v[1],"opponent":v[2],"points_for":v[3],"points_against":v[4],"result":v[5],"stats":st,"updated":v[7]})
        return out
    def pipeline_rows(self):
        c=self.conn(); rows=c.execute("SELECT game_id,is_final,teams_written,players_written,source,updated,error FROM data_pipeline ORDER BY updated DESC").fetchall(); c.close(); out=[]
        for r in rows:
            v=list(r) if self.pg else [r[k] for k in ("game_id","is_final","teams_written","players_written","source","updated","error")]
            out.append({"game_id":v[0],"final":bool(v[1]),"teams_written":int(v[2] or 0),"players_written":int(v[3] or 0),"source":v[4],"updated":v[5],"error":v[6]})
        return out
    def player_stat_rows(self,game_id=None):
        c=self.conn(); sql="SELECT game_id,player_id,name,team,position,stats,updated FROM player_game_stats"; args=()
        if game_id is not None: sql += " WHERE game_id="+("%s" if self.pg else "?"); args=(str(game_id),)
        sql += " ORDER BY updated DESC"; rows=c.execute(sql,args).fetchall(); c.close(); out=[]
        for r in rows:
            vals=list(r) if self.pg else [r[k] for k in ("game_id","player_id","name","team","position","stats","updated")]
            st=vals[5]; st=json.loads(st) if isinstance(st,str) else (st or {})
            out.append({"game_id":vals[0],"id":vals[1],"name":vals[2],"team":vals[3],"position":vals[4],"categories":st,"updated":vals[6]})
        return out
    def player_stat_game_ids(self):
        c=self.conn(); rows=c.execute("SELECT DISTINCT game_id FROM player_game_stats").fetchall(); c.close()
        return {str(r[0] if self.pg else r["game_id"]) for r in rows}

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
WEEK_CACHE={"key":None,"ts":0,"value":None}
WEEK_CACHE_SECONDS=45

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
    # ESPN Core date filters are most reliable as YYYYMMDD. Accept browser YYYY-MM-DD too.
    day=str(day)
    provider_day=day.replace("-","")
    cache_key=provider_day
    now=time.time()
    if SCORE_CACHE.get("key")==cache_key and SCORE_CACHE.get("value") is not None and now-SCORE_CACHE.get("ts",0)<SCORE_CACHE_SECONDS:
        return SCORE_CACHE["value"]
    u=f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events?dates={provider_day}&limit=32"
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


def _scoreboard_event_row(ev):
    comp=((ev.get("competitions") or [{}])[0])
    teams=[]
    for c in comp.get("competitors") or []:
        t=c.get("team") or {}
        records=c.get("records") or []
        rec=next((r.get("summary") for r in records if str(r.get("type") or "").lower() in ("total","overall")),None) or (records[0].get("summary") if records else None)
        teams.append({"side":c.get("homeAway"),"abbr":(t.get("abbreviation") or "").upper(),"name":t.get("displayName") or t.get("shortDisplayName"),"logo":_team_logo(t),"score":c.get("score","0"),"record":rec,"rank":c.get("curatedRank",{}).get("current") if isinstance(c.get("curatedRank"),dict) else None})
    st=comp.get("status") or {}; typ=st.get("type") or {}
    return {"id":str(ev.get("id") or comp.get("id") or ""),"date":ev.get("date") or comp.get("date"),"name":ev.get("name"),"shortName":ev.get("shortName"),"status":typ.get("shortDetail") or typ.get("description") or "Scheduled","state":typ.get("state") or "pre","completed":bool(typ.get("completed")),"period":st.get("period") or 0,"clock":st.get("displayClock") or "—","teams":teams,"venue":((comp.get("venue") or {}).get("fullName")),"season":(ev.get("season") or {}).get("year"),"season_type":(ev.get("season") or {}).get("type"),"week":(ev.get("week") or {}).get("number")}

def week_schedule(season=2026,week=None,seasontype=2):
    season=int(season or 2026); seasontype=int(seasontype or 2)
    key=f"{season}:{seasontype}:{week or 'current'}"; now=time.time()
    if WEEK_CACHE.get("key")==key and WEEK_CACHE.get("value") is not None and now-WEEK_CACHE.get("ts",0)<WEEK_CACHE_SECONDS:return WEEK_CACHE["value"]
    try:
        if week is None:
            raw=fetch("https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard","ESPN_SITE_CURRENT_WEEK")
            meta_week=((raw.get("week") or {}).get("number"))
            meta_season=((raw.get("season") or {}).get("year")) or season
            meta_type=((raw.get("season") or {}).get("type")) or seasontype
            if meta_week: week=int(meta_week); season=int(meta_season); seasontype=int(meta_type)
        url=f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={season}&seasontype={seasontype}&week={int(week)}&limit=32"
        raw=fetch(url,"ESPN_SITE_WEEK")
        games=[_scoreboard_event_row(x) for x in raw.get("events") or []]
        games=[g for g in games if g.get("id")]
        result={"ok":True,"season":season,"season_type":seasontype,"week":int(week),"games":games,"counts":{"live":sum(g["state"]=="in" for g in games),"final":sum(g["completed"] or g["state"]=="post" for g in games),"upcoming":sum(g["state"]=="pre" for g in games)},"source":"ESPN_SITE_WEEK"}
        WEEK_CACHE.update({"key":key,"ts":now,"value":result});return result
    except Exception as e:
        return {"ok":False,"season":season,"season_type":seasontype,"week":week,"games":[],"counts":{"live":0,"final":0,"upcoming":0},"source":"UNAVAILABLE","error":str(e)}

def _kickoff_epoch(v):
    try:return datetime.fromisoformat(str(v).replace("Z","+00:00")).timestamp()
    except Exception:return None

def should_collect_week_game(row):
    state=str(row.get("state") or "pre").lower()
    if state=="in":return True
    if row.get("completed") or state=="post":
        old=STORE.game(str(row.get("id")))
        return not old or not old.get("completed")
    ko=_kickoff_epoch(row.get("date"))
    return bool(ko and -3600 <= ko-time.time() <= 7200)

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

def game(gid,save=True,prefer_archive=True):
    gid=str(gid)
    with LIVE_CACHE_LOCK:
        cached=LIVE_CACHE.get(gid)
        if cached and time.time()-cached["ts"]<LIVE_CACHE_SECONDS:
            return cached["value"]
    # 11.1: completed games are immutable for normal UI reads. Once Atlas has a
    # completed snapshot, serve it from PostgreSQL instead of re-hitting upstream
    # every 2.5 seconds. The collector can pass prefer_archive=False for the one
    # authoritative final capture.
    if prefer_archive:
        archived=STORE.game(gid)
        if archived and (archived.get("completed") or str(archived.get("state") or "").lower()=="post"):
            archived=dict(archived)
            archived["served_from_archive"]=True
            archived["source"]=(archived.get("source") or "ATLAS_ARCHIVE")+":ARCHIVE"
            return archived
    candidates=_fetch_live_candidates(gid)
    if not candidates:
        archived=STORE.game(gid)
        return archived or {"id":gid,"available":False,"status":"Unavailable","teams":[],"team_stats":{},"players":[],"plays":[],"drives":[],"linescores":{},"source":"ARCHIVE_OR_UNAVAILABLE"}
    # Final-state authority comes first. Some ESPN subfeeds can finish with the
    # newest play timestamp while still carrying a stale pre-final header. Prefer
    # any provider candidate that explicitly reports completed/post, then use
    # football progress to break ties. This prevents missed final archives.
    def candidate_final(item):
        _,payload,_=item
        comp=((payload.get("header") or {}).get("competitions") or [{}])[0]
        typ=((comp.get("status") or {}).get("type") or {})
        return bool(typ.get("completed") or str(typ.get("state") or "").lower()=="post")
    finals=[x for x in candidates if candidate_final(x)]
    pool=finals or candidates
    pool.sort(key=lambda x:x[2],reverse=True)
    chosen_name,d,chosen_progress=pool[0]
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
        t=c.get("team") or {}; ab=norm_team_abbr(t.get("abbreviation"))
        if t.get("id") is not None: team_id_to_abbr[str(t.get("id"))]=ab
        lines[ab]=[x.get("displayValue",x.get("value")) for x in c.get("linescores") or []]
        teams.append({"side":c.get("homeAway"),"abbr":ab,"name":t.get("displayName") or t.get("shortDisplayName") or ab,"logo":_team_logo(t),"score":c.get("score",0),"color":t.get("color"),"alternateColor":t.get("alternateColor")})
    st=comp.get("status") or {}; typ=st.get("type") or {}
    out={"id":gid,"available":True,"status":typ.get("shortDetail") or typ.get("description") or "Scheduled","state":typ.get("state") or "pre","completed":bool(typ.get("completed")),"period":st.get("period") or 0,"clock":st.get("displayClock") or (st.get("clock") or {}).get("displayValue") or "—","teams":teams,"team_stats":{},"players":[],"plays":[],"drives":[],"scoring_plays":[],"linescores":lines,"source":PROVIDER+":"+chosen_name,"fetched_at":int(time.time())}

    for t in ((d.get("boxscore") or {}).get("teams") or []):
        ab=norm_team_abbr((t.get("team") or {}).get("abbreviation"))
        out["team_stats"][ab]={str(x.get("label") or x.get("name")):x.get("displayValue") for x in t.get("statistics") or []}
    for grp in ((d.get("boxscore") or {}).get("players") or []):
        ab=norm_team_abbr((grp.get("team") or {}).get("abbreviation"))
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


def hydrate_final_package(gid, persist=True):
    """Authoritative postgame hydration path. It intentionally bypasses the live
    candidate chooser and reads ESPN's completed-game summary directly so a stale
    play-by-play header cannot strand box-score rows outside the database."""
    gid=str(gid)
    fetch_errors=[]; raw=None; source="ESPN_FINAL_SUMMARY"
    for url,label in [
        (f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={gid}","ESPN_FINAL_SUMMARY"),
        (f"https://cdn.espn.com/core/nfl/game?xhr=1&gameId={gid}","ESPN_FINAL_CDN")
    ]:
        try:
            raw=fetch(url,label); source=label; break
        except Exception as e: fetch_errors.append(f"{label}:{type(e).__name__}")
    if raw is None: raise RuntimeError("final hydration failed: "+";".join(fetch_errors))
    d=_unwrap_espn(raw)
    comp=((d.get("header") or {}).get("competitions") or [{}])[0]
    status=(comp.get("status") or {}).get("type") or {}
    teams=[]; team_stats={}; players=[]; lines={}
    for c in comp.get("competitors") or []:
        t=c.get("team") or {}; ab=norm_team_abbr(t.get("abbreviation"))
        lines[ab]=[x.get("displayValue",x.get("value")) for x in c.get("linescores") or []]
        teams.append({"side":c.get("homeAway"),"abbr":ab,"name":t.get("displayName") or t.get("shortDisplayName") or ab,"logo":_team_logo(t),"score":c.get("score",0),"color":t.get("color"),"alternateColor":t.get("alternateColor")})
    for t in ((d.get("boxscore") or {}).get("teams") or []):
        ab=norm_team_abbr((t.get("team") or {}).get("abbreviation"))
        team_stats[ab]={str(x.get("label") or x.get("name")):x.get("displayValue") for x in t.get("statistics") or [] if (x.get("label") or x.get("name"))}
    for grp in ((d.get("boxscore") or {}).get("players") or []):
        ab=norm_team_abbr((grp.get("team") or {}).get("abbreviation"))
        for cat in grp.get("statistics") or []:
            labels=cat.get("labels") or []; cname=cat.get("name") or cat.get("label") or "stats"
            for row in cat.get("athletes") or []:
                a=row.get("athlete") or {}; vals=row.get("stats") or []
                pos=((a.get("position") or {}).get("abbreviation"))
                if not pos:
                    cl=str(cname).lower()
                    if "pass" in cl: pos="QB"
                    elif "kick" in cl and "return" not in cl: pos="K"
                    elif "punt" in cl and "return" not in cl: pos="P"
                players.append({"id":a.get("id"),"team":ab,"name":a.get("displayName") or a.get("fullName"),"position":pos,"category":cname,"stats":dict(zip(labels,vals))})
    # Schedule discovery is authoritative for Final. For direct hydration we also
    # accept a complete two-team box score, since ESPN occasionally lags type.state.
    complete=bool(status.get("completed") or str(status.get("state") or "").lower()=="post")
    old=STORE.game(gid) or {}
    out={**old,"id":gid,"available":True,"status":status.get("shortDetail") or status.get("description") or old.get("status") or "Final","state":"post" if complete or old.get("completed") else status.get("state") or old.get("state") or "post","completed":bool(complete or old.get("completed")),"teams":teams or old.get("teams") or [],"team_stats":team_stats or old.get("team_stats") or {},"players":players or old.get("players") or [],"linescores":lines or old.get("linescores") or {},"source":source,"fetch_errors":fetch_errors,"fetched_at":int(time.time())}
    if len(out.get("teams") or [])==2 and (out.get("completed") or _is_final_game(old)):
        out["completed"]=True; out["state"]="post"
        if persist: STORE.save(out)
    return out

def normalized_player_aggregates():
    """Aggregate only normalized database rows. AI never reparses raw provider JSON."""
    players={}
    for row in STORE.player_stat_rows():
        key=str(row.get("id") or (str(row.get("name") or "").lower()+"|"+norm_team_abbr(row.get("team"))))
        x=players.setdefault(key,{"id":row.get("id"),"name":row.get("name"),"team":norm_team_abbr(row.get("team")),"position":str(row.get("position") or "").upper(),"games":set(),"categories":{}})
        x["games"].add(str(row.get("game_id")))
        if not x.get("position") and row.get("position"): x["position"]=str(row.get("position")).upper()
        for cat,stats in (row.get("categories") or {}).items():
            dst=x["categories"].setdefault(str(cat),{})
            for label,val in (stats or {}).items():
                u=str(label).upper().strip()
                if any(bad in u for bad in ("AVG","RATE","RTG","QBR","PCT","LONG","LNG","Y/A","Y/C")): continue
                raw=str(val).replace(',','').replace('%','').strip()
                # Composite stats such as CMP/ATT are deliberately not summed.
                if '/' in raw: continue
                try:n=float(raw)
                except:continue
                dst[label]=dst.get(label,0)+n
    out=[]
    for x in players.values():
        x=dict(x); x["games"]=len(x.pop("games")); out.append(x)
    return out

def collect_once():
    # 11.1 Sunday Ready collector. Schedule discovery is cheap; full game hydration
    # is reserved for live games, the kickoff warm-up window, and one final capture.
    wk=week_schedule()
    rows=wk.get("games",[]) if wk.get("ok") else scoreboard().get("games",[])
    stats={"discovered":len(rows),"attempted":0,"succeeded":0,"failed":0,"skipped":0,"live":0,"pregame":0,"final":0}
    errors=[]
    for g in rows:
        state=str(g.get("state") or "pre").lower()
        if state=="in": stats["live"]+=1
        elif g.get("completed") or state=="post": stats["final"]+=1
        else: stats["pregame"]+=1
        if not should_collect_week_game(g):
            stats["skipped"]+=1; continue
        stats["attempted"]+=1
        try:
            # bypass archive only when the schedule says a final still needs capture
            force_final=bool(g.get("completed") or state=="post")
            result=game(g["id"], True, prefer_archive=not force_final)
            # The weekly scoreboard is authoritative for lifecycle state. If it
            # says FINAL but a detailed subfeed still carries a stale header,
            # preserve the detailed package and stamp the verified final state
            # before saving. This is the archive safety net that avoids requiring
            # a user to open every finished game.
            if force_final and result and result.get("available",True) and len(result.get("teams") or [])==2:
                result=dict(result)
                result["completed"]=True
                result["state"]="post"
                result["status"]=g.get("status") or result.get("status") or "Final"
                result["archive_verified_by"]="ESPN_SITE_WEEK"
                STORE.save(result)
                with LIVE_CACHE_LOCK: LIVE_CACHE[str(g["id"])]={"ts":time.time(),"value":result}
            if result and result.get("available",True): stats["succeeded"]+=1
            else:
                stats["failed"]+=1; errors.append(f"{g.get('id')}: unavailable")
        except Exception as e:
            stats["failed"]+=1; errors.append(f"{g.get('id')}: {type(e).__name__}")
    LAST["collector"]=int(time.time())
    LAST["week_collected"]=stats["succeeded"]
    LAST["week_discovered"]=stats["discovered"]
    LAST["collector_stats"]=stats
    LAST["collector_errors"]=errors[-5:]
    # Do not poison the whole app health state for isolated background failures.
    LAST["error"]=("; ".join(errors[-3:]) if errors and stats["succeeded"]==0 and stats["attempted"] else None)
    return stats

def collector():
    while True:
        stats=None
        try:
            stats=collect_once()
            # Historical recovery is automatic and throttled. This is what lets Atlas
            # repair Week 1 / missed finals without the user opening each game.
            backfill_once(False)
            try: repair_player_stats_once(12)
            except Exception as e: LAST["player_stats_repair_error"]=f"{type(e).__name__}: {e}"
        except Exception as e:
            LAST["collector_errors"]=[f"collector: {type(e).__name__}"]
        # Slow down when nothing is live; wake faster during games.
        delay=COLLECT_SECONDS if (stats or {}).get("live") else max(60,COLLECT_SECONDS)
        time.sleep(delay)



def _athlete_ref_id(obj):
    if not isinstance(obj,dict): return None
    if obj.get("id") is not None: return str(obj.get("id"))
    ref=obj.get("$ref") or ""
    if "/athletes/" in ref:
        return ref.split("/athletes/",1)[1].split("?",1)[0].split("/",1)[0]
    return None

def _normalize_roster_athlete(a,team,group=None):
    if not isinstance(a,dict): return None
    pos=a.get("position") or {}
    exp=a.get("experience") or {}
    college=a.get("college") or {}
    hs=a.get("headshot") or {}
    status=a.get("status") or {}
    return {
        "id":_athlete_ref_id(a),
        "name":a.get("fullName") or a.get("displayName") or a.get("name"),
        "team":team,
        "position":pos.get("abbreviation") if isinstance(pos,dict) else pos,
        "position_name":pos.get("displayName") or pos.get("name") if isinstance(pos,dict) else None,
        "jersey":a.get("jersey"),
        "age":a.get("age"),
        "height":a.get("displayHeight"),
        "weight":a.get("displayWeight"),
        "experience":exp.get("years") if isinstance(exp,dict) else exp,
        "college":college.get("name") or college.get("shortName") if isinstance(college,dict) else college,
        "headshot":hs.get("href") if isinstance(hs,dict) else hs,
        "status":status.get("name") or status.get("type") if isinstance(status,dict) else status,
        "group":group,
        "starter":False,
        "depth_rank":None,
        "depth_slot":None,
        "source":"ESPN_ROSTER"
    }

def _roster_items(raw,team):
    out=[]
    for block in raw.get("athletes") or []:
        if isinstance(block,dict) and isinstance(block.get("items"),list):
            group=block.get("position") or block.get("name")
            for a in block.get("items") or []:
                row=_normalize_roster_athlete(a,team,group)
                if row and row.get("name"): out.append(row)
        else:
            row=_normalize_roster_athlete(block,team)
            if row and row.get("name"): out.append(row)
    return out

def _depth_map(raw):
    depth={}
    charts=raw.get("depthCharts") or raw.get("items") or []
    for chart in charts:
        for slot,info in (chart.get("positions") or {}).items():
            pos=info.get("position") or {}
            for entry in info.get("athletes") or []:
                athlete=entry.get("athlete") or {}
                aid=_athlete_ref_id(athlete)
                if not aid: continue
                rank=entry.get("rank")
                old=depth.get(aid)
                if old is None or (rank is not None and (old.get("rank") is None or rank<old.get("rank"))):
                    depth[aid]={"rank":rank,"starter":rank==1,"slot":pos.get("abbreviation") or pos.get("name") or slot,"chart":chart.get("name")}
    return depth

def team_roster(team,force=False):
    team=str(team or "").upper()
    if team not in TEAM_IDS: return {"ok":False,"team":team,"players":[],"error":"Unknown NFL team"}
    now=time.time()
    with ROSTER_CACHE_LOCK:
        c=ROSTER_CACHE.get(team)
        if c and not force and now-c["ts"]<ROSTER_CACHE_SECONDS:return c["value"]
    raw=fetch(f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{TEAM_IDS[team]}/roster","ESPN_TEAM_ROSTER")
    players=_roster_items(raw,team)
    depth={}
    try:
        depthraw=fetch(f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{TEAM_IDS[team]}/depthcharts","ESPN_TEAM_DEPTHCHART")
        depth=_depth_map(depthraw)
    except Exception:
        pass
    for p in players:
        d=depth.get(str(p.get("id"))) or {}
        p["starter"]=bool(d.get("starter"));p["depth_rank"]=d.get("rank");p["depth_slot"]=d.get("slot");p["depth_chart"]=d.get("chart")
    value={"ok":True,"team":team,"players":players,"count":len(players),"starters":sum(1 for p in players if p.get("starter")),"source":"ESPN_ROSTER+DEPTHCHART","updated":int(now)}
    with ROSTER_CACHE_LOCK:ROSTER_CACHE[team]={"ts":now,"value":value}
    return value

def league_rosters():
    rows=[];errors=[]
    with ThreadPoolExecutor(max_workers=8) as ex:
        fut={ex.submit(team_roster,t):t for t in TEAM_IDS}
        for f in as_completed(fut):
            t=fut[f]
            try:
                d=f.result();rows.extend(d.get("players") or [])
                if not d.get("ok"):errors.append(t)
            except Exception:errors.append(t)
    return rows,errors

def _flatten_stats(raw):
    """Normalize ESPN web/core statistic payloads without assuming one schema."""
    out=[]
    def add(cat,label,val,abbr=None,rank=None):
        if label in (None,"") or val in (None,""): return
        out.append({"category":cat or "Season","label":str(label),"value":val,"abbr":abbr,"rank":rank})
    def walk(x,cat=None):
        if isinstance(x,dict):
            here=x.get("displayName") or x.get("name") or x.get("abbreviation") or cat
            stats=x.get("stats")
            # Most common ESPN web schema: category.stats[] objects.
            if isinstance(stats,list):
                for st in stats:
                    if isinstance(st,dict):
                        label=st.get("displayName") or st.get("name") or st.get("abbreviation") or st.get("shortDisplayName")
                        val=st.get("displayValue")
                        if val is None: val=st.get("value")
                        add(here,label,val,st.get("abbreviation"),st.get("rank"))
            # Some core responses pair labels/names with a values array.
            names=x.get("names") or x.get("labels")
            vals=x.get("values")
            if isinstance(names,list) and isinstance(vals,list):
                for i,val in enumerate(vals):
                    label=names[i] if i<len(names) else f"Stat {i+1}"
                    add(here,label,val)
            for k,v in x.items():
                if k not in {"stats","values","names","labels"}: walk(v,here if k in {"categories","splits","statistics"} else cat)
        elif isinstance(x,list):
            for v in x: walk(v,cat)
    walk(raw)
    seen=set();clean=[]
    for x in out:
        k=(str(x.get("category")),str(x.get("label")))
        if k not in seen:
            seen.add(k);clean.append(x)
    return clean[:160]

def _season_stats_102(aid):
    """Legacy 10.2 fallback."""
    attempts=[
      (f"https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{aid}/stats?season=2026&seasontype=2","ESPN_WEB_ATHLETE_STATS_2026"),
      (f"https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{aid}/stats","ESPN_WEB_ATHLETE_STATS"),
      (f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2026/types/2/athletes/{aid}/statistics/0","ESPN_CORE_ATHLETE_STATS_2026"),
      (f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2026/athletes/{aid}/statistics","ESPN_CORE_SEASON_ATHLETE_STATS"),
    ]
    errors=[]
    for url,src in attempts:
        try:
            raw=fetch(url,src); rows=_flatten_stats(raw)
            if rows:return rows,src,errors
        except Exception as e: errors.append(src)
    return [],None,errors

def _game_log(aid):
    attempts=[
      (f"https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{aid}/gamelog?season=2026","ESPN_WEB_GAMELOG_2026"),
      (f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2026/athletes/{aid}/eventlog","ESPN_CORE_EVENTLOG_2026"),
    ]
    for url,src in attempts:
        try:
            raw=fetch(url,src)
            # Keep a compact provider-grounded game-log representation. Frontend can show
            # rows when ESPN supplies event labels plus stat values.
            events=[]
            evmap=raw.get("events") if isinstance(raw,dict) else None
            if isinstance(evmap,dict):
                for eid,e in list(evmap.items())[:24]:
                    if isinstance(e,dict):events.append({"id":str(eid),"label":e.get("name") or e.get("shortName") or e.get("atVs") or str(eid),"date":e.get("gameDate") or e.get("date")})
            elif isinstance(evmap,list):
                for e in evmap[:24]:
                    if isinstance(e,dict):events.append({"id":str(e.get("id") or ""),"label":e.get("name") or e.get("shortName") or "Game","date":e.get("date")})
            # Preserve normalized stats if the gamelog exposes them.
            rows=_flatten_stats(raw)
            if events or rows:return {"events":events,"stats":rows[:80],"source":src}
        except Exception: pass
    return {"events":[],"stats":[],"source":None}

def _captured_player_games(aid,name=None,team=None):
    """Return one normalized Atlas archive row per unique game for a player."""
    rows=[]
    for gm in STORE.games():
        g=STORE.game(gm["id"]) or {}
        for p in g.get("players",[]) or []:
            same_id=aid and str(p.get("id") or "")==str(aid)
            same_name=name and p.get("name")==name and (not team or p.get("team")==team)
            if not (same_id or same_name): continue
            rows.append({"game_id":str(g.get("id") or gm["id"]),"status":g.get("status"),"team":p.get("team"),"category":p.get("category"),"stats":p.get("stats") or {}})
    return _merge_captured_game_rows(rows)

def player_profile(aid):
    aid=str(aid or "")
    if not aid.isdigit():return {"ok":False,"error":"Invalid athlete id"}
    now=time.time()
    with PROFILE_CACHE_LOCK:
        c=PROFILE_CACHE.get(aid)
        if c and now-c["ts"]<PROFILE_CACHE_SECONDS:return c["value"]
    raw=fetch(f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/athletes/{aid}","ESPN_ATHLETE_PROFILE")
    a=raw.get("athlete") if isinstance(raw.get("athlete"),dict) else raw
    # Profile fallback: common/v3 often carries richer bio fields.
    if not isinstance(a,dict) or not (a.get("fullName") or a.get("displayName")):
        try:
            wr=fetch(f"https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{aid}","ESPN_WEB_ATHLETE_PROFILE")
            a=wr.get("athlete") if isinstance(wr.get("athlete"),dict) else wr
        except Exception: a=a if isinstance(a,dict) else {}
    team=(a.get("team") or {}) if isinstance(a,dict) else {}
    pos=(a.get("position") or {}) if isinstance(a,dict) else {}
    exp=(a.get("experience") or {}) if isinstance(a,dict) else {}
    college=(a.get("college") or {}) if isinstance(a,dict) else {}
    hs=(a.get("headshot") or {}) if isinstance(a,dict) else {}
    team_ab=team.get("abbreviation")
    pname=a.get("fullName") or a.get("displayName")
    stats,stats_source,stat_errors,captured_stats,captured_games=_season_stats(aid,pname,team_ab)
    gamelog=_game_log(aid)
    archive_games=_captured_player_games(aid,pname,team_ab)
    depth_row={}
    if team_ab in TEAM_IDS:
        try:
            rd=team_roster(team_ab);depth_row=next((x for x in rd.get("players",[]) if str(x.get("id"))==aid),{})
        except Exception:pass
    value={"ok":True,"player":{"id":aid,"name":a.get("fullName") or a.get("displayName"),"team":team_ab,"team_name":team.get("displayName"),"position":pos.get("abbreviation"),"position_name":pos.get("displayName") or pos.get("name"),"jersey":a.get("jersey"),"age":a.get("age"),"height":a.get("displayHeight"),"weight":a.get("displayWeight"),"experience":exp.get("years") if isinstance(exp,dict) else exp,"college":college.get("name") if isinstance(college,dict) else college,"headshot":hs.get("href") if isinstance(hs,dict) else hs,"birth_place":((a.get("birthPlace") or {}).get("city") if isinstance(a.get("birthPlace"),dict) else None),"starter":bool(depth_row.get("starter")),"depth_rank":depth_row.get("depth_rank"),"depth_slot":depth_row.get("depth_slot"),"stats":stats,"stats_source":stats_source,"stats_status":"verified" if stats else "unavailable","stats_attempt_errors":stat_errors,"captured_stats":captured_stats,"captured_games":captured_games,"archive_games":archive_games,"gamelog":gamelog,"source":"ESPN_ATHLETE_PROFILE+MULTI_SOURCE_STATS+DEPTHCHART"},"updated":int(now)}
    with PROFILE_CACHE_LOCK:PROFILE_CACHE[aid]={"ts":now,"value":value}
    return value

def _merge_captured_game_rows(rows):
    """Collapse ESPN box-score category rows into one logical row per game/player.
    A player can appear once for passing, rushing, receiving, fumbles, etc.; those
    are categories from ONE game, not separate games.
    """
    grouped={}
    for row in rows or []:
        gid=str(row.get("game_id") or "")
        if not gid: continue
        g=grouped.setdefault(gid,{"game_id":gid,"status":row.get("status"),"team":row.get("team"),"categories":{},"stats":{}})
        cat=row.get("category") or "stats"
        stats=row.get("stats") or {}
        g["categories"].setdefault(cat,{}).update(stats)
        for k,v in stats.items(): g["stats"][f"{cat}:{k}"]=v
    return list(grouped.values())

def player_index():
    # 10.8: all active team rosters remain the directory, but archived box-score
    # category rows are collapsed into unique games before reaching the browser.
    out={}
    errors=[]
    try:
        roster_rows,errors=league_rosters()
        for p in roster_rows:
            key=str(p.get("id") or (p.get("team"),p.get("name")))
            out[key]={**p,"games":[]}
    except Exception:
        errors=["league_rosters"]
    if not out:
        for p in VERIFIED_PLAYERS:
            n=p.get("name")
            if n:out[str((p.get("team"),n))]={"id":None,"name":n,"team":p.get("team"),"position":p.get("pos"),"unit":p.get("unit"),"baseline":p.get("past"),"source":"EMBEDDED_VERIFIED_BASELINE","games":[],"starter":False}
    for gm in STORE.games():
        g=STORE.game(gm["id"]) or {}
        for p in g.get("players",[]):
            n=p.get("name");aid=str(p.get("id") or "")
            if not n:continue
            row=out.get(aid) if aid else None
            if row is None: row=next((v for v in out.values() if v.get("name")==n and v.get("team")==p.get("team")),None)
            if row is None:
                key=aid or str((p.get("team"),n));row={"id":p.get("id"),"name":n,"team":p.get("team"),"position":p.get("position"),"source":"ARCHIVED_FEED","games":[],"starter":False};out[key]=row
            row.setdefault("games",[]).append({"game_id":g["id"],"status":g.get("status"),"team":p.get("team"),"category":p.get("category"),"stats":p.get("stats")})
    for row in out.values(): row["games"]=_merge_captured_game_rows(row.get("games"))
    return sorted(out.values(),key=lambda x:(x.get("team") or "",0 if x.get("starter") else 1,x.get("position") or "",x.get("name") or ""))

def team_index():
    # Always return the full 32-team directory. Archived/live data enriches it;
    # a temporary provider outage must not make the Teams screen empty.
    names={"ARI":"Arizona Cardinals","ATL":"Atlanta Falcons","BAL":"Baltimore Ravens","BUF":"Buffalo Bills","CAR":"Carolina Panthers","CHI":"Chicago Bears","CIN":"Cincinnati Bengals","CLE":"Cleveland Browns","DAL":"Dallas Cowboys","DEN":"Denver Broncos","DET":"Detroit Lions","GB":"Green Bay Packers","HOU":"Houston Texans","IND":"Indianapolis Colts","JAX":"Jacksonville Jaguars","KC":"Kansas City Chiefs","LV":"Las Vegas Raiders","LAC":"Los Angeles Chargers","LA":"Los Angeles Rams","MIA":"Miami Dolphins","MIN":"Minnesota Vikings","NE":"New England Patriots","NO":"New Orleans Saints","NYG":"New York Giants","NYJ":"New York Jets","PHI":"Philadelphia Eagles","PIT":"Pittsburgh Steelers","SF":"San Francisco 49ers","SEA":"Seattle Seahawks","TB":"Tampa Bay Buccaneers","TEN":"Tennessee Titans","WAS":"Washington Commanders"}
    logo_ab={"LA":"lar","WAS":"wsh"}
    out={ab:{"abbr":ab,"name":names[ab],"logo":f"https://a.espncdn.com/i/teamlogos/nfl/500/{logo_ab.get(ab,ab.lower())}.png","games":[],"source":"ATLAS_TEAM_DIRECTORY"} for ab in TEAM_IDS}
    for gm in STORE.games():
        g=STORE.game(gm["id"]) or {}
        for t in g.get("teams",[]):
            ab=t.get("abbr")
            if not ab: continue
            row=out.setdefault(ab,{"abbr":ab,"name":t.get("name") or ab,"logo":_team_logo(t),"games":[],"source":"ARCHIVE"})
            row["name"]=t.get("name") or row.get("name"); row["logo"]=_team_logo(t) or row.get("logo")
            row["games"].append({"game_id":g["id"],"status":g.get("status"),"score":t.get("score"),"team_stats":g.get("team_stats",{}).get(ab,{})})
    return sorted(out.values(),key=lambda x:x.get("abbr") or "")


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
                    rows.append({'abbr':norm_team_abbr(tm.get('abbreviation')),'name':tm.get('displayName') or tm.get('name'),'logo':_team_logo(tm),'record':rec,'winPct':_stat_value(stats,['winPercent','winpct']),'pointsFor':_stat_value(stats,['pointsFor','pointsfor']),'pointsAgainst':_stat_value(stats,['pointsAgainst','pointsagainst']),'diff':_stat_value(stats,['differential','pointDifferential']),'streak':_stat_value(stats,['streak']),'rank':_stat_value(stats,['playoffSeed','rank'])})
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
                    vals.append({'name':athlete_name(z),'team':norm_team_abbr(tm.get('abbreviation')) if isinstance(tm,dict) else tm,'value':z.get('displayValue',z.get('value'))})
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
            ab=norm_team_abbr(x.get('team'))
            if ab in team_leaders and len(team_leaders[ab])<16:
                team_leaders[ab].append({'category':cat,'name':x.get('name'),'value':x.get('value')})
    return {'alignment':NFL_ALIGNMENT,'conferences':conferences,'divisions':divisions,'power':power,'teamLeaders':team_leaders}

def _archive_team_season_stats(team):
    team=norm_team_abbr(team); rows=STORE.team_game_rows(team)
    if not rows:return {"ok":False,"team":team,"stats":[],"source":"ATLAS_NORMALIZED_TEAM_GAMES","stored_games":0,"game_ids":[],"updated":int(time.time())}
    totals={}; pf=pa=0
    for g in rows:
        pf+=int(g.get("points_for") or 0); pa+=int(g.get("points_against") or 0)
        for k,v in (g.get("stats") or {}).items():
            raw=str(v).replace(',','').replace('%','').strip()
            try:n=float(raw.split('/')[0])
            except:continue
            key=str(k); totals[key]=totals.get(key,0)+n
    out=[{"category":"ATLAS Data Core","label":"Games Stored","value":len(rows)},{"category":"ATLAS Data Core","label":"Points For","value":pf},{"category":"ATLAS Data Core","label":"Points Against","value":pa},{"category":"ATLAS Data Core","label":"Point Differential","value":pf-pa}]
    for k,v in sorted(totals.items()):out.append({"category":"ATLAS Data Core","label":k,"value":round(v,2) if v%1 else int(v)})
    return {"ok":True,"team":team,"stats":out,"source":"ATLAS_NORMALIZED_TEAM_GAMES","stored_games":len(rows),"game_ids":[x['game_id'] for x in rows],"updated":int(time.time())}

def _team_season_stats(team):
    """Team totals with ATLAS final-game persistence as the durable fallback."""
    team=norm_team_abbr(team)
    if team not in TEAM_IDS:return {"ok":False,"team":team,"stats":[],"error":"Unknown NFL team"}
    archived=_archive_team_season_stats(team)
    # ATLAS 59: completed-game database is the product source of truth. Provider season
    # endpoints are used only until this team has a normalized completed-game sample.
    if archived.get("ok"):
        return archived
    tid=TEAM_IDS[team]
    attempts=[
      (f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2026/types/2/teams/{tid}/statistics","ESPN_CORE_TEAM_STATS_2026"),
      (f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2026/types/2/teams/{tid}/statistics/0","ESPN_CORE_TEAM_STATS_2026_SPLIT0"),
      (f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{tid}?enable=stats","ESPN_SITE_TEAM_STATS_2026"),
    ]
    errs=[]
    for url,src in attempts:
        try:
            raw=fetch(url,src); rows=_flatten_stats(raw)
            if rows:return {"ok":True,"team":team,"stats":rows,"source":src,"archive":archived,"updated":int(time.time())}
        except Exception as e:errs.append(f"{src}:{type(e).__name__}")
    if archived.get("ok"): return {**archived,"errors":errs}
    return {"ok":False,"team":team,"stats":[],"source":None,"archive":archived,"errors":errs,"updated":int(time.time())}

def _core_stat_rows(raw):
    """Normalize the season-scoped Core athlete statistics schema first, then fall back."""
    rows=[]
    cats=((raw.get('splits') or {}).get('categories') or []) if isinstance(raw,dict) else []
    for cat in cats:
        cname=cat.get('displayName') or cat.get('name') or 'Season'
        for st in cat.get('stats') or []:
            if not isinstance(st,dict):continue
            label=st.get('displayName') or st.get('shortDisplayName') or st.get('name') or st.get('abbreviation')
            val=st.get('displayValue')
            if val is None:val=st.get('value')
            if label and val is not None:rows.append({'category':cname,'label':str(label),'value':val,'abbr':st.get('abbreviation'),'rank':st.get('rank')})
    return rows or _flatten_stats(raw)

def _ref_url(obj):
    """Return an ESPN reference URL from the several shapes used by Core."""
    if isinstance(obj,str): return obj
    if isinstance(obj,dict): return obj.get('$ref') or obj.get('ref') or obj.get('href') or ''
    return ''

def _season_year(entry):
    season=entry.get('season') if isinstance(entry,dict) else None
    if isinstance(season,dict):
        for key in ('year','season'):
            try:
                if int(season.get(key))==2026:return 2026
            except Exception:pass
    ref=_ref_url(season)
    if '/seasons/2026' in ref:return 2026
    try:
        if int(entry.get('season'))==2026:return 2026
    except Exception:pass
    return None

def _season_type_of(st,ref=''):
    """Best-effort season type. 2 = NFL regular season."""
    if '/types/2/' in str(ref):return 2
    t=st.get('seasonType') or st.get('typeId') if isinstance(st,dict) else None
    if isinstance(t,dict):t=t.get('id') or t.get('type')
    try:return int(t)
    except Exception:return None

def _statisticslog_refs(aid, errors):
    """Ask Core for its own canonical stat resources; regular-season totals first."""
    try:
        log=fetch(f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/athletes/{aid}/statisticslog","ESPN_CORE_STATISTICSLOG")
    except Exception as e:
        errors.append('ESPN_CORE_STATISTICSLOG:'+type(e).__name__);return []
    ranked=[]
    for entry in (log.get('entries') or []) if isinstance(log,dict) else []:
        if not isinstance(entry,dict) or _season_year(entry)!=2026:continue
        for st in entry.get('statistics') or []:
            if not isinstance(st,dict):continue
            ref=_ref_url(st.get('statistics')) or _ref_url(st)
            if not ref:continue
            ref=ref.replace('http://','https://')
            typ=str(st.get('type') or '').lower()
            stype=_season_type_of(st,ref)
            # canonical regular-season total wins; then any regular-season resource;
            # then any 2026 total. This avoids accidentally selecting postseason/preseason.
            score=(100 if stype==2 else 0)+(20 if typ=='total' else 0)+(5 if '/statistics/0' in ref else 0)
            ranked.append((score,ref))
    ranked.sort(key=lambda x:-x[0])
    seen=set();out=[]
    for _,ref in ranked:
        if ref not in seen:seen.add(ref);out.append(ref)
    return out

def _captured_player_aggregate(aid,name=None,team=None):
    """Aggregate only Atlas-stored FINAL/complete game box-score rows for a player.
    This is deliberately labeled CAPTURED, never presented as a full season total.
    """
    buckets={};games=set()
    for gm in STORE.games():
        g=STORE.game(gm['id']) or {}
        if not any(x in str(g.get('status','')).lower() for x in ('final','complete','closed')):continue
        matched=False
        for p in g.get('players') or []:
            same_id=aid and str(p.get('id') or '')==str(aid)
            same_name=name and p.get('name')==name and (not team or p.get('team')==team)
            if not (same_id or same_name):continue
            matched=True
            cat=p.get('category') or 'Captured'
            for key,val in (p.get('stats') or {}).items():
                label=str(key).split(':')[-1]
                # Add numeric counting stats only. Rates/averages remain game-specific and
                # are intentionally excluded rather than mathematically mis-aggregated.
                try:num=float(str(val).replace(',','').replace('%',''))
                except Exception:continue
                upper=label.upper()
                if any(tok in upper for tok in ('AVG','PCT','%','RATE','RTG','LONG','Y/A','Y/C')):continue
                k=(cat,label);buckets[k]=buckets.get(k,0)+num
            if matched:games.add(str(gm['id']))
    rows=[]
    for (cat,label),val in buckets.items():
        rows.append({'category':cat,'label':label,'value':int(val) if float(val).is_integer() else round(val,2),'abbr':label,'rank':None})
    return rows,len(games)

def _season_stats(aid, name=None, team=None):
    """10.6 Player Data Engine.
    Core statisticslog is the directory of record. Direct endpoints and Web are fallbacks.
    Atlas-captured aggregation is returned separately and never mislabeled as season data.
    """
    errors=[]
    # 1) Follow the provider's canonical 2026 regular-season references first.
    for ref in _statisticslog_refs(aid,errors):
        try:
            raw=fetch(ref,'ESPN_CORE_STATISTICSLOG_REF_2026');rows=_core_stat_rows(raw)
            if rows:return rows,'ESPN CORE · 2026 REGULAR SEASON',errors,[],0
            errors.append('ESPN_CORE_STATISTICSLOG_REF_2026:empty')
        except Exception as e:errors.append('ESPN_CORE_STATISTICSLOG_REF_2026:'+type(e).__name__)
    # 2) Known direct season resources.
    attempts=[
      (f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2026/types/2/athletes/{aid}/statistics/0","ESPN_CORE_REGULAR_SEASON_SPLIT0_2026"),
      (f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2026/types/2/athletes/{aid}/statistics","ESPN_CORE_REGULAR_SEASON_STATS_2026"),
      (f"https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{aid}/stats?season=2026&seasontype=2","ESPN_WEB_ATHLETE_STATS_2026"),
      (f"https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{aid}/overview","ESPN_WEB_ATHLETE_OVERVIEW"),
      (f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/athletes/{aid}/statistics/0","ESPN_CORE_ATHLETE_TOTALS"),
    ]
    for url,src in attempts:
        try:
            raw=fetch(url,src);rows=_core_stat_rows(raw)
            if rows:return rows,('ESPN WEB · 2026' if 'WEB' in src else 'ESPN CORE · 2026'),errors,[],0
            errors.append(src+':empty')
        except Exception as e:errors.append(src+':'+type(e).__name__)
    # 3) Honest local fallback: captured completed games only, separately labeled.
    captured,n=_captured_player_aggregate(aid,name,team)
    return [],None,errors,captured,n

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


def atlas_overview():
    """Small, fast product-level health/coverage payload built from Atlas-owned data."""
    rows=STORE.games()
    finals=[]; live=[]; upcoming=[]; player_ids=set(); player_names=set(); teams=set(); snapshots=0
    last_final=None
    for meta in rows:
        g=STORE.game(str(meta.get("id"))) or {}
        state=str(g.get("state") or "").lower()
        done=bool(g.get("completed") or state=="post" or str(g.get("status") or "").lower().startswith("final"))
        if done: finals.append(g)
        elif state=="in": live.append(g)
        else: upcoming.append(g)
        for t in g.get("teams") or []:
            if t.get("abbr"): teams.add(t.get("abbr"))
        if done:
            for pl in g.get("players") or []:
                if pl.get("id"): player_ids.add(str(pl.get("id")))
                elif pl.get("name"): player_names.add(str(pl.get("name")))
        if done and (last_final is None or int(meta.get("updated") or 0)>int(last_final.get("updated") or 0)):
            last_final={"id":meta.get("id"),"updated":meta.get("updated"),"status":meta.get("status"),"teams":meta.get("teams") or []}
    unique_players=len(player_ids)+len(player_names)
    collector=LAST.get("collector_stats") or {}
    try: ac=archive_coverage()
    except Exception: ac={"expected_finals":len(finals),"archived":len(finals),"missing":0,"partial":0,"weeks":[]}
    return {"ok":True,"version":VERSION,"build":BUILD_NAME,"database":STORE.kind,
            "coverage":{"stored_games":len(rows),"final_games":len(finals),"live_games":len(live),"teams_seen":len(teams),"unique_final_players":unique_players,"unique_final_player_entities":unique_players,"player_coverage_definition":"unique player identities appearing in Atlas final-game box-score rows"},
            "archive_coverage":ac,
            "collector":{"last_run":LAST.get("collector"),**collector,"errors":LAST.get("collector_errors") or []},
            "backfill":{"last_run":LAST.get("backfill"),**(LAST.get("backfill_stats") or {}),"errors":LAST.get("backfill_errors") or []},
            "last_final":last_final,"source":"ATLAS_POSTGRES_ARCHIVE+COLLECTOR_STATE","updated":int(time.time())}

def archive_recent(limit=8):
    # Recent Captures is an archive view, never a schedule/discovery view.
    # Pregame/live rows may exist in the store for resilience, but cannot appear here.
    out=[]
    max_rows=max(1,min(int(limit or 8),24))
    for meta in STORE.games():
        g=STORE.game(str(meta.get("id"))) or {}
        done=bool(g.get("completed") or str(g.get("state") or "").lower()=="post" or str(g.get("status") or "").lower().startswith("final"))
        if not done: continue
        teams=g.get("teams") or []
        out.append({
            "id":g.get("id") or meta.get("id"),"status":g.get("status") or meta.get("status"),
            "state":g.get("state"),"completed":bool(g.get("completed")),"date":g.get("date"),
            "teams":[{"abbr":t.get("abbr"),"name":t.get("name"),"side":t.get("side"),"score":t.get("score"),"logo":t.get("logo")} for t in teams],
            "players":len(g.get("players") or []),"plays":len(g.get("plays") or []),"drives":len(g.get("drives") or []),
            "quality":game_quality(g) if 'game_quality' in globals() else None,
            "updated":meta.get("updated"),"archive_state":"ARCHIVED"
        })
        if len(out)>=max_rows: break
    return out

def game_quality(g):
    if not g:return {"score":0,"label":"NO DATA","checks":{}}
    checks={
        "teams":len(g.get("teams") or [])==2,
        "team_stats":bool(g.get("team_stats")),
        "players":bool(g.get("players")),
        "plays":bool(g.get("plays")),
        "drives":bool(g.get("drives")),
        "final":bool(g.get("completed") or str(g.get("state") or "").lower()=="post")
    }
    weights={"teams":20,"team_stats":20,"players":25,"plays":15,"drives":10,"final":10}
    score=sum(weights[k] for k,v in checks.items() if v)
    label="COMPLETE" if score>=90 else "STRONG" if score>=70 else "PARTIAL" if score>=40 else "LIMITED"
    return {"score":score,"label":label,"checks":checks}


def _is_final_game(g):
    return bool(g and (g.get("completed") or str(g.get("state") or "").lower()=="post" or str(g.get("status") or "").lower().startswith("final")))

def _archive_ready(g):
    """A final is archive-ready when final state + two teams are present.
    Player/team/play completeness is reported separately and never fabricated."""
    return bool(_is_final_game(g) and len(g.get("teams") or [])==2)

def archive_coverage(season=2026, season_type=2, through_week=None, force=False):
    """Compare official discovered final game IDs with Atlas-owned final captures."""
    now=time.time()
    if not force and through_week is None and ARCHIVE_COVERAGE_CACHE.get("value") is not None and now-ARCHIVE_COVERAGE_CACHE.get("ts",0)<ARCHIVE_COVERAGE_CACHE_SECONDS:
        return ARCHIVE_COVERAGE_CACHE["value"]
    if through_week is None:
        cur=week_schedule(season,None,season_type)
        through_week=int(cur.get("week") or 1)
    weeks=[]; total_expected=0; total_archived=0; total_partial=0; missing=[]
    for w in range(1,max(1,int(through_week))+1):
        wk=week_schedule(season,w,season_type)
        finals=[x for x in (wk.get("games") or []) if _is_final_game(x)] if wk.get("ok") else []
        archived=0; partial=0; miss=[]
        for row in finals:
            stored=STORE.game(str(row.get("id"))) or {}
            if _archive_ready(stored):
                archived+=1
                q=game_quality(stored)
                if int(q.get("score") or 0)<70: partial+=1
            else:
                miss.append(str(row.get("id")))
        total_expected+=len(finals); total_archived+=archived; total_partial+=partial; missing.extend(miss)
        weeks.append({"week":w,"expected_finals":len(finals),"archived":archived,"missing":len(miss),"partial":partial,"complete":bool(finals and archived==len(finals))})
    result={"season":int(season),"season_type":int(season_type),"through_week":int(through_week),"expected_finals":total_expected,"archived":total_archived,"missing":len(missing),"partial":total_partial,"weeks":weeks,"missing_game_ids":missing}
    if through_week is not None:
        ARCHIVE_COVERAGE_CACHE.update({"ts":now,"value":result})
    return result

def backfill_once(force=False):
    """Automatically recover completed games Atlas missed while asleep/offline.
    Only provider-confirmed finals are eligible. At most BACKFILL_BATCH games hydrate per scan."""
    global BACKFILL_LAST_SCAN
    now=time.time()
    with BACKFILL_LOCK:
        if not force and BACKFILL_LAST_SCAN and now-BACKFILL_LAST_SCAN<BACKFILL_SCAN_SECONDS:
            return LAST.get("backfill_stats") or {"status":"cooldown"}
        BACKFILL_LAST_SCAN=now
        cov=archive_coverage(force=True)
        queue=list(cov.get("missing_game_ids") or [])[:BACKFILL_BATCH]
        stats={"scanned":cov.get("expected_finals",0),"already_archived":cov.get("archived",0),"queued":len(queue),"captured":0,"failed":0,"remaining":cov.get("missing",0),"through_week":cov.get("through_week"),"batch":BACKFILL_BATCH}
        errors=[]
        for gid in queue:
            try:
                result=game(gid,True,prefer_archive=False)
                if _archive_ready(result): stats["captured"]+=1
                else:
                    stats["failed"]+=1; errors.append(f"{gid}: provider did not return a final package")
            except Exception as e:
                stats["failed"]+=1; errors.append(f"{gid}: {type(e).__name__}")
        stats["remaining"]=max(0,int(stats["remaining"])-int(stats["captured"]))
        LAST["backfill"]=int(time.time()); LAST["backfill_stats"]=stats; LAST["backfill_errors"]=errors[-5:]
        return stats


def rebuild_data_core_once(limit=12,force_fetch=False):
    """Idempotently migrate archived finals, then re-fetch only finals whose player box score is absent."""
    finals=[]; migrated=0; fetched=0; errors=[]
    have=STORE.player_stat_game_ids()
    for m in STORE.games():
        g=STORE.game(str(m.get("id"))) or {}
        if not _is_final_game(g):continue
        gid=str(g.get("id") or m.get("id")); finals.append(gid)
        try:
            res=STORE.ingest_final(g); migrated+=1 if res.get("teams") else 0
        except Exception as e:errors.append(f"{gid}: migrate {type(e).__name__}")
    skill={"QB","RB","FB","WR","TE"}
    positioned={}
    for r in STORE.player_stat_rows():
        if str(r.get("position") or "").upper() in skill: positioned.setdefault(str(r.get("game_id")),0); positioned[str(r.get("game_id"))]+=1
    missing=[gid for gid in finals if gid not in have or positioned.get(gid,0)==0]
    for gid in missing[:max(1,int(limit))]:
        try:
            fresh=hydrate_final_package(gid,True)
            if _is_final_game(fresh):
                res=STORE.ingest_final(fresh); fetched+=1 if res.get("players") else 0
                if not res.get("players"):errors.append(f"{gid}: provider returned no player rows")
        except Exception as e:errors.append(f"{gid}: fetch {type(e).__name__}")
    have2=STORE.player_stat_game_ids()
    return {"finals":len(finals),"migrated":migrated,"missing_before":len(missing),"recovered":fetched,"missing_after":len([x for x in finals if x not in have2]),"errors":errors[-8:]}

def repair_player_stats_once(limit=12):
    return rebuild_data_core_once(limit)

def unified_stats_health():
    pg=postgame_stats()
    teams={}
    for ab in TEAM_IDS:
        d=_archive_team_season_stats(ab)
        teams[ab]={"stored_games":d.get("stored_games",0),"stat_rows":len(d.get("stats") or [])}
    
    pos_counts={}
    for r in STORE.player_stat_rows():
        pos=str(r.get("position") or "UNKNOWN").upper(); pos_counts[pos]=pos_counts.get(pos,0)+1
    return {"ok":True,"version":VERSION,"build":BUILD_NAME,"database":STORE.kind,"postgame":{k:pg.get(k) for k in ("final_games","games_with_player_stats","games_missing_player_stats","player_game_rows")},"player_positions":pos_counts,"pipeline":STORE.pipeline_rows(),"team_game_rows":len(STORE.team_game_rows()),"teams":teams,"teams_with_stored_games":sum(1 for x in teams.values() if x["stored_games"]),"bootstrap":LAST.get("data_core_bootstrap"),"updated":int(time.time())}

def postgame_stats():
    rows=STORE.player_stat_rows(); game_ids=STORE.player_stat_game_ids(); finals=[]
    for m in STORE.games():
        g=STORE.game(str(m.get("id"))) or {}
        if _is_final_game(g): finals.append(str(g.get("id") or m.get("id")))
    def val(st,words):
        for cat,items in (st or {}).items():
            for k,v in (items or {}).items():
                key=re.sub(r'[^A-Z0-9]','',str(k).upper())
                if key in words:
                    try:return float(str(v).replace(',','').replace('%','').split('/')[0])
                    except: pass
        return 0.0
    awards=[]
    for x in rows:
        st=x.get("categories") or {}; pos=str(x.get("position") or '').upper()
        yds=val(st,{"YDS","YARDS"}); td=val(st,{"TD","TDS"}); rec=val(st,{"REC","RECEPTIONS"}); tackles=val(st,{"TOT","TOTAL","TACKLES"}); sacks=val(st,{"SACKS"}); ints=val(st,{"INT","INTERCEPTIONS"})
        score=yds/10+td*6+rec+tackles*1.2+sacks*4+ints*5
        if score>0: awards.append({**x,"impact":round(score,1)})
    awards.sort(key=lambda x:-x["impact"])
    return {"ok":True,"database":STORE.kind,"final_games":len(finals),"games_with_player_stats":len(game_ids & set(finals)),"games_missing_player_stats":len(set(finals)-game_ids),"player_game_rows":len(rows),"rows":rows,"awards":awards[:24],"updated":int(time.time())}

def archive_intelligence():
    """Read-only analytics over Atlas-owned final-game archives. Collector behavior is untouched."""
    games=[]; players={}; teams={}; total_plays=0; total_drives=0
    for meta in STORE.games():
        g=STORE.game(str(meta.get("id"))) or {}
        if not _is_final_game(g): continue
        ts=g.get("teams") or []
        row={"id":str(g.get("id") or meta.get("id")),"date":g.get("date"),"status":g.get("status"),
             "teams":[{"abbr":t.get("abbr"),"name":t.get("name"),"side":t.get("side"),"score":t.get("score"),"logo":t.get("logo")} for t in ts],
             "players":len(g.get("players") or []),"plays":len(g.get("plays") or []),"drives":len(g.get("drives") or []),
             "quality":game_quality(g)}
        games.append(row); total_plays+=row["plays"]; total_drives+=row["drives"]
        for t in ts:
            ab=t.get("abbr")
            if not ab: continue
            x=teams.setdefault(ab,{"abbr":ab,"games":0,"points":0,"points_allowed":0,"wins":0,"losses":0})
            x["games"]+=1
            try: x["points"]+=int(t.get("score") or 0)
            except: pass
            opp=next((z for z in ts if z is not t),None)
            if opp:
                try:
                    a=int(t.get("score") or 0); b=int(opp.get("score") or 0); x["points_allowed"]+=b
                    if a>b:x["wins"]+=1
                    elif a<b:x["losses"]+=1
                except: pass
        roster_meta={str(r.get("id")):r for r in (g.get("roster_players") or []) if r.get("id") is not None}
        normalized=[]
        for nr in STORE.player_stat_rows(str(g.get("id") or meta.get("id"))):
            for cat,stats in (nr.get("categories") or {}).items(): normalized.append({"id":nr.get("id"),"name":nr.get("name"),"team":nr.get("team"),"position":nr.get("position"),"category":cat,"stats":stats})
        for pr in (normalized or g.get("players") or []):
            rid=str(pr.get("id")) if pr.get("id") is not None else None
            rm=roster_meta.get(rid) or {}
            pteam=norm_team_abbr(pr.get("team") or rm.get("team"))
            ppos=pr.get("position") or rm.get("position")
            pname=pr.get("name") or rm.get("name")
            key=str(rid or (pname,pteam))
            x=players.setdefault(key,{"id":pr.get("id") or rm.get("id"),"name":pname,"team":pteam,"position":ppos,"games":set(),"categories":{}})
            if not x.get("position") and pr.get("position"): x["position"]=pr.get("position")
            if not x.get("team") and pr.get("team"): x["team"]=norm_team_abbr(pr.get("team"))
            x["games"].add(row["id"]); cat=str(pr.get("category") or "Other")
            dst=x["categories"].setdefault(cat,{})
            for k,v in (pr.get("stats") or {}).items():
                # Keep raw per-game values available to the client; aggregate only unambiguous counting labels.
                u=str(k).upper().strip(); raw=str(v).replace(',','').replace('%','')
                if any(bad in u for bad in ("AVG","RATE","RTG","QBR","PCT","LONG","LNG","Y/A","Y/C","C/ATT")): continue
                try:n=float(raw)
                except:continue
                dst[k]=dst.get(k,0)+n
    # Data Core team rows are authoritative for team history.
    if STORE.team_game_rows():
        teams={}
        for tr in STORE.team_game_rows():
            ab=norm_team_abbr(tr.get("team")); x=teams.setdefault(ab,{"abbr":ab,"games":0,"points":0,"points_allowed":0,"wins":0,"losses":0})
            x["games"]+=1; x["points"]+=int(tr.get("points_for") or 0); x["points_allowed"]+=int(tr.get("points_against") or 0)
            if tr.get("result")=="W":x["wins"]+=1
            elif tr.get("result")=="L":x["losses"]+=1
    plist=[]
    for x in players.values():
        x=dict(x); x["games"]=len(x["games"]); plist.append(x)
    tlist=list(teams.values())
    for x in tlist:
        n=max(1,x["games"]); x["ppg"]=round(x["points"]/n,1); x["papg"]=round(x["points_allowed"]/n,1); x["diff_per_game"]=round((x["points"]-x["points_allowed"])/n,1)
    games.sort(key=lambda x:str(x.get("date") or ""),reverse=True)
    return {"ok":True,"version":VERSION,"sample":{"final_games":len(games),"players":len(plist),"teams":len(tlist),"plays":total_plays,"drives":total_drives},
            "games":games,"players":plist,"teams":tlist,"source":"ATLAS_FINAL_ARCHIVE_READ_ONLY","updated":int(time.time())}



def archive_trends(team=None):
    """Chronological trends from normalized team-game rows only."""
    team=norm_team_abbr(team) if team else None
    rows=[]
    for tr in STORE.team_game_rows(team):
        rows.append({"game_id":tr.get("game_id"),"date":None,"team":norm_team_abbr(tr.get("team")),"opponent":norm_team_abbr(tr.get("opponent")),"points_for":int(tr.get("points_for") or 0),"points_against":int(tr.get("points_against") or 0),"margin":int(tr.get("points_for") or 0)-int(tr.get("points_against") or 0),"result":tr.get("result"),"plays":0,"drives":0})
    if team:
        for i,r in enumerate(rows):
            w=rows[max(0,i-2):i+1]; r["rolling3_pf"]=round(sum(x["points_for"] for x in w)/len(w),1); r["rolling3_pa"]=round(sum(x["points_against"] for x in w)/len(w),1)
    return {"ok":True,"team":team,"games":rows,"source":"ATLAS_NORMALIZED_TEAM_GAMES","updated":int(time.time())}

def atlas_insights(team=None):
    """Deterministic observations backed only by captured final-game rows."""
    d=archive_trends(team); rows=d["games"]; out=[]
    if not rows:return {"ok":True,"team":d.get("team"),"insights":[],"source":d["source"],"updated":d["updated"]}
    if team:
        last=rows[-1]; out.append({"title":"Latest stored result","text":f"{team} scored {last['points_for']} and allowed {last['points_against']} vs {last['opponent']}.","game_id":last['game_id']})
        hi=max(rows,key=lambda x:x['points_for']); out.append({"title":"Stored scoring high","text":f"{hi['points_for']} points vs {hi['opponent']} is {team}'s highest scoring output in the {len(rows)} archived game sample.","game_id":hi['game_id']})
        if len(rows)>=3:
            w=rows[-3:]; out.append({"title":"Three-game scoring window","text":f"Across the latest 3 stored games, {team} averaged {sum(x['points_for'] for x in w)/3:.1f} points and allowed {sum(x['points_against'] for x in w)/3:.1f}.","game_id":last['game_id']})
            margins=[x['margin'] for x in w]
            if margins[0]<margins[1]<margins[2]: out.append({"title":"Margin trend","text":"Scoring margin improved in each of the latest three stored games.","game_id":last['game_id']})
            elif margins[0]>margins[1]>margins[2]: out.append({"title":"Margin trend","text":"Scoring margin declined in each of the latest three stored games.","game_id":last['game_id']})
    else:
        out.append({"title":"Archive sample","text":f"ATLAS currently holds {len(rows)} team-game rows from completed games.","game_id":rows[-1]['game_id']})
    return {"ok":True,"team":d.get("team"),"insights":out,"source":"ATLAS_DERIVED_FROM_FINAL_ARCHIVE","updated":int(time.time())}


def _record_parts(record):
    parts=str(record or '0-0').split('-')
    try:w=float(parts[0] or 0)
    except:w=0
    try:l=float(parts[1] or 0) if len(parts)>1 else 0
    except:l=0
    try:t=float(parts[2] or 0) if len(parts)>2 else 0
    except:t=0
    return w,l,t

def _clamp(v,lo,hi): return max(lo,min(hi,v))

AI_SNAPSHOT={"ts":0,"value":None,"building":False,"error":None,"duration_ms":None}
AI_SNAPSHOT_LOCK=threading.Lock()
AI_REFRESH_SECONDS=60

TEAM_NAMES_AI={"ARI":"Arizona Cardinals","ATL":"Atlanta Falcons","BAL":"Baltimore Ravens","BUF":"Buffalo Bills","CAR":"Carolina Panthers","CHI":"Chicago Bears","CIN":"Cincinnati Bengals","CLE":"Cleveland Browns","DAL":"Dallas Cowboys","DEN":"Denver Broncos","DET":"Detroit Lions","GB":"Green Bay Packers","HOU":"Houston Texans","IND":"Indianapolis Colts","JAX":"Jacksonville Jaguars","KC":"Kansas City Chiefs","LV":"Las Vegas Raiders","LAC":"Los Angeles Chargers","LA":"Los Angeles Rams","MIA":"Miami Dolphins","MIN":"Minnesota Vikings","NE":"New England Patriots","NO":"New Orleans Saints","NYG":"New York Giants","NYJ":"New York Jets","PHI":"Philadelphia Eagles","PIT":"Pittsburgh Steelers","SF":"San Francisco 49ers","SEA":"Seattle Seahawks","TB":"Tampa Bay Buccaneers","TEN":"Tennessee Titans","WAS":"Washington Commanders"}

def _ai_logo(ab):
    x={"LA":"lar","WAS":"wsh"}.get(ab,ab.lower())
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{x}.png"

def atlas_projection_engine():
    """ATLAS 62: normalized-DB-only model. No raw archive scans and no network calls."""
    team_rows=STORE.team_game_rows()
    player_rows=STORE.player_stat_rows()
    # Aggregate team history in one pass from the normalized table.
    agg={ab:{"games":0,"wins":0,"losses":0,"ties":0,"pf":0,"pa":0,"margins":[]} for ab in TEAM_IDS}
    for r in team_rows:
        ab=norm_team_abbr(r.get("team"))
        if ab not in agg: continue
        a=agg[ab]; a["games"]+=1; a["pf"]+=int(r.get("points_for") or 0); a["pa"]+=int(r.get("points_against") or 0)
        res=r.get("result")
        if res=="W": a["wins"]+=1
        elif res=="L": a["losses"]+=1
        else: a["ties"]+=1
        a["margins"].append(int(r.get("points_for") or 0)-int(r.get("points_against") or 0))
    teams=[]
    for ab in TEAM_IDS:
        a=agg[ab]; gp=a["games"]; w=a["wins"]; l=a["losses"]; t=a["ties"]
        pct=(w+.5*t)/gp if gp else .5
        dpg=(a["pf"]-a["pa"])/gp if gp else 0
        recent=sum(a["margins"][-3:])/len(a["margins"][-3:]) if a["margins"] else dpg
        expected=_clamp(.55*pct+.25*(.5+_clamp(dpg,-14,14)/56)+.20*(.5+_clamp(recent,-14,14)/56),.15,.85)
        remaining=max(0,17-gp); projected=w+.5*t+remaining*expected
        teams.append({"abbr":ab,"name":TEAM_NAMES_AI.get(ab,ab),"logo":_ai_logo(ab),"record":f"{w}-{l}"+(f"-{t}" if t else ""),"games_played":gp,"wins":w,"losses":l,"ties":t,"point_diff":a["pf"]-a["pa"],"diff_per_game":round(dpg,2),"recent_margin":round(recent,2),"strength":round(expected*100,1),"expected_win_rate":round(expected*100,1),"projected_wins":round(projected,1),"projected_losses":round(17-projected,1),"remaining":remaining,"record_source":"normalized_db"})
    teams.sort(key=lambda x:(-x["strength"],-x["projected_wins"],x["abbr"]))
    for i,x in enumerate(teams,1):x["projection_rank"]=i
    strength={x["abbr"]:x for x in teams}

    # Aggregate players from the already-loaded normalized rows. One DB query total.
    pp={}
    for row in player_rows:
        key=str(row.get("id") or (str(row.get("name") or "").lower()+"|"+norm_team_abbr(row.get("team"))))
        x=pp.setdefault(key,{"id":row.get("id"),"name":row.get("name"),"team":norm_team_abbr(row.get("team")),"position":str(row.get("position") or "").upper(),"games":set(),"categories":{}})
        x["games"].add(str(row.get("game_id")))
        if not x["position"] and row.get("position"):x["position"]=str(row.get("position")).upper()
        for cat,stats in (row.get("categories") or {}).items():
            dst=x["categories"].setdefault(str(cat),{})
            for label,val in (stats or {}).items():
                u=str(label).upper().strip()
                if any(b in u for b in ("AVG","RATE","RTG","QBR","PCT","LONG","LNG","Y/A","Y/C")):continue
                raw=str(val).replace(',','').replace('%','').strip()
                if '/' in raw:continue
                try:dst[label]=dst.get(label,0)+float(raw)
                except:pass
    def nval(v):
        try:return float(str(v).replace(',','').replace('%','').strip().split('/')[0])
        except:return 0.0
    def pickstat(st, aliases):
        norm=lambda z:re.sub(r'[^A-Z0-9]','',str(z).upper()); amap={norm(k):v for k,v in (st or {}).items()}
        for a in aliases:
            if norm(a) in amap:return nval(amap[norm(a)])
        return 0.0
    def catfind(cats,word):
        for k,v in (cats or {}).items():
            if word in str(k).upper():return v or {}
        return {}
    fantasy=[]
    for p in pp.values():
        ng=max(1,len(p["games"])); cats=p["categories"]; pas=catfind(cats,'PASS'); rush=catfind(cats,'RUSH'); rec=catfind(cats,'RECEIV'); fum=catfind(cats,'FUMBL')
        total=(pickstat(pas,['YDS','YARDS'])/25+pickstat(pas,['TD','PASS TD'])*4-pickstat(pas,['INT','INTERCEPTIONS'])*2+pickstat(rush,['YDS','YARDS'])/10+pickstat(rush,['TD','RUSH TD'])*6+pickstat(rec,['REC','RECEPTIONS'])+pickstat(rec,['YDS','YARDS'])/10+pickstat(rec,['TD','REC TD'])*6-pickstat(fum,['LOST','FUM LOST'])*2)
        if total==0:continue
        fppg=total/ng
        fantasy.append({"id":p["id"],"name":p["name"],"team":p["team"],"position":p["position"],"games":ng,"season_fppg":round(fppg,1),"recent3_fppg":round(fppg,1),"projected_fantasy":round(fppg,1),"projection_basis":"NORMALIZED_DB"})
    fantasy.sort(key=lambda x:-x["projected_fantasy"]); fantasy=fantasy[:120]
    maxfp=max([x["projected_fantasy"] for x in fantasy] or [1]); mvp=[]
    for x in fantasy:
        if x["position"] not in ('QB','RB','WR','TE'):continue
        ts=(strength.get(x["team"]) or {}).get('strength',50); score=70*(x['projected_fantasy']/maxfp)+30*(ts/100)
        mvp.append({**x,"mvp_score":round(score,1),"team_strength":ts})
    mvp.sort(key=lambda x:-x["mvp_score"]);mvp=mvp[:20]
    positions={p:len([x for x in fantasy if x["position"]==p]) for p in ('QB','RB','WR','TE')}
    # Upcoming forecasts use only already-warmed week cache; never network on AI request.
    games=[]
    for g in ((WEEK_CACHE.get('value') or {}).get('games') or []):
        if g.get('state')!='pre':continue
        ts=g.get('teams') or []; away=next((x for x in ts if x.get('side')=='away'),ts[0] if ts else {});home=next((x for x in ts if x.get('side')=='home'),ts[-1] if ts else {})
        aa=norm_team_abbr(away.get('abbr'));ha=norm_team_abbr(home.get('abbr'));av=strength.get(aa);hv=strength.get(ha)
        if not av or not hv:continue
        hp=_clamp(50+(hv['strength']-av['strength'])*.72+2,20,80);ap=100-hp
        games.append({'id':g.get('id'),'date':g.get('date'),'away':aa,'home':ha,'away_prob':round(ap,1),'home_prob':round(hp,1),'pick':ha if hp>=ap else aa,'confidence':round(abs(hp-50)*2,1),'status':g.get('status')})
    return {'ok':True,'season':2026,'teams':teams,'games':games,'fantasy':fantasy,'mvp':mvp,'diagnostics':{'database':STORE.kind,'team_game_rows':len(team_rows),'player_game_rows':len(player_rows),'qualified_players':len(fantasy),'position_counts':positions},'formula':{'team_strength':'55% stored win rate + 25% bounded point differential/game + 20% recent stored margin','season_projection':'current stored wins + remaining games × ATLAS expected win rate; schedule-neutral baseline','game_probability':'relative ATLAS team strength + small home-field adjustment, bounded 20–80%','fantasy':'PPR-like production from normalized final-game player rows','mvp':'70% normalized production + 30% projected team strength'},'source':'ATLAS_NORMALIZED_DB_MODEL','updated':int(time.time())}

def rebuild_ai_snapshot():
    with AI_SNAPSHOT_LOCK:
        if AI_SNAPSHOT['building']:return False
        AI_SNAPSHOT['building']=True
    t=time.perf_counter()
    try:
        v=atlas_projection_engine(); dur=round((time.perf_counter()-t)*1000,1)
        with AI_SNAPSHOT_LOCK:AI_SNAPSHOT.update({'ts':time.time(),'value':v,'error':None,'duration_ms':dur,'building':False})
        return True
    except Exception as e:
        with AI_SNAPSHOT_LOCK:AI_SNAPSHOT.update({'error':f'{type(e).__name__}: {e}','building':False})
        return False

def ai_snapshot_response():
    with AI_SNAPSHOT_LOCK:
        v=AI_SNAPSHOT.get('value'); ts=AI_SNAPSHOT.get('ts',0); building=AI_SNAPSHOT.get('building'); err=AI_SNAPSHOT.get('error'); dur=AI_SNAPSHOT.get('duration_ms')
    if v:
        out=dict(v);out['cache']={'age_seconds':round(max(0,time.time()-ts),1),'building':building,'last_build_ms':dur};return out
    return {'ok':True,'warming':True,'teams':[],'games':[],'fantasy':[],'mvp':[],'diagnostics':{'database':STORE.kind},'source':'ATLAS_AI_SNAPSHOT_WARMING','updated':int(time.time()),'error':err}

def ai_snapshot_worker():
    while True:
        rebuild_ai_snapshot()
        time.sleep(AI_REFRESH_SECONDS)

def atlas_ai_status():
    return {"ok":True,"enabled":bool(OPENAI_API_KEY),"provider":"openai" if OPENAI_API_KEY else "atlas-local","model":OPENAI_MODEL if OPENAI_API_KEY else "ATLAS deterministic engine","role":"reasoning_layer","source_of_truth":"ATLAS normalized Postgres/database","version":VERSION}

def _atlas_ai_context(question):
    # Deliberately compact: the LLM reasons over ATLAS facts; it never becomes the stats database.
    snap=ai_snapshot_response()
    teams=(snap.get("teams") or [])[:32]
    fantasy=(snap.get("fantasy") or [])[:40]
    mvp=(snap.get("mvp") or [])[:20]
    games=(snap.get("games") or [])[:20]
    q=str(question or "").upper()
    mentioned=[]
    for t in teams:
        ab=str(t.get("abbr") or "").upper()
        if ab and (ab in q or str(t.get("name") or "").upper() in q): mentioned.append(t)
    return {"atlas_model":{"teams":teams,"upcoming_games":games,"top_player_projections":fantasy,"mvp_signal":mvp,"diagnostics":snap.get("diagnostics") or {},"formula":snap.get("formula") or {}},"focus_teams":mentioned[:4],"rules":{"facts":"Only use supplied ATLAS data as current statistical facts.","missing":"If the data needed is absent, say ATLAS does not have it yet.","predictions":"Clearly label predictions/rankings as ATLAS model outputs, not facts.","no_invention":"Never invent injuries, news, plays, stats, contracts, odds, or Next Gen Stats."}}

def atlas_ai_ask(question):
    question=str(question or "").strip()
    if not question:return {"ok":False,"error":"Ask ATLAS a football question."}
    if len(question)>1200:return {"ok":False,"error":"Question is too long."}
    ctx=_atlas_ai_context(question)
    if not OPENAI_API_KEY:
        return {"ok":False,"enabled":False,"provider":"atlas-local","error":"OpenAI reasoning is not configured. Add OPENAI_API_KEY in Render Environment. ATLAS statistics and deterministic projections remain available.","context_ready":True}
    payload={
      "model":OPENAI_MODEL,
      "reasoning":{"effort":"low"},
      "instructions":"You are ATLAS Intelligence, an NFL analytics assistant inside ATLAS. The ATLAS database and deterministic model are the source of truth. Explain football clearly and concisely. Never invent missing current facts. Distinguish measured database facts from ATLAS projections. Do not present sportsbook odds or betting advice. Return useful analysis grounded only in the supplied ATLAS context.",
      "input":[{"role":"user","content":[{"type":"input_text","text":"QUESTION:\n"+question+"\n\nATLAS_CONTEXT_JSON:\n"+json.dumps(ctx,separators=(',',':'))}]}],
      "max_output_tokens":900
    }
    req=Request("https://api.openai.com/v1/responses",data=json.dumps(payload).encode(),headers={"Authorization":"Bearer "+OPENAI_API_KEY,"Content-Type":"application/json","User-Agent":"ATLAS/68.0"},method="POST")
    t=time.perf_counter()
    try:
        with urlopen(req,timeout=OPENAI_TIMEOUT) as r: data=json.loads(r.read().decode())
        textout=data.get("output_text") or ""
        if not textout:
            chunks=[]
            for item in data.get("output") or []:
                for c in item.get("content") or []:
                    if c.get("type") in ("output_text","text") and c.get("text"):chunks.append(c["text"])
            textout="\n".join(chunks)
        if not textout:return {"ok":False,"error":"ATLAS Intelligence returned no text.","provider":"openai"}
        return {"ok":True,"answer":textout,"provider":"openai","model":OPENAI_MODEL,"latency_ms":round((time.perf_counter()-t)*1000,1),"grounding":"ATLAS_NORMALIZED_DB+ATLAS_MODEL","updated":int(time.time())}
    except Exception as e:
        return {"ok":False,"error":f"ATLAS Intelligence unavailable: {type(e).__name__}","provider":"openai","model":OPENAI_MODEL}

def atlas_search(q):
    q=str(q or '').strip().lower()
    if len(q)<2:return {"ok":True,"query":q,"results":[]}
    out=[]
    for t in team_index():
        text=f"{t.get('name','')} {t.get('abbr','')}".lower()
        if q in text: out.append({"type":"team","id":norm_team_abbr(t.get('abbr')),"label":t.get('name'),"meta":norm_team_abbr(t.get('abbr'))})
    try:
        for x in player_index():
            text=f"{x.get('name','')} {x.get('team','')} {x.get('position','')}".lower()
            if q in text: out.append({"type":"player","id":x.get('id'),"label":x.get('name'),"meta":f"{x.get('team','')} · {x.get('position','')}"})
            if len(out)>=18: break
    except Exception: pass
    for g in archive_recent(24):
        names=' '.join(str(t.get('name') or t.get('abbr') or '') for t in g.get('teams') or []).lower()
        if q in names or q in str(g.get('id')): out.append({"type":"game","id":g.get('id'),"label":" @ ".join((t.get('abbr') or '?') for t in g.get('teams') or []),"meta":g.get('status')})
    return {"ok":True,"query":q,"results":out[:18]}

SOURCE_HEALTH_CACHE={"ts":0,"value":None}
SOURCE_HEALTH_LOCK=threading.Lock()

def _probe_url(url, label, kind, role):
    started=time.time()
    try:
        req=Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; GridironAtlas/17.1)","Accept":"application/json,text/html,*/*"})
        with urlopen(req,timeout=7) as r:
            code=getattr(r,"status",200); r.read(256)
        return {"name":label,"kind":kind,"role":role,"ok":200<=code<400,"status":str(code),"latency_ms":round((time.time()-started)*1000)}
    except Exception as e:
        return {"name":label,"kind":kind,"role":role,"ok":False,"status":type(e).__name__,"latency_ms":round((time.time()-started)*1000)}

def _internal_diagnostics():
    checks=[]
    def run(name,fn,detail):
        try:
            v=fn(); ok=bool(v)
            checks.append({"name":name,"ok":ok,"detail":detail(v) if callable(detail) else detail})
        except Exception as e: checks.append({"name":name,"ok":False,"detail":type(e).__name__+": "+str(e)[:90]})
    run("Database store",lambda:STORE.kind,lambda v:str(v))
    run("Team map",lambda:len(TEAM_IDS)==32,lambda v:"32 NFL team identifiers" if v else "Team map incomplete")
    run("Static application",lambda:(ROOT/'index.html').exists() and (ROOT/'atlas680.js').exists() and (ROOT/'atlas680.css').exists(),"Core UI assets present")
    run("Verified baseline",lambda:len(VERIFIED_PLAYERS),lambda v:f"{v} embedded baseline rows")
    run("Collector state",lambda:LAST is not None,"Collector state object available")
    return checks

def source_health(force=False):
    now=time.time()
    with SOURCE_HEALTH_LOCK:
        if not force and SOURCE_HEALTH_CACHE["value"] and now-SOURCE_HEALTH_CACHE["ts"]<60:return SOURCE_HEALTH_CACHE["value"]
    probes=[
      ("https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard","ESPN Scoreboard","live feed","Scores · schedule · game state"),
      ("https://site.api.espn.com/apis/v2/sports/football/nfl/standings?season=2026","ESPN Standings","season feed","Standings and records"),
      ("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams","ESPN Teams","identity feed","Teams and public metadata"),
      ("https://www.nfl.com/stats/","NFL Stats","official reference","Official statistics cross-check"),
      ("https://operations.nfl.com/gameday/technology/nfl-next-gen-stats/","NFL Next Gen Stats","ngs reference","Official NGS methodology reference"),
      ("https://aws.amazon.com/sports/nfl/","AWS × NFL","ngs infrastructure","Infrastructure reference; not a raw stats API"),
    ]
    with ThreadPoolExecutor(max_workers=6) as ex: sources=list(ex.map(lambda p:_probe_url(*p),probes))
    value={"ok":True,"sources":sources,"diagnostics":_internal_diagnostics(),"ngs_mode":"SOURCE-GATED","ngs_raw_feed":False,"updated":int(time.time())}
    with SOURCE_HEALTH_LOCK: SOURCE_HEALTH_CACHE.update(ts=time.time(),value=value)
    return value

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
        p=urlparse(self.path).path
        if not p.startswith("/api/"):
            self.send_header("Cache-Control","no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma","no-cache")
            self.send_header("Expires","0")
            self.send_header("X-ATLAS-Build",VERSION)
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Referrer-Policy","no-referrer")
        self.send_header("Permissions-Policy","camera=(), microphone=(), geolocation=()")
        self.send_header("X-Frame-Options","SAMEORIGIN")
        super().end_headers()
    def sendj(self,o,status=200):
        b=json.dumps(o).encode();self.send_response(status);self.send_header("Content-Type","application/json");self.send_header("Cache-Control","no-store");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
    def do_POST(self):
        u=urlparse(self.path)
        if u.path!="/api/ai/ask":return self.sendj({"ok":False,"error":"Not found"},404)
        try:
            n=min(int(self.headers.get("Content-Length","0") or 0),20000)
            body=json.loads(self.rfile.read(n).decode() or "{}")
        except Exception:return self.sendj({"ok":False,"error":"Invalid JSON"},400)
        out=atlas_ai_ask(body.get("question"))
        return self.sendj(out,200 if out.get("ok") else (503 if out.get("enabled") is False else 502))

    def do_GET(self):
        u=urlparse(self.path);q=parse_qs(u.query)
        if u.path=="/api/games":return self.sendj(scoreboard((q.get("date") or [None])[0]))
        if u.path=="/api/week":
            season=(q.get("season") or [2026])[0]; week=(q.get("week") or [None])[0]; st=(q.get("type") or [2])[0]
            try:return self.sendj(week_schedule(season, int(week) if week not in (None,"") else None, st))
            except Exception as e:return self.sendj({"ok":False,"games":[],"error":str(e)},502)
        if u.path=="/api/game":
            gid=(q.get("id") or [DEFAULT_GAME_ID])[0]
            if not str(gid).isdigit() or not (6 <= len(str(gid)) <= 20): return self.sendj({"ok":False,"error":"Invalid game id"},400)
            return self.sendj(game(gid))
        if u.path=="/api/archive":return self.sendj({"games":STORE.games(),"database":STORE.kind})
        if u.path=="/api/atlas":return self.sendj(atlas_overview())
        if u.path=="/api/archive-intelligence":return self.sendj(archive_intelligence())
        if u.path=="/api/stats-health":return self.sendj(unified_stats_health())
        if u.path=="/api/data-center":return self.sendj(unified_stats_health())
        if u.path=="/api/postgame-stats":
            if (q.get("repair") or ["0"])[0] in ("1","true"): repair_player_stats_once(12)
            return self.sendj(postgame_stats())
        if u.path=="/api/trends":
            return self.sendj(archive_trends((q.get("team") or [None])[0]))
        if u.path=="/api/insights":
            return self.sendj(atlas_insights((q.get("team") or [None])[0]))
        if u.path=="/api/search":
            return self.sendj(atlas_search((q.get("q") or [""])[0]))
        if u.path=="/api/projections":return self.sendj(ai_snapshot_response())
        if u.path=="/api/ai/status":return self.sendj(atlas_ai_status())
        if u.path=="/api/projections/rebuild":return self.sendj({"ok":False,"error":"AI snapshots rebuild automatically."},405)
        if u.path=="/api/archive-coverage":
            try:return self.sendj({"ok":True,**archive_coverage(),"backfill":LAST.get("backfill_stats") or {}})
            except Exception as e:return self.sendj({"ok":False,"error":str(e)},502)
        if u.path=="/api/recent":
            try: limit=int((q.get("limit") or [8])[0])
            except Exception: limit=8
            return self.sendj({"ok":True,"games":archive_recent(limit),"database":STORE.kind})
        if u.path=="/api/quality":
            gid=(q.get("id") or [DEFAULT_GAME_ID])[0]
            return self.sendj({"id":gid,**game_quality(STORE.game(gid) or game(gid))})
        if u.path in ["/api/history","/api/snapshots"]:
            gid=(q.get("id") or [DEFAULT_GAME_ID])[0]
            if not str(gid).isdigit() or not (6 <= len(str(gid)) <= 20): return self.sendj({"ok":False,"error":"Invalid game id"},400)
            return self.sendj({"id":gid,"snapshots":STORE.snaps(gid)})
        if u.path=="/api/players":
            team=(q.get("team") or [None])[0]
            if team:
                try:return self.sendj(team_roster(team))
                except Exception as e:return self.sendj({"ok":False,"team":str(team).upper(),"players":[],"error":str(e)},502)
            rows=player_index();return self.sendj({"players":rows,"count":len(rows),"teams":len({p.get("team") for p in rows if p.get("team")}),"source":"LEAGUE_ROSTERS+ATLAS_ARCHIVE"})
        if u.path=="/api/roster":
            team=(q.get("team") or [""])[0]
            try:return self.sendj(team_roster(team))
            except Exception as e:return self.sendj({"ok":False,"team":str(team).upper(),"players":[],"error":str(e)},502)
        if u.path=="/api/player":
            aid=(q.get("id") or [""])[0]
            try:return self.sendj(player_profile(aid))
            except Exception as e:return self.sendj({"ok":False,"error":str(e)},502)
        if u.path=="/api/teamstats":
            team=(q.get("team") or [""])[0]
            try:return self.sendj(_team_season_stats(team))
            except Exception as e:return self.sendj({"ok":False,"team":str(team).upper(),"stats":[],"error":str(e)},502)
        if u.path=="/api/teams":return self.sendj({"teams":team_index()})
        if u.path=="/api/league":return self.sendj(league_hq())
        if u.path=="/api/health":return self.sendj({"ok":True,"version":VERSION,"build":BUILD_NAME,"database":STORE.kind,"provider":PROVIDER,"collector_seconds":COLLECT_SECONDS,"last":LAST})
        if u.path=="/api/build":return self.sendj({"ok":True,"version":VERSION,"build":BUILD_NAME,"js":"atlas680.js","css":"atlas680.css","database":STORE.kind,"ai":atlas_ai_status()})
        if u.path=="/api/sources":return self.sendj(source_health((q.get("force") or ["0"])[0]=="1"))
        if u.path=="/api/collect":return self.sendj({"ok":False,"error":"Manual collection by GET is disabled; collector runs automatically."},405)
        if u.path=="/api/export.csv":
            gid=(q.get("id") or [DEFAULT_GAME_ID])[0]
            if not str(gid).isdigit() or not (6 <= len(str(gid)) <= 20): return self.sendj({"ok":False,"error":"Invalid game id"},400)
            g=game(gid);buf=io.StringIO();w=csv.writer(buf);w.writerow(["team","player","position","category","stat","value"])
            for p in g.get("players",[]):
                for k,v in (p.get("stats") or {}).items():w.writerow([p.get("team"),p.get("name"),p.get("position"),p.get("category"),k,v])
            b=buf.getvalue().encode();self.send_response(200);self.send_header("Content-Type","text/csv");self.send_header("Content-Disposition",f'attachment; filename="gridiron-{gid}.csv"');self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b);return
        if u.path=="/api/live":return self.sendj(legacy_live())
        if u.path=="/":self.path="/index.html"
        super().do_GET()

if __name__=="__main__":
    try:
        LAST["data_core_bootstrap"]=rebuild_data_core_once(64)
    except Exception as e:
        LAST["data_core_bootstrap"]={"error":f"{type(e).__name__}: {e}"}
    rebuild_ai_snapshot()
    threading.Thread(target=ai_snapshot_worker,daemon=True).start()
    threading.Thread(target=collector,daemon=True).start()
    ThreadingHTTPServer((HOST,PORT),H).serve_forever()
