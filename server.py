import json, os, time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from pathlib import Path

HOST="0.0.0.0"; PORT=int(os.environ.get("PORT","10000")); ROOT=Path(__file__).parent/"app"
GAME_ID="401872932"; YEAR=2026
URLS={
"game":f"https://cdn.espn.com/core/nfl/game?xhr=1&gameId={GAME_ID}",
"summary":f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={GAME_ID}",
"standings":f"https://site.api.espn.com/apis/v2/sports/football/nfl/league/standings?season={YEAR}",
"news":"https://site.api.espn.com/apis/site/v2/sports/football/nfl/news?limit=12",
"det_schedule":f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/det/schedule?season={YEAR}",
"buf_schedule":f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/buf/schedule?season={YEAR}",
"det_roster":"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/det/roster",
"buf_roster":"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/buf/roster"}
cache={}
def fetch(url):
    req=Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    with urlopen(req,timeout=10) as r:return json.loads(r.read().decode())
def get(k,ttl=30):
    if k not in cache or time.time()-cache[k][0]>ttl: cache[k]=(time.time(),fetch(URLS[k]))
    return cache[k][1]
def safe(k,ttl=30):
    try:return get(k,ttl)
    except:return {}

def game_data():
    raw=safe("game",2); pkg=raw.get("gamepackageJSON",raw); summ=safe("summary",3)
    source=summ if summ.get("header") else pkg
    comp=((source.get("header",{}).get("competitions") or [{}])[0]); cs=comp.get("competitors") or []
    out={"game":{},"plays":[],"team_stats":{},"players":[]}
    for c in cs:
        ab=((c.get("team") or {}).get("abbreviation") or "").upper()
        if ab in ("DET","BUF"):
            out["game"][ab.lower()+"Score"]=c.get("score",0)
            rec=c.get("records") or []
            if rec: out["game"][ab.lower()+"Record"]=rec[0].get("summary")
    st=comp.get("status") or {}; typ=st.get("type") or {}
    out["game"].update(status=typ.get("shortDetail") or typ.get("description") or typ.get("state"),
      clock=st.get("displayClock"),period=st.get("period"))
    teams=((summ.get("boxscore") or {}).get("teams") or [])
    maps={}
    for t in teams:
        ab=((t.get("team") or {}).get("abbreviation") or "").upper()
        maps[ab]={str(x.get("label") or x.get("name")):x.get("displayValue") for x in t.get("statistics") or []}
    all_labels=sorted(set(maps.get("DET",{}))|set(maps.get("BUF",{})))
    for lab in all_labels: out["team_stats"][lab]=[maps.get("DET",{}).get(lab,"—"),maps.get("BUF",{}).get(lab,"—")]
    for grp in ((summ.get("boxscore") or {}).get("players") or []):
        ab=((grp.get("team") or {}).get("abbreviation") or "").upper()
        for cat in grp.get("statistics") or []:
            cname=cat.get("name") or cat.get("label") or "Stats"; labs=cat.get("labels") or []
            for a in cat.get("athletes") or []:
                ath=a.get("athlete") or {}; vals=a.get("stats") or []
                out["players"].append({"team":ab,"name":ath.get("displayName"),"id":ath.get("id"),
                    "category":cname,"stats":dict(zip(labs,vals))})
    plays=summ.get("plays") or []
    if not plays:
        dr=pkg.get("drives") or {}; ds=([dr.get("current")] if dr.get("current") else [])+(dr.get("previous") or [])[-4:]
        for d in ds:
            for p in (d or {}).get("plays") or []:plays.append(p)
    out["plays"]=[{"clock":((p.get("clock") or {}).get("displayValue")),"text":p.get("text")} for p in plays[-18:]]
    return out

def roster():
    out=[]
    for ab,k in [("DET","det_roster"),("BUF","buf_roster")]:
        d=safe(k,300)
        for g in d.get("athletes") or []:
            gp=g.get("position") if isinstance(g.get("position"),str) else ""
            for a in g.get("items") or []:
                pos=(a.get("position") or {}).get("abbreviation") or gp or "—"
                out.append({"team":ab,"name":a.get("fullName") or a.get("displayName"),"id":a.get("id"),"pos":pos,
                            "jersey":a.get("jersey"),"age":a.get("age"),"experience":((a.get("experience") or {}).get("years"))})
    return out

def standings():
    d=safe("standings",120); rows=[]
    def walk(node):
        if isinstance(node,dict):
            if "standings" in node and isinstance(node["standings"],dict):
                for e in node["standings"].get("entries") or []:
                    team=e.get("team") or {}; stats={x.get("name"):x.get("displayValue") for x in e.get("stats") or []}
                    rows.append({"team":team.get("displayName"),"abbr":team.get("abbreviation"),"logo":team.get("logos",[{}])[0].get("href") if team.get("logos") else None,
                                 "wins":stats.get("wins"),"losses":stats.get("losses"),"ties":stats.get("ties"),"pct":stats.get("winPercent"),
                                 "pf":stats.get("pointsFor"),"pa":stats.get("pointsAgainst"),"streak":stats.get("streak")})
            for v in node.values(): walk(v)
        elif isinstance(node,list):
            for v in node:walk(v)
    walk(d)
    uniq={r["abbr"]:r for r in rows if r.get("abbr")}
    return list(uniq.values())

def schedules():
    out={}
    for ab,k in [("DET","det_schedule"),("BUF","buf_schedule")]:
        d=safe(k,120); arr=[]
        for e in d.get("events") or []:
            comp=(e.get("competitions") or [{}])[0]; cs=comp.get("competitors") or []
            opp=None
            for c in cs:
                ca=((c.get("team") or {}).get("abbreviation") or "").upper()
                if ca and ca!=ab: opp=(c.get("team") or {}).get("displayName")
            st=(comp.get("status") or {}).get("type") or {}
            arr.append({"date":e.get("date"),"name":e.get("name"),"opponent":opp,"status":st.get("shortDetail") or st.get("description")})
        out[ab]=arr
    return out

def news():
    d=safe("news",120); return [{"headline":a.get("headline"),"description":a.get("description"),"published":a.get("published")} for a in d.get("articles") or []]

class H(SimpleHTTPRequestHandler):
    def __init__(self,*a,**k):super().__init__(*a,directory=str(ROOT),**k)
    def js(self,o,s=200):
        b=json.dumps(o).encode();self.send_response(s);self.send_header("Content-Type","application/json");self.send_header("Cache-Control","no-store");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
    def do_GET(self):
        p=urlparse(self.path).path
        try:
            if p=="/api/status":return self.js({"ok":True,"gameId":GAME_ID})
            if p=="/api/live":return self.js(game_data())
            if p=="/api/rosters":return self.js({"players":roster()})
            if p=="/api/standings":return self.js({"standings":standings()})
            if p=="/api/schedules":return self.js(schedules())
            if p=="/api/news":return self.js({"articles":news()})
        except Exception as e:return self.js({"error":str(e)},502)
        if p=="/":self.path="/index.html"
        return super().do_GET()
if __name__=="__main__":
    print("HuddleIntel V7",HOST,PORT);ThreadingHTTPServer((HOST,PORT),H).serve_forever()
