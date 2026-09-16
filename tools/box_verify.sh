cd /opt/banksy/front-desk
echo "=== end-to-end on the box: signed webhook -> VLM -> rules -> MCP ==="
./.venv/bin/python test_e2e.py 2>&1 | tail -16
echo
echo "=== MCP protocol suite ==="
set -a; . ./.env; set +a
./.venv/bin/python test_mcp.py 2>&1 | tail -5
