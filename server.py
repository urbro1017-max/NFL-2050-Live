import json,os
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from urllib.request import Request,urlopen
from pathlib import Path
HOST="0.0.0.0";PORT=int(os.environ.get("PORT","10000"));ROOT=Path(__file__).parent/"app"
# Verified Sep 17, 2026: ESPN event 401872932 resolves to DET at BUF, 2026 Week 2.
GAME_ID="401872932"
URL=f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={GAME_ID}"
FALLBACK=f"https://cdn.espn.com/core/nfl/game?xhr=1&gameId={GAME_ID}"
def fetch(u):
 req=Request(u,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
 with urlopen(req,timeout=8) as r:return json.loads(r.read().decode())
def live():
 out={"game":{"status":"Pregame","detScore":0,"bufScore":0,"period":0,"clock":"—","possession":"—","downDistance":"—","ballSpot":"—"},"plays":[],"team_stats":{},"players":[],"linescores":{"DET":[],"BUF":[]},"drives":[]}
 try:d=fetch(URL)
 except:
  try:
   d=fetch(FALLBACK);d=d.get("gamepackageJSON",d)
  except:return out
 comp=((d.get("header",{}).get("competitions") or [{}])[0])
 for c in comp.get("competitors") or []:
  ab=((c.get("team") or {}).get("abbreviation") or "").upper()
  if ab=="DET":out["game"]["detScore"]=c.get("score",0)
  if ab=="BUF":out["game"]["bufScore"]=c.get("score",0)
  if ab in ("DET","BUF"):out["linescores"][ab]=[x.get("displayValue",x.get("value")) for x in (c.get("linescores") or [])]
 st=comp.get("status") or {};typ=st.get("type") or {}
 out["game"]["status"]=typ.get("shortDetail") or typ.get("description") or "Pregame"
 out["game"]["period"]=st.get("period") or 0
 out["game"]["clock"]=st.get("displayClock") or (st.get("clock") or {}).get("displayValue") or "—"
 # Team box score
 for t in ((d.get("boxscore") or {}).get("teams") or []):
  ab=((t.get("team") or {}).get("abbreviation") or "").upper()
  if ab not in ("DET","BUF"):continue
  out["team_stats"][ab]={str(x.get("label") or x.get("name")):x.get("displayValue") for x in (t.get("statistics") or [])}
 # Player box score
 for grp in ((d.get("boxscore") or {}).get("players") or []):
  ab=((grp.get("team") or {}).get("abbreviation") or "").upper()
  for cat in grp.get("statistics") or []:
   cname=cat.get("name") or cat.get("label") or "stats"; labels=cat.get("labels") or []
   for row in cat.get("athletes") or []:
    a=row.get("athlete") or {}; vals=row.get("stats") or []
    out["players"].append({"team":ab,"name":a.get("displayName"),"category":cname,"stats":dict(zip(labels,vals))})
 rawplays=(d.get("plays") or [])
 for p in rawplays[-24:]:out["plays"].append({"clock":(p.get("clock") or {}).get("displayValue"),"text":p.get("text")})
 if rawplays:
  lp=rawplays[-1]; out["game"]["downDistance"]=lp.get("shortText") or lp.get("text","")[:42]
  out["game"]["ballSpot"]=((lp.get("end") or {}).get("yardLine")) or "—"
  out["game"]["possession"]=((lp.get("team") or {}).get("abbreviation")) or "—"
 drives=((d.get("drives") or {}).get("previous") or [])[-8:]
 for dr in drives:
  tm=((dr.get("team") or {}).get("abbreviation")) or "—"; desc=dr.get("description") or dr.get("displayResult") or dr.get("result") or "Drive"
  out["drives"].append({"team":tm,"result":desc,"yards":dr.get("yards"),"time":dr.get("timeElapsed"),"start":dr.get("start"),"end":dr.get("end"),"plays":dr.get("offensivePlays") or dr.get("plays")})
 return out

class H(SimpleHTTPRequestHandler):
 def __init__(self,*a,**k):super().__init__(*a,directory=str(ROOT),**k)
 def do_GET(self):
  if self.path.startswith("/api/live"):
   b=json.dumps(live()).encode();self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Cache-Control","no-store");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b);return
  if self.path=="/":self.path="/index.html"
  super().do_GET()
if __name__=="__main__":ThreadingHTTPServer((HOST,PORT),H).serve_forever()
