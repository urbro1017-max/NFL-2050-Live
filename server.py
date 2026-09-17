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
 out={"game":{"status":"Pregame","detScore":0,"bufScore":0},"plays":[]}
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
 st=comp.get("status") or {};typ=st.get("type") or {}
 out["game"]["status"]=typ.get("shortDetail") or typ.get("description") or "Pregame"
 for p in (d.get("plays") or [])[-20:]:out["plays"].append({"clock":(p.get("clock") or {}).get("displayValue"),"text":p.get("text")})
 return out
class H(SimpleHTTPRequestHandler):
 def __init__(self,*a,**k):super().__init__(*a,directory=str(ROOT),**k)
 def do_GET(self):
  if self.path.startswith("/api/live"):
   b=json.dumps(live()).encode();self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Cache-Control","no-store");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b);return
  if self.path=="/":self.path="/index.html"
  super().do_GET()
if __name__=="__main__":ThreadingHTTPServer((HOST,PORT),H).serve_forever()
