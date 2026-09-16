#!/usr/bin/env python3
"""Poll Ring's Event History API instead of waiting for webhooks.

Ring's own docs sanction this: "Webhook URL is required even if you plan to
poll... acknowledge deliveries with 200 and use the Event History API instead."

WHY THIS IS THE BETTER PATH FOR THIS PRODUCT:
Polling removes four things from the critical path — the public tunnel,
Cloudflare, webhook signature verification, and Ring being able to reach us at
all. We reach out on our own schedule. For an appliance whose entire pitch is
that nothing needs to leave the building, not requiring an inbound endpoint is
the more honest architecture.

It writes the SAME records frontdesk.py writes, so the MCP server and the lobby
dashboard read one store and cannot tell the difference.

Still requires a linked account: the access token must carry consent for the
devices. A Playground token only ever sees the Playground fixture device.

Env:
  FRONTDESK_STORE   the shared JSONL store
  FD_POLL_SECONDS   default 30
  FD_POLL_DEVICES   optional comma-separated device ids; default is all
"""

import json
import logging
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ring_link                                            # noqa: E402

STORE = os.environ.get("FRONTDESK_STORE", "front_desk_events.jsonl")
INTERVAL = int(os.environ.get("FD_POLL_SECONDS", "30"))
ONLY = [d.strip() for d in os.environ.get("FD_POLL_DEVICES", "").split(",") if d.strip()]
SEEN_FILE = os.environ.get(
    "FD_POLL_SEEN",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", ".polled.json"))

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("poller")


def api(path, token):
    req = urllib.request.Request(ring_link.AVA_BASE + path, headers={
        "Authorization": f"Bearer {token}",
        "User-Agent": ring_link.USER_AGENT,
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read() or b"{}"), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.read()[:200].decode(errors='replace')}"
    except Exception as e:                                  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"


def load_seen():
    try:
        with open(SEEN_FILE, encoding="utf-8") as fh:
            return set(json.load(fh))
    except (OSError, json.JSONDecodeError):
        return set()


def save_seen(seen):
    os.makedirs(os.path.dirname(SEEN_FILE), exist_ok=True)
    # Keep the tail: event ids are only needed to avoid reprocessing.
    with open(SEEN_FILE, "w", encoding="utf-8") as fh:
        json.dump(sorted(seen)[-5000:], fh)


def normalize(ev, device_id, device_name):
    """History events use a different shape than webhook events.

    Webhooks give meta/data/attributes with source and thumbnail_url; history
    gives start/end/event_type with a relationships block. Two normalizers is a
    documented annoyance (see FRICTION.md #6) — this is the history one, mapped
    onto the same record shape frontdesk.py writes.
    """
    a = ev.get("attributes") or {}
    start = a.get("start")
    ts = (datetime.fromtimestamp(start / 1000, tz=timezone.utc).isoformat()
          if isinstance(start, (int, float)) else None)
    return {
        "record_type": "event",
        "event_id": ev.get("id"),
        "event_type": a.get("event_type", "unknown"),
        "timestamp": ts,
        "device_id": device_id,
        "device_name": device_name,
        "source_type": "history",
        "duration_ms": (a.get("end") - start) if a.get("end") and start else None,
        "thumbnail_url": a.get("thumbnail_url"),
        "received_at": datetime.now(timezone.utc).isoformat(),
        "via": "poll",
    }


def persist(record):
    os.makedirs(os.path.dirname(os.path.abspath(STORE)) or ".", exist_ok=True)
    with open(STORE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def classify_and_record(event):
    """Same two-record pattern frontdesk.py uses: event, then classification."""
    from frontdesk import classify_event          # reuses snapshot fetch + rules
    verdict = classify_event(event)
    persist({"record_type": "classification",
             "event_id": event["event_id"],
             "device_id": event.get("device_id"),
             "classified_at": datetime.now(timezone.utc).isoformat(),
             "verdict": verdict})
    return verdict


def poll_once(seen):
    token = ring_link.access_token()
    if not token:
        log.warning("no linked account yet - nothing to poll")
        return seen, 0

    devices, err = api("/v1/devices", token)
    if err:
        log.error("device list failed: %s", err)
        return seen, 0

    found = 0
    for d in (devices.get("data") or []):
        did = d.get("id")
        if ONLY and did not in ONLY:
            continue
        name = (d.get("attributes") or {}).get("name", "?")
        body, err = api(f"/v1/history/devices/{did}/events?limit=20", token)
        if err:
            log.error("history failed for %s: %s", name, err)
            continue
        # Oldest first so the store reads chronologically.
        for ev in reversed(body.get("data") or []):
            eid = ev.get("id")
            if not eid or eid in seen:
                continue
            seen.add(eid)
            rec = normalize(ev, did, name)
            persist(rec)
            verdict = classify_and_record(rec)
            found += 1
            log.info("%s  %s -> %s", name, rec["event_type"],
                     verdict.get("disposition"))
    return seen, found


def main():
    log.info("polling every %ss  store=%s", INTERVAL, os.path.abspath(STORE))
    seen = load_seen()
    log.info("%d event ids already processed", len(seen))
    while True:
        try:
            seen, found = poll_once(seen)
            if found:
                save_seen(seen)
        except Exception as e:                              # noqa: BLE001
            log.exception("poll cycle failed: %s", e)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "once":
        s, n = poll_once(load_seen())
        save_seen(s)
        print(f"{n} new event(s)")
    else:
        main()
