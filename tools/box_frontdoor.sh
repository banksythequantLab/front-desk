cd /opt/banksy/front-desk
exec > /tmp/fd.log 2>&1
set -a; . ./.env; set +a
./.venv/bin/python - <<'PY'
import json, sys, time, urllib.request, urllib.error
sys.path.insert(0, "/opt/banksy/front-desk")
sys.path.insert(0, "/opt/banksy/front-desk/classifier")
import ring_link

tok = ring_link.access_token()
UA = ring_link.USER_AGENT
DEV = None

class NoRedir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None
op = urllib.request.build_opener(NoRedir)

def api(path):
    r = urllib.request.Request(ring_link.AVA_BASE + path,
        headers={"Authorization": "Bearer " + tok, "User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(r, timeout=40) as x:
        return json.loads(x.read() or b"{}")

devs = api("/v1/devices")
for d in devs.get("data") or []:
    if (d.get("attributes") or {}).get("name") == "Front Door":
        DEV = d["id"]
print("front door:", DEV[:40], "...")

hist = api("/v1/history/devices/" + DEV + "/events?limit=6")
ev = (hist.get("data") or [])
if not ev:
    print("no events"); raise SystemExit(0)
a = ev[0].get("attributes") or {}
mid = int((a["start"] + a["end"]) / 2)
print("event:", a.get("event_type"), "mid-timestamp:", mid)

body = {"type": "at_timestamp", "timestamp": mid,
        "image_options": {"format": "jpeg",
                          "resolution": {"width": 1920, "height": 1080}}}
r = urllib.request.Request(
    ring_link.AVA_BASE + "/v1/devices/" + DEV + "/media/image/download",
    data=json.dumps(body).encode(), method="POST",
    headers={"Authorization": "Bearer " + tok, "User-Agent": UA,
             "Accept": "*/*", "Content-Type": "application/json"})
try:
    with op.open(r, timeout=60) as x:
        st, hdrs = x.status, dict(x.headers)
except urllib.error.HTTPError as e:
    # With redirects disabled urllib RAISES on the 303 rather than returning
    # it. The pre-signed URL is on e.headers, so this is the success path.
    st, hdrs = e.code, dict(e.headers)

loc = hdrs.get("Location") or hdrs.get("location")
print("HTTP", st, "| pre-signed URL:", "yes" if loc else "no")
if not loc:
    raise SystemExit(0)

with urllib.request.urlopen(urllib.request.Request(loc, headers={"User-Agent": UA}), timeout=60) as x:
    img = x.read(); ih = dict(x.headers)
p = "/opt/banksy/front-desk/data/frontdoor.jpg"
open(p, "wb").write(img)
print("saved", len(img), "bytes  origin:", ih.get("X-Media-Origin"))

from classify import classify
t0 = time.time()
out = classify(p)
obs = out.get("observations") or {}
print("--- classifier on YOUR front door ---")
print("elapsed     : %.1fs" % (time.time() - t0))
print("disposition :", out.get("disposition"), "| escalate", out.get("escalate"))
print("notes       :", obs.get("notes"))
print("lighting    :", obs.get("lighting"), "| quality:", obs.get("image_quality"))
PY
