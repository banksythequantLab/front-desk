cd /opt/banksy/front-desk
exec > /tmp/pt.log 2>&1
set -a; . ./.env; set +a
./.venv/bin/python - <<'PY'
import json, sys, time
sys.path.insert(0, "/opt/banksy/front-desk")
import poller, ring_link

tok = ring_link.access_token()
print("token:", "yes" if tok else "NO")

devs, err = poller.api("/v1/devices", tok)
if err:
    print("devices failed:", err); raise SystemExit(1)

for d in devs.get("data") or []:
    did = d["id"]; name = (d.get("attributes") or {}).get("name")
    body, err = poller.api("/v1/history/devices/" + did + "/events?limit=3", tok)
    if err:
        print(name, "history failed:", err); continue
    evs = body.get("data") or []
    if not evs:
        print(name, "no events"); continue
    ev = poller.normalize(evs[0], did, name)
    print("=" * 56)
    print(name, "|", ev["event_type"], "| start", ev.get("_start"))
    t0 = time.time()
    path, ferr = poller.fetch_frame(did, ev, tok)
    print("  fetch: %.1fs" % (time.time() - t0), "->", ferr or path)
    if path:
        sys.path.insert(0, "/opt/banksy/front-desk/classifier")
        from classify import classify
        out = classify(path)
        obs = out.get("observations") or {}
        print("  disposition:", out.get("disposition"), "| escalate", out.get("escalate"))
        print("  notes      :", obs.get("notes"))
        import os
        os.unlink(path)
PY
