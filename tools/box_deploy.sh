set -e
cd /opt/banksy

if [ -d front-desk/.git ]; then
  echo "=== repo exists, pulling ==="
  cd front-desk && git pull --ff-only
else
  echo "=== cloning ==="
  git clone -q https://github.com/banksythequantLab/front-desk.git
  cd front-desk
fi
git log --oneline -1

echo
echo "=== venv (isolated - does not touch system python or the voice stack) ==="
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
./.venv/bin/pip -q install --upgrade pip
./.venv/bin/pip -q install requests pillow mcp
echo "installed:"
./.venv/bin/python -c "import requests, PIL, mcp; import importlib.metadata as m; print('  requests', m.version('requests')); print('  pillow  ', m.version('pillow')); print('  mcp     ', m.version('mcp'))"

echo
echo "=== compile check ==="
./.venv/bin/python -m py_compile frontdesk.py mcp_server.py dashboard.py store.py oauth_provider.py classifier/classify.py && echo "  all modules compile"

echo
echo "=== rules suite (no model needed) ==="
cd classifier && ../.venv/bin/python test_rules.py | tail -2
