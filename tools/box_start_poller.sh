cd /opt/banksy/front-desk
git pull -q --ff-only 2>/dev/null
sudo -n cp deploy/frontdesk-poller.service /etc/systemd/system/
sudo -n systemctl daemon-reload
sudo -n systemctl enable -q frontdesk-poller
sudo -n systemctl restart frontdesk-poller
sleep 40

echo "=== poller ==="
systemctl is-active frontdesk-poller
echo
echo "=== log ==="
tail -20 logs/poller.log 2>/dev/null
echo
echo "=== store ==="
wc -l data/events.jsonl 2>/dev/null || echo "  no events yet"
