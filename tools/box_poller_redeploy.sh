cd /opt/banksy/front-desk
git pull -q --ff-only
git log --oneline -1
sudo -n systemctl restart frontdesk-poller
echo "waiting for a poll cycle..."
sleep 90
echo
echo "=== poller ==="
systemctl is-active frontdesk-poller
tail -14 logs/poller.log
echo
echo "=== dispositions in the store ==="
grep -o '"disposition": "[a-z_]*"' data/events.jsonl 2>/dev/null | sort | uniq -c | sort -rn | head
