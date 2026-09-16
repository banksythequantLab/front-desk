cd /opt/banksy/front-desk
./.venv/bin/python - <<'PY'
import anyio
from mcp import Client

URL = "https://knowledge.appstore-mcp.ring.amazon.dev/mcp"

def text_of(res):
    return "\n".join(getattr(c, "text", "") for c in res.content if getattr(c, "text", None))

async def main():
    async with Client(URL) as c:
        r = await c.call_tool("ring___get_doc",
                              {"uri": "amazon_vision_api/app_integrations.md"})
        print(text_of(r)[:7000])

anyio.run(main)
PY
