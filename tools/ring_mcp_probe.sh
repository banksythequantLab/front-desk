cd /opt/banksy/front-desk
./.venv/bin/python - <<'PY'
import anyio, json
from mcp import Client

URL = "https://knowledge.appstore-mcp.ring.amazon.dev/mcp"

async def main():
    try:
        async with Client(URL) as c:
            info = c.server_info
            print("connected:", getattr(info, "name", "?"), getattr(info, "version", ""))
            tools = await c.list_tools()
            for t in tools.tools:
                print(f"\n--- {t.name} ---")
                print((t.description or "").strip()[:400])
                schema = getattr(t, "inputSchema", None)
                if schema:
                    print("params:", list((schema.get("properties") or {}).keys()))
    except Exception as e:
        print("FAILED:", type(e).__name__, str(e)[:400])

anyio.run(main)
PY
