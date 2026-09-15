#!/usr/bin/env python3
"""Shared reader for the Front Desk event store.

frontdesk.py acks the webhook, then a worker appends a separate classification
record keyed by event_id. Both the MCP server and the lobby dashboard need the
same join, so it lives here once rather than drifting in two places.
"""

import json
import os
from datetime import datetime, timedelta, timezone

STORE = os.environ.get("FRONTDESK_STORE", "front_desk_events.jsonl")


def load_events(store=None):
    """Return event records with their classification verdicts merged in."""
    path = store or STORE
    if not os.path.exists(path):
        return []
    events, verdicts = [], {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("record_type") == "classification":
                eid = rec.get("event_id")
                if eid:
                    verdicts[eid] = rec          # last write wins
            else:
                events.append(rec)
    for ev in events:
        v = verdicts.get(ev.get("event_id"))
        if v:
            ev["verdict"] = v.get("verdict")
            ev["classified_at"] = v.get("classified_at")
    return events


def event_time(rec):
    for key in ("timestamp", "received_at"):
        v = rec.get(key)
        if not v:
            continue
        try:
            t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
            return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def within(rec, hours):
    t = event_time(rec)
    return t is not None and t >= datetime.now(timezone.utc) - timedelta(hours=hours)


def disposition(rec):
    v = rec.get("verdict") or {}
    return v.get("disposition") or v.get("verdict") or "unclassified"


def escalated(rec):
    v = rec.get("verdict") or {}
    return bool(v.get("escalate"))
