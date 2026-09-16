cd /opt/banksy/front-desk
./.venv/bin/python - <<'PY'
import inspect
from mcp.server.mcpserver import MCPServer
print("=== MCPServer.__init__ ===")
print(inspect.signature(MCPServer.__init__))
print()
print("=== MCPServer.run ===")
print(inspect.signature(MCPServer.run))
print()
print("=== has .tool? ===", hasattr(MCPServer, "tool"))
print("=== has .settings? ===", hasattr(MCPServer, "settings"))
doc = (MCPServer.run.__doc__ or "").strip().splitlines()
print()
print("=== run docstring ===")
for line in doc[:14]:
    print("  " + line)
PY
