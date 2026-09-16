cd /opt/banksy/front-desk
echo "=== fastmcp import (what mcp_server.py uses) ==="
./.venv/bin/python -c "from mcp.server.fastmcp import FastMCP; print('OK')" 2>&1 | tail -3
echo
echo "=== available server submodules ==="
./.venv/bin/python - <<'PY'
import pkgutil, mcp.server as s
print(sorted(x.name for x in pkgutil.iter_modules(s.__path__)))
PY
echo
echo "=== does mcp_server.py import cleanly? ==="
FRONTDESK_STORE=/tmp/x.jsonl ./.venv/bin/python -c "import mcp_server; print('mcp_server imports OK')" 2>&1 | tail -4
