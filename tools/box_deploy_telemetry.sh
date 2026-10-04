cd /opt/banksy/front-desk
git pull -q --ff-only
git log --oneline -1
echo
echo "=== telemetry dry run ==="
set -a; . ./.env; set +a
./.venv/bin/python telemetry.py once
echo
echo "=== restart poller with the 416 retry ==="
sudo -n systemctl restart frontdesk-poller
sleep 5
systemctl is-active frontdesk-poller
