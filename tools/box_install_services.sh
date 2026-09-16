set -e
cd /opt/banksy/front-desk
git pull -q --ff-only
mkdir -p logs data

echo "=== installing units ==="
sudo -n cp deploy/frontdesk-vlm.service \
          deploy/frontdesk-receiver.service \
          deploy/frontdesk-mcp.service \
          deploy/frontdesk-dashboard.service \
          deploy/frontdesk-tunnel.service /etc/systemd/system/
sudo -n systemctl daemon-reload

echo "=== stopping the hand-started vision server so systemd owns it ==="
pkill -f 'port 8081' 2>/dev/null || true
sleep 3

echo "=== enabling ==="
sudo -n systemctl enable -q frontdesk-vlm frontdesk-receiver frontdesk-mcp \
                            frontdesk-dashboard frontdesk-tunnel
sudo -n systemctl start frontdesk-vlm
echo "waiting for the model to load..."
sleep 45
sudo -n systemctl start frontdesk-receiver frontdesk-mcp frontdesk-dashboard
sleep 5
sudo -n systemctl start frontdesk-tunnel
sleep 15

echo
echo "=== status ==="
for s in frontdesk-vlm frontdesk-receiver frontdesk-mcp frontdesk-dashboard frontdesk-tunnel; do
  printf "  %-24s %s\n" "$s" "$(systemctl is-active $s)"
done

echo
echo "=== local ports ==="
ss -lnt 2>/dev/null | awk 'NR>1 {print $4}' | grep -E ':(8081|8310|8311|8313)$' | sort
