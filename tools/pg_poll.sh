cd /opt/banksy/front-desk
umask 077
cat > /tmp/.pg3 <<'TOK'
eyJhbGciOiJSUzI1NiIsImprdSI6Ii9vYXV0aC9pbnRlcm5hbC9qd2tzIiwia2lkIjoiZDc0YjNhMWUiLCJ0eXAiOiJKV1QifQ.eyJhcHBfaWQiOiJSaW5nRGV2ZWxvcGVyUG9ydGFsUGxheWdyX0pmRHJ5dm5JbUVUUjFQbU5DZzIxYSIsImNpZCI6ImF2YTEucmluZy5jbGllbnQuVlZZV0M3U1BQV1JFT1BJWklMNElISkY0MkgzSTNOWjRQSlhDSFZQVllBWTJTT01SSlg2RkdBSDVaRkwyU0pTSkg3S1pCSVhONEFJSjVEVEpHMlNKV1hRSlBRSlRXVFpCRzJSSkdITk5CQjY0QlZSWkFIN1dVWTVQUTZNVkRGWE9IR0pCQlZVRk9QUDRHMjJHVkxQSU4yNk9aWk5VSTJNVVhKTzdPUlBSNFRQRElJQ0pIUEZJSkJTNUJGNFdYNllTTkRSNEhYUSIsImV4cCI6MTc4OTU4ODE2NSwiaGFyZHdhcmVfaWQiOiJ1bmRlZmluZWQiLCJpYXQiOjE3ODk1ODYzNjUsImlzcyI6IlJpbmdPYXV0aFNlcnZpY2UtcHJvZDp1cy1lYXN0LTE6MS4wLjMzODcuMCIsIm9pYXQiOjE3ODk1ODYzNjUsIm9uX2JlaGFsZl9vZiI6ImF2YTEucmluZy5hY2NvdW50LjVDVEJCUEtZN1ZJRzdWWU9NVTJYMjVLR0xUSFE2T1E1RkhTUE1FTDYzTEFDS0wyTVlQQjRVMlFTRlhaVEtYWUNKTEUyQ05WQ0dBVTI2UUpXSjRGT1lBWlRGWkdKMlZGTSIsInJuZCI6Ik1VYnFzWlRqREoiLCJzY29wZXMiOlsiYXZhLnYxOnJlYWQiXSwic2Vzc2lvbl9pZCI6InJpbmctc2Vzc2lvbi1lMWFlMDRhZi0zZmUwLTQ5NTctODJkMi00ZTg1MDY5NDVhNzgiLCJzc3QiOjF9.Jwt6FKiXbNiCRCA903L6JkqEyxjcNiYyoTc86Ava-qPuD9Voxp9mz6Q-YKNrS9c1DFjJQtP8i1Js8ns4l9peEikVJSzOdDcH7-_CrGM_BFR6DhO_N-JMrKYoNWKTI74Z5HSONQNyEYB509W03jSR1zdb_6zzToMf8eW_PuWET4KJ4Lla4u34fIR9yFkZ5kNLxc_KACksEnND7PLWVRkBhSrHzahtqtpgpBgeaQQk7YisRCmVX5iZ7U1JffMTwSQ_ueDjIZ-GS0yf3sfoKfEJKDzyJZcM6CaRM9SXcEoSDTMXEIl-Gdv1OTzYQPFbKpstSjUpKyt8euK3K80NzfaS6A
TOK

mkdir -p data/playground
nohup ./.venv/bin/python - > data/playground/poll.log 2>&1 <<'PY' &
import json, time, urllib.request, urllib.error, os

tok = open("/tmp/.pg3").read().strip()
DEV = None
seen = set()
OUT = "/opt/banksy/front-desk/data/playground"

def call(p):
    r = urllib.request.Request("https://api.amazonvision.com" + p,
                               headers={"Authorization": "Bearer " + tok})
    try:
        with urllib.request.urlopen(r, timeout=25) as x:
            return x.status, json.loads(x.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:200].decode(errors="replace")
    except Exception as e:
        return 0, str(e)

code, body = call("/v1/devices")
if isinstance(body, dict) and body.get("data"):
    DEV = body["data"][0]["id"]
    print("watching:", (body["data"][0].get("attributes") or {}).get("name"), flush=True)
else:
    print("no device:", body, flush=True)
    raise SystemExit(1)

deadline = time.time() + 900          # 15 minutes
print("polling every 8s for 15 minutes...\n", flush=True)
while time.time() < deadline:
    code, body = call(f"/v1/history/devices/{DEV}/events?limit=20&include=cv_detections")
    if isinstance(body, dict):
        for e in body.get("data") or []:
            eid = e.get("id")
            if eid in seen:
                continue
            seen.add(eid)
            a = e.get("attributes") or {}
            print("-" * 64, flush=True)
            print(json.dumps(e, indent=2)[:1500], flush=True)
            if body.get("included"):
                print("INCLUDED:", json.dumps(body["included"], indent=2)[:900], flush=True)
            with open(os.path.join(OUT, f"{eid}.json"), "w") as fh:
                json.dump({"event": e, "included": body.get("included")}, fh, indent=2)
    time.sleep(8)
print("\npolling window closed.", flush=True)
PY
echo "poller started (15 min window) -> data/playground/poll.log"
sleep 12
cat data/playground/poll.log
