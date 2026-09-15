#!/usr/bin/env python3
"""Front Desk lobby dashboard — the Fire TV surface.

PRIVACY DECISION — this screen shows status and counts, never faces.
A lobby display is visible to everyone in the room, including other clients.
Who visits a lawyer is itself sensitive, so no image, no name and no per-visitor
identifying detail is rendered here. That is a deliberate product constraint,
not a missing feature.

NETWORK DECISION — binds to the LAN only and is NOT tunnelled to the internet.
The webhook receiver is public because Ring has to reach it. A lobby screen has
no reason to be, so it isn't.

Env:
  FRONTDESK_STORE  path to the JSONL store
  FD_DASH_PORT     default 8313
  FD_DASH_BIND     default 0.0.0.0 (LAN); set 127.0.0.1 to restrict further
"""

import json
import os
from collections import Counter
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from store import disposition, escalated, event_time, load_events, within

PORT = int(os.environ.get("FD_DASH_PORT", "8313"))
BIND = os.environ.get("FD_DASH_BIND", "0.0.0.0")

LABELS = {
    "delivery": "Deliveries",
    "possible_service": "Needs review",
    "visitor": "Visitors",
    "passerby": "Passed by",
    "parcel_removed": "Parcel removed",
    "parcel_present_no_person": "Parcel waiting",
    "no_person": "Motion only",
    "no_snapshot": "No image",
    "unclassified": "Pending",
    "error": "Errors",
}


def summary(hours=24):
    recs = [r for r in load_events() if within(r, hours)]
    counts = Counter(disposition(r) for r in recs)
    review = sum(1 for r in recs if escalated(r))
    latest = max((event_time(r) for r in recs if event_time(r)), default=None)
    return {
        "window_hours": hours,
        "total": len(recs),
        "needs_review": review,
        "counts": [{"key": k, "label": LABELS.get(k, k.replace("_", " ").title()),
                    "n": n} for k, n in counts.most_common()],
        "latest": latest.isoformat() if latest else None,
        "generated": datetime.now(timezone.utc).isoformat(),
    }


PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Front Desk</title>
<style>
  :root { --bg:#0b1019; --fg:#f0f4fa; --mute:#8a9ab0; --dim:#5c6a80;
          --acc:#40c4a8; --warn:#e8a850; --line:#26344a; }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { background:var(--bg); color:var(--fg); font-family:"Segoe UI",
         system-ui,-apple-system,sans-serif; padding:4vh 5vw; min-height:100vh; }
  /* 10-foot UI: everything sized so it reads across a lobby. */
  header { display:flex; justify-content:space-between; align-items:baseline;
           border-bottom:2px solid var(--line); padding-bottom:1.6vh; }
  h1 { font-size:3.4vh; letter-spacing:.14em; text-transform:uppercase;
       color:var(--mute); font-weight:600; }
  .clock { font-size:3.4vh; color:var(--dim); font-variant-numeric:tabular-nums; }
  .status { margin:6vh 0 5vh; }
  .headline { font-size:11vh; font-weight:700; line-height:1; }
  .ok { color:var(--acc); } .attn { color:var(--warn); }
  .sub { font-size:3.2vh; color:var(--mute); margin-top:1.6vh; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(22vw,1fr));
          gap:2.2vh 2vw; }
  .card { border:2px solid var(--line); border-radius:14px; padding:2.4vh 2vw; }
  .n { font-size:7vh; font-weight:700; line-height:1;
       font-variant-numeric:tabular-nums; }
  .lbl { font-size:2.4vh; color:var(--mute); margin-top:.8vh; }
  .card.flag { border-color:var(--warn); } .card.flag .n { color:var(--warn); }
  footer { position:fixed; left:5vw; right:5vw; bottom:3vh; display:flex;
           justify-content:space-between; font-size:2vh; color:var(--dim);
           border-top:1px solid var(--line); padding-top:1.4vh; }
  .dot { display:inline-block; width:1.1vh; height:1.1vh; border-radius:50%;
         background:var(--acc); margin-right:.8vh; vertical-align:middle; }
  .stale .dot { background:var(--warn); }
</style></head>
<body>
  <header>
    <h1>Front Desk</h1>
    <div class="clock" id="clock">--:--</div>
  </header>

  <div class="status">
    <div class="headline ok" id="headline">&mdash;</div>
    <div class="sub" id="sub">Loading&hellip;</div>
  </div>

  <div class="grid" id="grid"></div>

  <footer>
    <div id="health"><span class="dot"></span><span id="healthtext">connecting</span></div>
    <div>No images are shown on this screen.</div>
  </footer>

<script>
function tick(){
  const d=new Date();
  document.getElementById('clock').textContent =
    d.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
}
function ago(iso){
  if(!iso) return 'no events yet';
  const m = Math.floor((Date.now()-new Date(iso))/60000);
  if(m<1) return 'just now';
  if(m<60) return m+' min ago';
  const h=Math.floor(m/60);
  return h+' hr'+(h>1?'s':'')+' ago';
}
async function refresh(){
  const f=document.getElementById('health');
  try{
    const r=await fetch('/api/summary',{cache:'no-store'});
    const d=await r.json();
    const head=document.getElementById('headline');
    const sub=document.getElementById('sub');
    if(d.needs_review>0){
      head.textContent=d.needs_review;
      head.className='headline attn';
      sub.textContent=d.needs_review===1?'event needs a look':'events need a look';
    } else {
      head.textContent='All clear';
      head.className='headline ok';
      sub.textContent=d.total+' event'+(d.total===1?'':'s')+' in the last '+
                      d.window_hours+' hours \\u00b7 last '+ago(d.latest);
    }
    document.getElementById('grid').innerHTML = d.counts.length
      ? d.counts.map(c=>'<div class="card'+(c.key==='possible_service'?' flag':'')+
          '"><div class="n">'+c.n+'</div><div class="lbl">'+c.label+'</div></div>').join('')
      : '<div class="card"><div class="n">0</div><div class="lbl">Nothing today</div></div>';
    f.classList.remove('stale');
    document.getElementById('healthtext').textContent='live';
  }catch(e){
    f.classList.add('stale');
    document.getElementById('healthtext').textContent='reconnecting';
  }
}
tick(); refresh();
setInterval(tick,10000);
setInterval(refresh,15000);
</script>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "FrontDeskDash/0.1"

    def log_message(self, *a):
        pass                      # a lobby screen polls constantly; don't spam

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            body = PAGE.encode()
            ctype = "text/html; charset=utf-8"
        elif path == "/api/summary":
            body = json.dumps(summary()).encode()
            ctype = "application/json"
        else:
            body = b'{"error":"not found"}'
            ctype = "application/json"
        self.send_response(200 if not body.startswith(b'{"error"') else 404)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    srv = ThreadingHTTPServer((BIND, PORT), Handler)
    print(f"Front Desk dashboard on http://{BIND}:{PORT}  (LAN only, not tunnelled)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
