import json, os, time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from pathlib import Path

HOST="0.0.0.0"; PORT=int(os.environ.get("PORT","10000")); ROOT=Path(__file__).parent/"app"
YEAR=2026
URLS={
"standings":f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/league/standings?season={YEAR}",
"news":"https://site.api.espn.com/apis/site/v2/sports/football/nfl/news?limit=12",
"det_schedule":f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/det/schedule?season={YEAR}",
"buf_schedule":f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/buf/schedule?season={YEAR}",
"det_roster":"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/det/roster",
"buf_roster":"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/buf/roster"}
cache={}
def fetch(url):
    req=Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    with urlopen(req,timeout=10) as r:return json.loads(r.read().decode())
def get(k,ttl=30,url=None):
    key=url or k
    if key not in cache or time.time()-cache[key][0]>ttl: cache[key]=(time.time(),fetch(url or URLS[k]))
    return cache[key][1]
def safe(k,ttl=30,url=None):
    try:return get(k,ttl,url)
    except:return {}

def current_game_id():
    """Find this season's DET-vs-BUF game dynamically instead of a hardcoded,
    quickly-stale event id. Looks at DET's schedule for the game against BUF
    and picks the closest one to now (handles the rare case of two meetings
    in a season, e.g. a playoff rematch)."""
    d=safe("det_schedule",600)
    best=None;best_diff=None;now=time.time()
    for e in d.get("events") or []:
        comp=(e.get("competitions") or [{}])[0]; cs=comp.get("competitors") or []
        opp=None
        for c in cs:
            ab=((c.get("team") or {}).get("abbreviation") or "").upper()
            if ab=="BUF": opp=True
        if opp:
            try:
                ts=time.mktime(time.strptime(e.get("date","")[:19],"%Y-%m-%dT%H:%M:%S"))
            except Exception:
                ts=now
            diff=abs(ts-now)
            if best_diff is None or diff<best_diff: best=e.get("id"); best_diff=diff
    return best

