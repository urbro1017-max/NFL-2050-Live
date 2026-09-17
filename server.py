import json,os,time,sqlite3,csv,io,threading
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from urllib.request import Request,urlopen
from urllib.parse import urlparse,parse_qs
from pathlib import Path

HOST="0.0.0.0"; PORT=int(os.environ.get("PORT","10000")); ROOT=Path(__file__).parent/"app"
DEFAULT_GAME_ID=os.environ.get("DEFAULT_GAME_ID","401872932")
DATABASE_URL=os.environ.get("DATABASE_URL","")
COLLECT_SECONDS=max(15,int(os.environ.get("COLLECT_SECONDS","30")))
DBFILE=Path(os.environ.get("GRIDIRON_DB",str(Path(__file__).parent/"gridiron_atlas.db")))
PROVIDER="ESPN_CORE_DISCOVERY+CDN_GAME"
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
        "teams":teams
    }

def scoreboard(date=None):
    """Discover NFL event IDs with ESPN Core, then hydrate rows from CDN game packages.

    Core's events endpoint returns reference objects rather than the site-scoreboard
    event shape. 3.1 incorrectly parsed those transports as interchangeable.
    """
    day=date or time.strftime("%Y%m%d")
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
        return {"games":games,"source":PROVIDER,"date":day,"event_count":len(ids)}
    except Exception:
        # Preserve archive usability if discovery is temporarily unavailable.
        archived=[]
        for x in STORE.games():
            archived.append({"id":x["id"],"status":x.get("status","Archived"),"teams":x.get("teams",[]),"date":None})
        LAST["fallback"]="archive"
        return {"games":archived,"source":"ARCHIVE_FALLBACK","date":day,"event_count":len(archived)}

