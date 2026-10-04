cd /opt/banksy/front-desk
echo "=== dispositions now in the store ==="
grep -o '"disposition": "[a-z_]*"' data/events.jsonl | sort | uniq -c | sort -rn

echo
echo "=== what Alexa+ would say ==="
set -a; . ./.env; set +a
./.venv/bin/python - <<'PY'
import anyio, json
from mcp import Client
async def main():
    async with Client("http://127.0.0.1:8311/mcp") as c:
        r = await c.call_tool("who_came_by", {"hours": 24})
        print(" ", json.loads(r.content[0].text)["summary"])
        r = await c.call_tool("needs_review", {"hours": 168})
        d = json.loads(r.content[0].text)
        print("  needs review:", d["count"])
anyio.run(main)
PY

echo
echo "=== lobby dashboard ==="
curl -s -m 8 http://127.0.0.1:8313/api/summary | head -c 320