def game_data():
    gid=current_game_id()
    if not gid: return {"game":{},"plays":[],"team_stats":{},"players":[]}
    raw=safe("game",2,url=f"https://cdn.espn.com/core/nfl/game?xhr=1&gameId={gid}")
    pkg=raw.get("gamepackageJSON",raw)
    summ=safe("summary",3,url=f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={gid}")
    source=summ if summ.get("header") else pkg
    comp=((source.get("header",{}).get("competitions") or [{}])[0]); cs=comp.get("competitors") or []
    out={"game":{"eventId":gid},"plays":[],"team_stats":{},"players":[]}
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

def odds_data():
    """Win probability + betting lines for the tracked game. ESPN's summary
    payload carries these under 'predictor' (pregame model) and 'pickcenter'
    (market lines) — best-effort parse; returns {} if the game/feed isn't
    available yet rather than guessing at values."""
    gid=current_game_id()
    if not gid: return {}
    summ=safe("summary",3,url=f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={gid}")
    out={}
    try:
        pred=summ.get("predictor") or {}
        if pred:
            out["homeWinPct"]=(pred.get("homeTeam") or {}).get("gameProjection")
            out["awayWinPct"]=(pred.get("awayTeam") or {}).get("gameProjection")
    except Exception: pass
    try:
        pc=(summ.get("pickcenter") or [])
        if pc:
            p=pc[0]
            out["spread"]=p.get("details")
            out["overUnder"]=p.get("overUnder")
            out["provider"]=(p.get("provider") or {}).get("name")
            out["awayMoneyline"]=(p.get("awayTeamOdds") or {}).get("moneyLine")
            out["homeMoneyline"]=(p.get("homeTeamOdds") or {}).get("moneyLine")
    except Exception: pass
    return out

def scoreval(c):
    s=c.get("score")
    if isinstance(s,dict): return s.get("value") or s.get("displayValue")
    return s

def head_to_head():
    """Recent DET-vs-BUF meetings, pulled from DET's schedule across the last
    several seasons. Only returns games ESPN marks completed."""
    out=[]
    for yr in range(YEAR-6,YEAR+1):
        d=safe(f"det_sched_{yr}",86400,url=f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/det/schedule?season={yr}")
        for e in d.get("events") or []:
            comp=(e.get("competitions") or [{}])[0]; cs=comp.get("competitors") or []
            det_s=buf_s=None; is_h2h=False
            for c in cs:
                ab=((c.get("team") or {}).get("abbreviation") or "").upper()
                if ab=="BUF": is_h2h=True; buf_s=scoreval(c)
                if ab=="DET": det_s=scoreval(c)
            st=(comp.get("status") or {}).get("type") or {}
            if is_h2h and st.get("completed"):
                winner=None
                try:
                    if float(det_s)>float(buf_s): winner="DET"
                    elif float(buf_s)>float(det_s): winner="BUF"
                except Exception: pass
                out.append({"date":e.get("date"),"season":yr,"detScore":det_s,"bufScore":buf_s,"winner":winner})
    out.sort(key=lambda x:x.get("date") or "",reverse=True)
    return out

def player_detail(pid):
    """Bio + season stats for one player. Best-effort against ESPN's
    undocumented athlete endpoints: if the shape doesn't match, sections
    just come back empty rather than raising, consistent with the rest of
    this app never inventing data it doesn't have."""
    bio={}
    try:
        d=safe(f"athlete_{pid}",3600,url=f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/athletes/{pid}")
        a=d.get("athlete") or d
        bp=a.get("birthPlace") or {}
        bio={"name":a.get("displayName"),"jersey":a.get("jersey"),
             "position":(a.get("position") or {}).get("abbreviation"),
             "height":a.get("displayHeight"),"weight":a.get("displayWeight"),
             "age":a.get("age"),"experience":((a.get("experience") or {}).get("years")),
             "college":(a.get("college") or {}).get("name"),
             "birthPlace":", ".join([x for x in [bp.get("city"),bp.get("state")] if x]),
             "headshot":(a.get("headshot") or {}).get("href") or f"https://a.espncdn.com/i/headshots/nfl/players/full/{pid}.png"}
    except Exception: pass
    stats=[]
    try:
        d2=safe(f"athlete_stats_{pid}",3600,url=f"https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{pid}/stats")
        cats=d2.get("categories") or (d2.get("splits") or {}).get("categories") or []
        for cat in cats:
            names=cat.get("names") or cat.get("labels") or []
            vals=(cat.get("statistics") or [{}])[0].get("stats") if cat.get("statistics") else cat.get("stats")
            if isinstance(vals,list) and names:
                stats.append({"name":cat.get("displayName") or cat.get("name"),"stats":dict(zip(names,vals))})
    except Exception: pass
    return {"bio":bio,"seasonStats":stats}

def roster():
    out=[]
    for ab,k in [("DET","det_roster"),("BUF","buf_roster")]:
        d=safe(k,300)
        for g in d.get("athletes") or []:
            gp=g.get("position") if isinstance(g.get("position"),str) else ""
            for a in g.get("items") or []:
                pos=(a.get("position") or {}).get("abbreviation") or gp or "—"
                pid=a.get("id")
                out.append({"team":ab,"name":a.get("fullName") or a.get("displayName"),"id":pid,"pos":pos,
                            "jersey":a.get("jersey"),"age":a.get("age"),"experience":((a.get("experience") or {}).get("years")),
                            "headshot":f"https://a.espncdn.com/i/headshots/nfl/players/full/{pid}.png" if pid else None})
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
                                 "pf":stats.get("pointsFor"),"pa":stats.get("pointsAgainst"),"streak":stats.get("streak"),
                                 "stats":stats})
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
            if p=="/api/status":
                gid=current_game_id()
                checks={}
                for k in ["standings","news","det_roster","buf_roster"]:
                    try: checks[k]=bool(safe(k,5))
                    except: checks[k]=False
                checks["game"]=bool(gid)
                return self.js({"ok":True,"gameId":gid,"sources":checks})
            if p=="/api/live":return self.js(game_data())
            if p=="/api/rosters":return self.js({"players":roster()})
            if p=="/api/standings":return self.js({"standings":standings()})
            if p=="/api/schedules":return self.js(schedules())
            if p=="/api/news":return self.js({"articles":news()})
            if p=="/api/odds":return self.js(odds_data())
            if p=="/api/h2h":return self.js({"games":head_to_head()})
            if p.startswith("/api/player/"):
                pid=p.rsplit("/",1)[-1]
                if pid: return self.js(player_detail(pid))
        except Exception as e:return self.js({"error":str(e)},502)
        # SPA fallback: any non-file, non-api path (e.g. /matchup, /players,
        # a bookmark or a page refresh on a tab) serves index.html instead of
        # 404ing, so deep links and refreshes always land on a working page.
        target=ROOT/p.lstrip("/")
        if p=="/" or not target.is_file():
            self.path="/index.html"
        return super().do_GET()
if __name__=="__main__":
    print("HuddleIntel V7",HOST,PORT);ThreadingHTTPServer((HOST,PORT),H).serve_forever()
