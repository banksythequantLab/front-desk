cd /opt/banksy/front-desk
./.venv/bin/python - <<'PY'
import inspect
from mcp import Client
print("Client.__init__:", inspect.signature(Client.__init__))
print()
meths = [n for n in dir(Client) if not n.startswith('_')]
print("methods:", meths)
print()
for n in ("list_tools", "call_tool", "initialize"):
    if hasattr(Client, n):
        print(f"{n}:", inspect.signature(getattr(Client, n)))
print()
print("is async ctx:", hasattr(Client, "__aenter__"))
PY
