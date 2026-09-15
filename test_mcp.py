#!/usr/bin/env python3
"""Exercise the Front Desk MCP server over Streamable HTTP.

Speaks the real protocol (initialize -> tools/list -> tools/call) rather than
poking the HTTP surface, so a pass here means an MCP client can actually use it.
"""
import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8311/mcp"
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:<38} {detail}")


def text_of(res):
    out = []
    for c in res.content:
        if getattr(c, "type", None) == "text":
            out.append(c.text)
    return "\n".join(out)


async def main():
    print(f"Front Desk MCP test against {URL}\n")
    async with streamablehttp_client(URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            check("initialize", bool(init.serverInfo.name),
                  f"server={init.serverInfo.name!r}")

            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            check("tools/list", len(names) == 5, names)

            expected = ["door_events", "event_detail", "needs_review",
                        "store_status", "who_came_by"]
            check("expected tool set", names == expected)

            for t in tools.tools:
                if not (t.description or "").strip():
                    check(f"description: {t.name}", False)
            check("all tools documented",
                  all((t.description or "").strip() for t in tools.tools))

            r = await session.call_tool("store_status", {})
            d = json.loads(text_of(r))
            check("store_status", "events" in d, f"events={d.get('events')}")

            r = await session.call_tool("who_came_by", {"hours": 24})
            d = json.loads(text_of(r))
            check("who_came_by", "summary" in d, d.get("summary", "")[:60])

            r = await session.call_tool("door_events", {"hours": 24, "limit": 5})
            d = json.loads(text_of(r))
            check("door_events", "events" in d, f"returned={d.get('returned')}")

            leaked = [e for e in d.get("events", [])
                      if "thumbnail_url" in e or "raw" in e or "bounding_box" in e]
            check("no images leak to voice surface", not leaked)

            r = await session.call_tool("needs_review", {"hours": 168})
            d = json.loads(text_of(r))
            check("needs_review", "count" in d, f"count={d.get('count')}")

            r = await session.call_tool("event_detail", {"event_id": "does_not_exist"})
            d = json.loads(text_of(r))
            check("event_detail handles miss", d.get("error") == "not found")

    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
