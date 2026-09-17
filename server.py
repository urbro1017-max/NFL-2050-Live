import json,os,time,sqlite3,csv,io
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from urllib.request import Request,urlopen
from urllib.parse import urlparse,parse_qs
from pathlib import Path

HOST="0.0.0.0"; PORT=int(os.environ.get("PORT","10000")); ROOT=Path(__file__).parent/"app"
DEFAULT_GAME_ID="401872932"
SNAPSHOTS={}
DB=Path(os.environ.get("GRIDIRON_DB",str(Path(__file__).parent/"gridiron_atlas.db")))
def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    c.executescript("""CREATE TABLE IF NOT EXISTS games(game_id TEXT PRIMARY KEY, payload TEXT, status TEXT, updated INTEGER);
    CREATE TABLE IF NOT EXISTS snapshots(id INTEGER PRIMARY KEY AUTOINCREMENT,game_id TEXT,ts INTEGER,payload TEXT);
    CREATE INDEX IF NOT EXISTS ix_snap_game ON snapshots(game_id,ts);"""); c.commit(); return c
def persist_game(g):
    if not g.get("available"): return
    c=db(); c.execute("INSERT INTO games VALUES(?,?,?,?) ON CONFLICT(game_id) DO UPDATE SET payload=excluded.payload,status=excluded.status,updated=excluded.updated",(g["id"],json.dumps(g),g.get("status",""),int(time.time())))
    snap={"t":int(time.time()),"status":g.get("status"),"scores":{x["abbr"]:x["score"] for x in g.get("teams",[])},"team_stats":g.get("team_stats",{})}
    prev=c.execute("SELECT payload FROM snapshots WHERE game_id=? ORDER BY ts DESC,id DESC LIMIT 1",(g["id"],)).fetchone()
    if not prev or json.loads(prev["payload"]).get("scores")!=snap["scores"] or json.loads(prev["payload"]).get("team_stats")!=snap["team_stats"]:
        c.execute("INSERT INTO snapshots(game_id,ts,payload) VALUES(?,?,?)",(g["id"],snap["t"],json.dumps(snap)))
    c.commit(); c.close()


