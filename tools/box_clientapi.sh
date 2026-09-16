cd /opt/banksy/front-desk
./.venv/bin/python - <<'PY'
import mcp.client.streamable_http as m
print("streamable_http exports:", [n for n in dir(m) if not n.startswith("_")][:20])
import pkgutil, mcp.client as c
print("client submodules:", sorted(x.name for x in pkgutil.iter_modules(c.__path__)))
import mcp
print("top-level:", [n for n in dir(mcp) if 'lient' in n or 'ession' in n])
PY
