cd /opt/banksy/front-desk
./.venv/bin/python - <<'PY'
import anyio, json
from mcp import Client

URL = "https://knowledge.appstore-mcp.ring.amazon.dev/mcp"

QUERIES = [
    "webhook HMAC signature verification header name",
    "how to verify webhook signature signing key encoding",
    "account linking token exchange URL client id client secret direction",
]

def text_of(res):
    out = []
    for c in res.content:
        t = getattr(c, "text", None)
        if t:
            out.append(t)
    return "\n".join(out)

async def main():
    async with Client(URL) as c:
        for q in QUERIES:
            print("=" * 78)
            print("Q:", q)
            print("=" * 78)
            try:
                r = await c.call_tool("ring___search_docs", {"query": q})
                print(text_of(r)[:2600])
            except Exception as e:
                print("FAILED:", type(e).__name__, str(e)[:300])
            print()

anyio.run(main)
PY
