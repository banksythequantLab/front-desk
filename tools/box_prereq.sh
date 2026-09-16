echo "=== python ==="
python3 -V
python3 -c "import requests, PIL; print('requests', requests.__version__, '| pillow', PIL.__version__)" 2>&1 | tail -1
python3 -c "import mcp; print('mcp ok')" 2>&1 | tail -1
echo
echo "=== pip available? ==="
python3 -m pip --version 2>&1 | tail -1
ls /usr/lib/python3*/EXTERNALLY-MANAGED 2>/dev/null && echo "(PEP668 managed - needs venv or --break-system-packages)"
echo
echo "=== cloudflared ==="
which cloudflared || echo "not installed"
echo
echo "=== git + target dir ==="
which git
ls -d /opt/banksy/front-desk 2>/dev/null || echo "front-desk not present yet"
df -h /opt/banksy | tail -1
echo
echo "=== ports in use ==="
ss -lnt 2>/dev/null | awk 'NR>1 {print $4}' | sort -u | tr '\n' ' '