def fetch(u):
    req=Request(u,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    with urlopen(req,timeout=8) as r:return json.loads(r.read().decode())

def scoreboard():
    try:d=fetch("https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard")
    except Exception:
        try:d=fetch("https://cdn.espn.com/core/nfl/scoreboard?xhr=1")
        except Exception:return {"games":[],"source":"unavailable"}
    events=d.get("events") or ((d.get("content") or {}).get("sbData") or {}).get("events") or []
    games=[]
    for e in events:
        comp=((e.get("competitions") or [{}])[0]); teams=[]
        for c in comp.get("competitors") or []:
            t=c.get("team") or {}
            teams.append({"side":c.get("homeAway"),"abbr":t.get("abbreviation"),"name":t.get("displayName") or t.get("shortDisplayName"),"logo":t.get("logo"),"score":c.get("score","0")})
        st=(comp.get("status") or e.get("status") or {}); typ=st.get("type") or {}
        games.append({"id":str(e.get("id") or comp.get("id") or ""),"date":e.get("date"),"status":typ.get("shortDetail") or typ.get("description") or "Scheduled","teams":teams})
    return {"games":games,"source":"ESPN public scoreboard"}

def generic_game(game_id):
    url=f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={game_id}"
    fb=f"https://cdn.espn.com/core/nfl/game?xhr=1&gameId={game_id}"
    try:d=fetch(url)
    except Exception:
        try:d=fetch(fb); d=d.get("gamepackageJSON",d)
        except Exception:return {"id":game_id,"available":False,"status":"Unavailable","teams":[],"team_stats":{},"players":[],"plays":[],"drives":[],"linescores":{}}
    comp=((d.get("header",{}).get("competitions") or [{}])[0]); teams=[]; lines={}
    for c in comp.get("competitors") or []:
        t=c.get("team") or {}; ab=(t.get("abbreviation") or "").upper()
        lines[ab]=[x.get("displayValue",x.get("value")) for x in (c.get("linescores") or [])]
        teams.append({"side":c.get("homeAway"),"abbr":ab,"name":t.get("displayName") or t.get("shortDisplayName") or ab,"logo":t.get("logo"),"score":c.get("score",0),"color":t.get("color"),"alternateColor":t.get("alternateColor")})
    st=comp.get("status") or {}; typ=st.get("type") or {}
    out={"id":game_id,"available":True,"status":typ.get("shortDetail") or typ.get("description") or "Scheduled","period":st.get("period") or 0,"clock":st.get("displayClock") or (st.get("clock") or {}).get("displayValue") or "—","teams":teams,"team_stats":{},"players":[],"plays":[],"drives":[],"linescores":lines,"source":"ESPN public game feed","fetched_at":int(time.time())}
    for t in ((d.get("boxscore") or {}).get("teams") or []):
        ab=((t.get("team") or {}).get("abbreviation") or "").upper()
        out["team_stats"][ab]={str(x.get("label") or x.get("name")):x.get("displayValue") for x in (t.get("statistics") or [])}
    for grp in ((d.get("boxscore") or {}).get("players") or []):
        ab=((grp.get("team") or {}).get("abbreviation") or "").upper()
        for cat in grp.get("statistics") or []:
            labels=cat.get("labels") or []; cname=cat.get("name") or cat.get("label") or "stats"
            for row in cat.get("athletes") or []:
                a=row.get("athlete") or {}
                out["players"].append({"team":ab,"name":a.get("displayName"),"category":cname,"stats":dict(zip(labels,row.get("stats") or []))})
    raw=d.get("plays") or []
    for p in raw[-80:]:
        out["plays"].append({"clock":(p.get("clock") or {}).get("displayValue"),"period":(p.get("period") or {}).get("number"),"text":p.get("text"),"team":((p.get("team") or {}).get("abbreviation")),"start":p.get("start"),"end":p.get("end")})
    dr=(d.get("drives") or {}).get("previous") or []
    for x in dr:
        out["drives"].append({"team":((x.get("team") or {}).get("abbreviation")) or "—","result":x.get("description") or x.get("displayResult") or x.get("result") or "Drive","yards":x.get("yards"),"time":x.get("timeElapsed"),"start":x.get("start"),"end":x.get("end"),"plays":x.get("offensivePlays") or x.get("plays")})
    # lightweight server-session snapshots for progression graphs
    snap={"t":out["fetched_at"],"status":out["status"],"scores":{x["abbr"]:x["score"] for x in teams},"yards":{}}
    for ab,stats in out["team_stats"].items():
        for k,v in stats.items():
            if "total" in k.lower() and "yard" in k.lower(): snap["yards"][ab]=v; break
    arr=SNAPSHOTS.setdefault(game_id,[])
    if not arr or arr[-1]["scores"]!=snap["scores"] or arr[-1]["yards"]!=snap["yards"]: arr.append(snap)
    SNAPSHOTS[game_id]=arr[-240:]
    persist_game(out)
    return out

def legacy_live():
    g=generic_game(DEFAULT_GAME_ID)
    out={"game":{"status":g.get("status","Pregame"),"detScore":0,"bufScore":0,"period":g.get("period",0),"clock":g.get("clock","—"),"possession":"—","downDistance":"—","ballSpot":"—"},"plays":g.get("plays",[])[-24:],"team_stats":g.get("team_stats",{}),"players":g.get("players",[]),"linescores":{"DET":g.get("linescores",{}).get("DET",[]),"BUF":g.get("linescores",{}).get("BUF",[])},"drives":g.get("drives",[])[-8:]}
    for t in g.get("teams",[]):
        if t["abbr"]=="DET":out["game"]["detScore"]=t["score"]
        if t["abbr"]=="BUF":out["game"]["bufScore"]=t["score"]
    if out["plays"]:
        p=out["plays"][-1];out["game"]["downDistance"]=(p.get("text") or "")[:42];out["game"]["ballSpot"]=((p.get("end") or {}).get("yardLine")) or "—";out["game"]["possession"]=p.get("team") or "—"
    return out

class H(SimpleHTTPRequestHandler):
    def __init__(self,*a,**k):super().__init__(*a,directory=str(ROOT),**k)
    def sendj(self,obj):
        b=json.dumps(obj).encode();self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Cache-Control","no-store");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
    def do_GET(self):
        u=urlparse(self.path); q=parse_qs(u.query)
        if u.path=="/api/games":return self.sendj(scoreboard())
        if u.path=="/api/game":return self.sendj(generic_game((q.get("id") or [DEFAULT_GAME_ID])[0]))
        if u.path=="/api/history":return self.sendj({"id":(q.get("id") or [DEFAULT_GAME_ID])[0],"snapshots":SNAPSHOTS.get((q.get("id") or [DEFAULT_GAME_ID])[0],[])})
        if u.path=="/api/archive":
            c=db(); rows=c.execute("SELECT game_id,status,updated,payload FROM games ORDER BY updated DESC").fetchall(); c.close()
            return self.sendj({"games":[{"id":r["game_id"],"status":r["status"],"updated":r["updated"],"teams":json.loads(r["payload"]).get("teams",[])} for r in rows]})
        if u.path=="/api/snapshots":
            gid=(q.get("id") or [DEFAULT_GAME_ID])[0]; c=db(); rows=c.execute("SELECT payload FROM snapshots WHERE game_id=? ORDER BY ts",(gid,)).fetchall(); c.close()
            return self.sendj({"id":gid,"snapshots":[json.loads(r["payload"]) for r in rows]})
        if u.path=="/api/export.csv":
            gid=(q.get("id") or [DEFAULT_GAME_ID])[0]; g=generic_game(gid); buf=io.StringIO(); w=csv.writer(buf); w.writerow(["team","player","category","stat","value"])
            for p in g.get("players",[]):
                for k,v in (p.get("stats") or {}).items(): w.writerow([p.get("team"),p.get("name"),p.get("category"),k,v])
            b=buf.getvalue().encode(); self.send_response(200); self.send_header("Content-Type","text/csv"); self.send_header("Content-Disposition",f'attachment; filename="gridiron-{gid}.csv"'); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b); return
        if u.path=="/api/live":return self.sendj(legacy_live())
        if u.path=="/":self.path="/index.html"
        super().do_GET()
if __name__=="__main__":ThreadingHTTPServer((HOST,PORT),H).serve_forever()