def game(gid,save=True):
    # CDN game package first. The site summary endpoint is retained only as a
    # fallback because some server environments receive 403 from site.api.
    try:
        raw=fetch(f"https://cdn.espn.com/core/nfl/game?xhr=1&gameId={gid}","ESPN_CDN_GAME")
        d=raw.get("gamepackageJSON",raw)
        LAST["fallback"]=None
    except Exception:
        try:
            d=fetch(f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={gid}","ESPN_SITE_SUMMARY_FALLBACK")
            LAST["fallback"]="site summary"
        except Exception:
            return STORE.game(gid) or {"id":gid,"available":False,"status":"Unavailable","teams":[],"team_stats":{},"players":[],"plays":[],"drives":[],"linescores":{},"source":"ARCHIVE_OR_UNAVAILABLE"}
    comp=((d.get("header") or {}).get("competitions") or [{}])[0];teams=[];lines={}
    for c in comp.get("competitors") or []:
        t=c.get("team") or {};ab=(t.get("abbreviation") or "").upper();lines[ab]=[x.get("displayValue",x.get("value")) for x in c.get("linescores") or []]
        teams.append({"side":c.get("homeAway"),"abbr":ab,"name":t.get("displayName") or t.get("shortDisplayName") or ab,"logo":_team_logo(t),"score":c.get("score",0),"color":t.get("color"),"alternateColor":t.get("alternateColor")})
    st=comp.get("status") or {};typ=st.get("type") or {}
    out={"id":gid,"available":True,"status":typ.get("shortDetail") or typ.get("description") or "Scheduled","period":st.get("period") or 0,"clock":st.get("displayClock") or (st.get("clock") or {}).get("displayValue") or "—","teams":teams,"team_stats":{},"players":[],"plays":[],"drives":[],"linescores":lines,"source":PROVIDER,"fetched_at":int(time.time())}
    for t in ((d.get("boxscore") or {}).get("teams") or []):
        ab=((t.get("team") or {}).get("abbreviation") or "").upper();out["team_stats"][ab]={str(x.get("label") or x.get("name")):x.get("displayValue") for x in t.get("statistics") or []}
    for grp in ((d.get("boxscore") or {}).get("players") or []):
        ab=((grp.get("team") or {}).get("abbreviation") or "").upper()
        for cat in grp.get("statistics") or []:
            labels=cat.get("labels") or [];cname=cat.get("name") or cat.get("label") or "stats"
            for row in cat.get("athletes") or []:
                a=row.get("athlete") or {};out["players"].append({"id":a.get("id"),"team":ab,"name":a.get("displayName"),"position":((a.get("position") or {}).get("abbreviation")),"category":cname,"stats":dict(zip(labels,row.get("stats") or []))})
    for p in (d.get("plays") or [])[-180:]:
        out["plays"].append({"id":p.get("id"),"clock":(p.get("clock") or {}).get("displayValue"),"period":(p.get("period") or {}).get("number"),"text":p.get("text"),"team":((p.get("team") or {}).get("abbreviation")),"start":p.get("start"),"end":p.get("end"),"type":((p.get("type") or {}).get("text"))})
    drive_block=d.get("drives") or {}
    drive_rows=list(drive_block.get("previous") or [])
    current=drive_block.get("current")
    if isinstance(current,dict) and current.get("id") not in {x.get("id") for x in drive_rows}: drive_rows.append(current)
    for x in drive_rows:
        out["drives"].append({"id":x.get("id"),"team":((x.get("team") or {}).get("abbreviation")) or "—","result":x.get("description") or x.get("displayResult") or x.get("result") or "Drive","yards":x.get("yards"),"time":x.get("timeElapsed"),"start":x.get("start"),"end":x.get("end"),"plays":x.get("offensivePlays") or x.get("plays")})
    if save:STORE.save(out)
    return out

def collect_once():
    sb=scoreboard()
    for g in sb.get("games",[]):
        st=(g.get("status") or "").lower()
        if any(x in st for x in ["q1","q2","q3","q4","half","ot","final","end"]):
            try:game(g["id"],True)
            except Exception as e:LAST["error"]=str(e)
    LAST["collector"]=int(time.time())
def collector():
    while True:
        try:collect_once()
        except Exception as e:LAST["error"]=str(e)
        time.sleep(COLLECT_SECONDS)

def player_index():
    out={}
    for gm in STORE.games():
        g=STORE.game(gm["id"]) or {}
        for p in g.get("players",[]):
            n=p.get("name"); 
            if not n:continue
            out.setdefault(n,{"name":n,"team":p.get("team"),"position":p.get("position"),"games":[]})
            out[n]["games"].append({"game_id":g["id"],"status":g.get("status"),"team":p.get("team"),"category":p.get("category"),"stats":p.get("stats")})
    return list(out.values())

def team_index():
    out={}
    for gm in STORE.games():
        g=STORE.game(gm["id"]) or {}
        for t in g.get("teams",[]):
            ab=t.get("abbr");out.setdefault(ab,{"abbr":ab,"name":t.get("name"),"logo":_team_logo(t),"games":[]});out[ab]["games"].append({"game_id":g["id"],"status":g.get("status"),"score":t.get("score"),"team_stats":g.get("team_stats",{}).get(ab,{})})
    return list(out.values())

def legacy_live():
    g=game(DEFAULT_GAME_ID);out={"game":{"status":g.get("status","Pregame"),"detScore":0,"bufScore":0,"period":g.get("period",0),"clock":g.get("clock","—"),"possession":"—","downDistance":"—","ballSpot":"—"},"plays":g.get("plays",[])[-24:],"team_stats":g.get("team_stats",{}),"players":g.get("players",[]),"linescores":{"DET":g.get("linescores",{}).get("DET",[]),"BUF":g.get("linescores",{}).get("BUF",[])},"drives":g.get("drives",[])[-8:]}
    for t in g.get("teams",[]):
        if t["abbr"]=="DET":out["game"]["detScore"]=t["score"]
        if t["abbr"]=="BUF":out["game"]["bufScore"]=t["score"]
    if out["plays"]:
        p=out["plays"][-1];out["game"]["downDistance"]=(p.get("text") or "")[:42];out["game"]["ballSpot"]=((p.get("end") or {}).get("yardLine")) or "—";out["game"]["possession"]=p.get("team") or "—"
    return out

class H(SimpleHTTPRequestHandler):
    def __init__(self,*a,**k):super().__init__(*a,directory=str(ROOT),**k)
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
        if u.path=="/api/health":return self.sendj({"ok":True,"version":"3.2","database":STORE.kind,"provider":PROVIDER,"collector_seconds":COLLECT_SECONDS,"last":LAST})
        if u.path=="/api/collect":collect_once();return self.sendj({"ok":True,"last":LAST})
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
