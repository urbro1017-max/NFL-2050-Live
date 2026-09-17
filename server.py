import json, os, time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from pathlib import Path

HOST="0.0.0.0"; PORT=int(os.environ.get("PORT","10000"))
ROOT=Path(__file__).parent/"app"; GAME_ID="401872932"
CDN=f"https://cdn.espn.com/core/nfl/game?xhr=1&gameId={GAME_ID}"
SUMMARY=f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={GAME_ID}"
ROSTERS={"DET":"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/det/roster",
         "BUF":"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/buf/roster"}
cache={}

def fetch(url):
    req=Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    with urlopen(req,timeout=10) as r:return json.loads(r.read().decode())

def cached(k,url,ttl):
    if k not in cache or time.time()-cache[k][0]>ttl:
        cache[k]=(time.time(),fetch(url))
    return cache[k][1]

def live():
    raw=cached("cdn",CDN,2); pkg=raw.get("gamepackageJSON",raw)
    # Summary often has richer player/team boxscore; if unavailable, CDN still powers game state.
    try: summary=cached("summary",SUMMARY,3)
    except: summary={}
    header=(summary or pkg).get("header",{})
    comp=((header.get("competitions") or [{}])[0]); competitors=comp.get("competitors") or []
    out={"game":{},"plays":[],"team_stats":{},"players":[]}
    for c in competitors:
        ab=((c.get("team") or {}).get("abbreviation") or "").upper()
        if ab in ("DET","BUF"):
            out["game"][ab.lower()+"Score"]=c.get("score",0)
            out["game"][ab.lower()+"Record"]=(((c.get("records") or [{}])[0]).get("summary"))
    status=comp.get("status") or {}; typ=status.get("type") or {}
    out["game"].update(status=typ.get("shortDetail") or typ.get("description") or typ.get("state"),
                       clock=status.get("displayClock"),period=status.get("period"))
    # Team box score
    teams=((summary.get("boxscore") or {}).get("teams") or [])
    by={}
    for t in teams:
        ab=((t.get("team") or {}).get("abbreviation") or "").upper()
        by[ab]={s.get("label") or s.get("name"):s.get("displayValue") for s in t.get("statistics") or []}
    labels=["Total Yards","Passing Yards","Rushing Yards","1st Downs","3rd Down Efficiency","Possession Time"]
    for lab in labels: out["team_stats"][lab]=[by.get("DET",{}).get(lab,"—"),by.get("BUF",{}).get(lab,"—")]
    # Player box score
    for grp in ((summary.get("boxscore") or {}).get("players") or []):
        ab=((grp.get("team") or {}).get("abbreviation") or "").upper()
        for cat in grp.get("statistics") or []:
            cname=cat.get("name") or cat.get("type") or cat.get("label")
            labels2=cat.get("labels") or []
            for a in cat.get("athletes") or []:
                ath=a.get("athlete") or {}
                vals=a.get("stats") or []
                out["players"].append({"team":ab,"name":ath.get("displayName"),"id":ath.get("id"),
                    "category":cname,"stats":dict(zip(labels2,vals))})
    # Plays
    plays=summary.get("plays") or []
    if not plays:
        drives=pkg.get("drives") or {}; cur=drives.get("current"); prev=drives.get("previous") or []
        for d in ([cur] if cur else [])+prev[-4:]:
            for p in (d or {}).get("plays") or []: plays.append(p)
    for p in plays[-15:]:
        out["plays"].append({"clock":((p.get("clock") or {}).get("displayValue")),"text":p.get("text")})
    return out

def roster():
    out=[]
    for ab,url in ROSTERS.items():
        try:
            data=cached("roster"+ab,url,300)
            # site roster schema groups athletes under athletes[] entries
            groups=data.get("athletes") or []
            for g in groups:
                pos=g.get("position") or ""
                for a in g.get("items") or []:
                    out.append({"team":ab,"name":a.get("fullName") or a.get("displayName"),
                                "id":a.get("id"),"pos":((a.get("position") or {}).get("abbreviation") or pos)})
        except: pass
    return out

class H(SimpleHTTPRequestHandler):
    def __init__(self,*a,**k):super().__init__(*a,directory=str(ROOT),**k)
    def js(self,o,s=200):
        b=json.dumps(o).encode();self.send_response(s);self.send_header("Content-Type","application/json")
        self.send_header("Cache-Control","no-store");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
    def do_GET(self):
        p=urlparse(self.path).path
        if p=="/api/status":return self.js({"ok":True,"gameId":GAME_ID,"connected":["live game","team boxscore","player boxscore","rosters"]})
        if p=="/api/live":
            try:return self.js(live())
            except Exception as e:return self.js({"error":"upstream unavailable","detail":str(e)},502)
        if p=="/api/rosters":return self.js({"players":roster()})
        if p=="/":self.path="/index.html"
        return super().do_GET()
if __name__=="__main__":ThreadingHTTPServer((HOST,PORT),H).serve_forever()
