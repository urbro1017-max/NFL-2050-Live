from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from pathlib import Path
import json, time, threading, webbrowser, os, sys

EVENT_ID = "401872932"
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "10000"))
ROOT = Path(__file__).resolve().parent
APP = ROOT / "app"

GAME_URL = f"https://cdn.espn.com/core/nfl/game?xhr=1&gameId={EVENT_ID}"
PBP_URL = f"https://cdn.espn.com/core/nfl/playbyplay?xhr=1&gameId={EVENT_ID}"
SCORE_URL = "https://cdn.espn.com/core/nfl/scoreboard?xhr=1"
ROSTER_URLS = {
    "DET": "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/8/roster",
    "BUF": "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/2/roster",
}

cache={"live":None,"rosters":None,"live_at":0,"roster_at":0,"error":None}
lock=threading.Lock()

def get_json(url, timeout=8):
    req=Request(url,headers={"User-Agent":"Mozilla/5.0 NFL2050/1.0","Accept":"application/json"})
    with urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def gp(data):
    return data.get("gamepackageJSON", data) if isinstance(data,dict) else {}

def team_abbr(obj):
    if not isinstance(obj,dict): return ""
    t=obj.get("team",obj)
    return t.get("abbreviation") or t.get("shortDisplayName") or ""

def normalize():
    game_raw=get_json(GAME_URL)
    pkg=gp(game_raw)
    header=pkg.get("header",{}) or {}
    comps=header.get("competitions",[]) or []
    comp=comps[0] if comps else {}
    competitors=comp.get("competitors",[]) or []
    scores={}
    for c in competitors:
        ab=team_abbr(c)
        if ab:
            sc=c.get("score",0)
            if isinstance(sc,dict): sc=sc.get("displayValue",sc.get("value",0))
            scores[ab]=sc

    status=comp.get("status",{}) or header.get("status",{}) or {}
    stype=status.get("type",{}) if isinstance(status,dict) else {}
    game={
      "detScore":scores.get("DET",0),
      "bufScore":scores.get("BUF",0),
      "period":status.get("period") or comp.get("period"),
      "clock":status.get("displayClock") or comp.get("displayClock"),
      "status":stype.get("shortDetail") or stype.get("detail") or stype.get("description") or "Pregame"
    }

    team_stats={"DET":[],"BUF":[]}
    box=pkg.get("boxscore",{}) or {}
    for t in box.get("teams",[]) or []:
        ab=team_abbr(t)
        if ab in team_stats:
            stats=[]
            for s in t.get("statistics",[]) or []:
                stats.append({
                    "name":s.get("name",""),
                    "label":s.get("label") or s.get("displayName") or s.get("name",""),
                    "value":s.get("value"),
                    "displayValue":s.get("displayValue")
                })
            team_stats[ab]=stats

    plays=[]
    # Try game package first.
    for source in (pkg.get("plays"), (pkg.get("drives") or {}).get("previous")):
        if isinstance(source,list):
            for p in source:
                if not isinstance(p,dict): continue
                if "plays" in p and isinstance(p["plays"],list):
                    for q in p["plays"]:
                        plays.append({"text":q.get("text",""),"clock":(q.get("clock") or {}).get("displayValue","") if isinstance(q.get("clock"),dict) else q.get("clock","")})
                else:
                    plays.append({"text":p.get("text",""),"clock":(p.get("clock") or {}).get("displayValue","") if isinstance(p.get("clock"),dict) else p.get("clock","")})
    if not plays:
        try:
            pbp=gp(get_json(PBP_URL))
            arr=pbp.get("plays",[]) if isinstance(pbp,dict) else []
            for p in arr:
                plays.append({"text":p.get("text",""),"clock":(p.get("clock") or {}).get("displayValue","") if isinstance(p.get("clock"),dict) else p.get("clock","")})
        except Exception:
            pass

    return {"game":game,"teamStats":team_stats,"plays":plays[-30:],"source":"ESPN CDN","eventId":EVENT_ID,"fetchedAt":time.time()}

def normalize_roster(team, raw):
    athletes=[]
    # Site API roster usually has groups with athletes.
    groups=raw.get("athletes",[]) if isinstance(raw,dict) else []
    for g in groups:
        items=g.get("items",[]) if isinstance(g,dict) else []
        for a in items:
            athletes.append({
              "team":team,"id":a.get("id"),"name":a.get("displayName") or a.get("fullName"),
              "number":a.get("jersey"),"position":(a.get("position") or {}).get("abbreviation"),
              "active":a.get("active",True)
            })
    return athletes

def rosters():
    out=[]
    for team,url in ROSTER_URLS.items():
        out.extend(normalize_roster(team,get_json(url)))
    return out

class Handler(SimpleHTTPRequestHandler):
    def translate_path(self,path):
        clean=urlparse(path).path
        if clean.startswith("/api/"): return str(APP/"__none__")
        rel=clean.lstrip("/") or "index.html"
        return str(APP/rel)
    def do_GET(self):
        path=urlparse(self.path).path
        if path=="/api/live":
            try:
                with lock:
                    now=time.time()
                    if cache["live"] is None or now-cache["live_at"]>=2.5:
                        cache["live"]=normalize(); cache["live_at"]=now; cache["error"]=None
                    data=cache["live"]
                self.send_json(data)
            except Exception as e:
                with lock: cache["error"]=str(e); old=cache["live"]
                if old:
                    old=dict(old); old["stale"]=True; old["error"]=str(e); self.send_json(old)
                else:
                    self.send_json({"game":{"status":"DATA LINK RETRYING"},"teamStats":{"DET":[],"BUF":[]},"plays":[],"error":str(e)},503)
            return
        if path=="/api/rosters":
            try:
                with lock:
                    now=time.time()
                    if cache["rosters"] is None or now-cache["roster_at"]>=300:
                        cache["rosters"]=rosters(); cache["roster_at"]=now
                    data=cache["rosters"]
                self.send_json({"players":data,"fetchedAt":cache["roster_at"]})
            except Exception as e: self.send_json({"players":[],"error":str(e)},503)
            return
        if path=="/api/status":
            self.send_json({"eventId":EVENT_ID,"liveCached":cache["live"] is not None,"rosterCached":cache["rosters"] is not None,"error":cache["error"]})
            return
        super().do_GET()
    def send_json(self,obj,status=200):
        b=json.dumps(obj).encode()
        self.send_response(status); self.send_header("Content-Type","application/json"); self.send_header("Cache-Control","no-store"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def log_message(self,fmt,*args): pass

if __name__=="__main__":
    os.chdir(APP)
    server=ThreadingHTTPServer((HOST,PORT),Handler)
    url=f"http://{HOST}:{PORT}"
    print("="*58)
    print(" NFL 2050 LIVE ENGINE")
    print(f" Game: DET @ BUF | ESPN Event {EVENT_ID}")
    print(f" App:  {url}")
    print(" Hosted NFL 2050 service is running.")
    print(" Press Ctrl+C to stop.")
    print("="*58)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
