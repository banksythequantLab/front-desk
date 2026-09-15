#!/usr/bin/env python3
"""
Front Desk MCP server — the Alexa+ track surface.

Self-hosted, Streamable HTTP. Reads the append-only JSONL event store that
frontdesk.py writes; it never calls Ring and never actuates anything.

DESIGN NOTE — why every tool is read-only:
A voice assistant that can unlock a door is a different product with a
different risk profile. This exposes what happened at the door, nothing more.
There is deliberately no tool that opens, arms, disarms, or replies to anyone.

DESIGN NOTE — why no images cross this boundary:
Visitors to a law office are identifiable, and who visits a lawyer is itself
privileged-adjacent. Tools return dispositions and counts. Thumbnail URLs stay
in the store and are never returned, so nothing spoken aloud in a lobby — or
logged by a voice platform — can identify a caller.

Env:
  FRONTDESK_STORE   path to the JSONL store (default front_desk_events.jsonl)
  FD_MCP_PORT       default 8311
"""

import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone

from mcp.server.fastmcp import FastMCP

STORE = os.environ.get("FRONTDESK_STORE", "front_desk_events.jsonl")
PORT = int(os.environ.get("FD_MCP_PORT", "8311"))

mcp = FastMCP("front-desk")

# Fields safe to surface to a voice assistant. thumbnail_url, bounding_box and
# raw are intentionally absent.
PUBLIC = ("event_id", "event_type", "timestamp", "device_id", "source_type")


def _load():
    """Read the store and merge classification records onto their events.

    frontdesk.py acks the webhook before classifying, then appends a separate
    classification record keyed by event_id. The store stays append-only; the
    join happens here on read.
    """
    if not os.path.exists(STORE):
        return []
    events, verdicts = [], {}
    with open(STORE, encoding="utf-8") as fh:
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


def _ts(rec):
    for key in ("timestamp", "received_at"):
        v = rec.get(key)
        if not v:
            continue
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except ValueError:
            continue
    return None


def _within(rec, hours):
    t = _ts(rec)
    if t is None:
        return False
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t >= datetime.now(timezone.utc) - timedelta(hours=hours)


def _disposition(rec):
    v = rec.get("verdict") or {}
    return v.get("disposition") or v.get("verdict") or "unclassified"


def _escalated(rec):
    v = rec.get("verdict") or {}
    return bool(v.get("escalate"))


def _slim(rec):
    out = {k: rec.get(k) for k in PUBLIC}
    out["disposition"] = _disposition(rec)
    out["needs_review"] = _escalated(rec)
    return out


# ------------------------------------------------------------------ tools

@mcp.tool()
def who_came_by(hours: int = 24) -> dict:
    """Summarise who came to the door over the last N hours.

    Returns counts by disposition and a short plain-language summary suitable
    for reading aloud. No images or identifying detail.
    """
    recs = [r for r in _load() if _within(r, hours)]
    counts = Counter(_disposition(r) for r in recs)
    review = sum(1 for r in recs if _escalated(r))

    if not recs:
        summary = f"Nothing at the door in the last {hours} hours."
    else:
        parts = [f"{n} {d.replace('_', ' ')}" for d, n in counts.most_common()]
        summary = f"{len(recs)} event{'s' if len(recs) != 1 else ''} in the last {hours} hours: " + ", ".join(parts) + "."
        if review:
            summary += f" {review} need{'s' if review == 1 else ''} a look."
    return {"window_hours": hours, "total": len(recs),
            "by_disposition": dict(counts), "needs_review": review,
            "summary": summary}


@mcp.tool()
def door_events(hours: int = 24, disposition: str | None = None,
                limit: int = 20) -> dict:
    """List door events, newest first.

    disposition filters to one category, e.g. delivery, possible_service,
    visitor, passerby, parcel_removed, no_person.
    """
    limit = max(1, min(limit, 100))
    recs = [r for r in _load() if _within(r, hours)]
    if disposition:
        recs = [r for r in recs if _disposition(r) == disposition]
    recs.sort(key=lambda r: _ts(r) or datetime.min.replace(tzinfo=timezone.utc),
              reverse=True)
    return {"window_hours": hours, "filter": disposition,
            "returned": len(recs[:limit]), "events": [_slim(r) for r in recs[:limit]]}


@mcp.tool()
def needs_review(hours: int = 168) -> dict:
    """Door events flagged for a human to look at.

    A possible_service flag means a person arrived holding papers and was not
    in delivery uniform. It does NOT mean service of process was effected —
    that is a legal conclusion a person makes, never this system.
    """
    recs = [r for r in _load() if _within(r, hours) and _escalated(r)]
    recs.sort(key=lambda r: _ts(r) or datetime.min.replace(tzinfo=timezone.utc),
              reverse=True)
    return {"window_hours": hours, "count": len(recs),
            "events": [_slim(r) for r in recs],
            "note": "Flagged for human review. No legal conclusion has been drawn."}


@mcp.tool()
def event_detail(event_id: str) -> dict:
    """Full detail for one door event, including what the model observed.

    Returns the observation record and the rule that produced the disposition,
    so a decision can be audited. Images are not returned.
    """
    for rec in _load():
        if rec.get("event_id") == event_id:
            v = rec.get("verdict") or {}
            out = _slim(rec)
            out["observations"] = v.get("observations")
            out["why"] = v.get("why") or v.get("reason")
            out["model"] = v.get("model")
            out["confidence"] = rec.get("confidence")
            return out
    return {"error": "not found", "event_id": event_id}


@mcp.tool()
def store_status() -> dict:
    """Health of the event store — is the door agent actually recording?"""
    recs = _load()
    latest = max((_ts(r) for r in recs if _ts(r)), default=None)
    return {"store": os.path.abspath(STORE), "exists": os.path.exists(STORE),
            "events": len(recs),
            "latest_event": latest.isoformat() if latest else None}


if __name__ == "__main__":
    mcp.settings.port = PORT
    mcp.settings.host = "0.0.0.0"
    mcp.settings.stateless_http = True
    mcp.settings.json_response = True
    mcp.run(transport="streamable-http")
