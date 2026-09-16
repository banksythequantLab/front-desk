cd /opt/banksy/front-desk
git pull -q --ff-only
git log --oneline -1
echo
echo "=== import check under mcp 2.x ==="
FRONTDESK_STORE=/tmp/x.jsonl ./.venv/bin/python - <<'PY'
import mcp_server as m
print("imports OK   mcp2 =", m._MCP2)
mgr = getattr(m.mcp, "_tool_manager", None)
if mgr:
    print("tools:", sorted(t.name for t in mgr.list_tools()))
PY
