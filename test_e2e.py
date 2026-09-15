#!/usr/bin/env python3
"""End-to-end: signed webhook -> snapshot fetch -> VLM -> rules -> MCP.

Serves a real image locally so the worker has something to actually fetch,
then reads the result back through the MCP server the way Alexa+ would.
"""
import asyncio, hashlib, hmac, json, os, shutil, subprocess, sys, time
import urllib.request

ROOT = r"D:\front-desk"
FIX = os.path.join(ROOT, "_fixtures")
STORE = os.path.join(ROOT, "e2e_events.jsonl")
KEY = "e2e-test-key"
IMG_SRC = r"B:\pitch\10767.jpg"

results = []
def check(name, ok, detail=""):
    results.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:<40} {detail}")

os.makedirs(FIX, exist_ok=True)
shutil.copy(IMG_SRC, os.path.join(FIX, "snap.jpg"))
for f in (STORE,):
    if os.path.exists(f):
        os.remove(f)

env = dict(os.environ, FRONTDESK_HMAC_KEY=KEY, FRONTDESK_STORE=STORE,
           FRONTDESK_PORT="8310", FD_MCP_PORT="8311")

procs = []
def spawn(args, cwd=ROOT):
    # DEVNULL, not PIPE: nobody drains these, and a full pipe buffer deadlocks
    # the child (http.server logs every request).
    p = subprocess.Popen(args, cwd=cwd, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    procs.append(p)
    return p

print("e2e: webhook -> snapshot -> VLM -> rules -> MCP\n")
spawn([sys.executable, "-m", "http.server", "8312"], cwd=FIX)
spawn([sys.executable, "frontdesk.py"])
time.sleep(4)

now = int(time.time() * 1000)
body = {"meta": {"version": "1.1", "time": "2026-09-15T00:00:00Z",
                 "request_id": f"e2e_{now}"},
        "data": {"id": f"evt_e2e_{now}", "type": "person_detected",
                 "attributes": {"source": "dev_frontdoor_001",
                                "source_type": "doorbell", "timestamp": now,
                                "confidence": 0.97,
                                "thumbnail_url": "http://127.0.0.1:8312/snap.jpg"}}}
raw = json.dumps(body).encode()
sig = hmac.new(KEY.encode(), raw, hashlib.sha256).hexdigest()
req = urllib.request.Request("http://127.0.0.1:8310/ring/webhook", data=raw,
                             headers={"Content-Type": "application/json",
                                      "X-Ring-Signature": sig}, method="POST")
t0 = time.time()
with urllib.request.urlopen(req, timeout=10) as r:
    ack = json.loads(r.read())
ack_ms = (time.time() - t0) * 1000
check("webhook acked", ack.get("status") == "processed", f"{ack_ms:.0f}ms")
check("ack was fast (async worked)", ack_ms < 2000, f"{ack_ms:.0f}ms < 2000ms")

eid = body["data"]["id"]
verdict = None
for _ in range(60):
    time.sleep(2)
    if not os.path.exists(STORE):
        continue
    for line in open(STORE, encoding="utf-8"):
        rec = json.loads(line)
        if rec.get("record_type") == "classification" and rec.get("event_id") == eid:
            verdict = rec["verdict"]
            break
    if verdict:
        break
check("classification appeared", verdict is not None,
      f"{time.time()-t0:.1f}s total")
if verdict:
    check("snapshot was fetched and read",
          verdict.get("disposition") != "no_snapshot", verdict.get("disposition"))
    obs = verdict.get("observations") or {}
    check("observations returned", bool(obs.get("notes")),
          str(obs.get("notes"))[:46])
    check("downscaled before send", obs.get("_sent_dims") is not None,
          str(obs.get("_sent_dims")))

spawn([sys.executable, "mcp_server.py"])
time.sleep(6)

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def via_mcp():
    async with streamablehttp_client("http://127.0.0.1:8311/mcp") as (rd, wr, _):
        async with ClientSession(rd, wr) as s:
            await s.initialize()
            r = await s.call_tool("door_events", {"hours": 24})
            d = json.loads(r.content[0].text)
            ev = next((e for e in d["events"] if e["event_id"] == eid), None)
            check("MCP sees the event", ev is not None)
            if ev:
                check("MCP merged the verdict",
                      ev.get("disposition") not in (None, "unclassified"),
                      ev.get("disposition"))
                check("no image fields leaked",
                      not any(k in ev for k in ("thumbnail_url", "raw", "bounding_box")))
            r = await s.call_tool("who_came_by", {"hours": 24})
            print("\n  who_came_by ->", json.loads(r.content[0].text)["summary"])

try:
    asyncio.run(via_mcp())
finally:
    for p in procs:
        p.kill()
    shutil.rmtree(FIX, ignore_errors=True)
    if os.path.exists(STORE):
        os.remove(STORE)

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
