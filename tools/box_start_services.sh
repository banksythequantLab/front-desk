cd /opt/banksy/front-desk
mkdir -p logs data

echo "=== units present? ==="
ls /etc/systemd/system/frontdesk-*.service | sed 's|.*/|  |'

echo
echo "=== stop any hand-started llama-server on 8081 (by port, not by pattern) ==="
PID=$(ss -lntp 2>/dev/null | awk '$4 ~ /:8081$/ {print $NF}' | grep -oP 'pid=\K[0-9]+' | head -1)
if [ -n "$PID" ]; then
  echo "  killing pid $PID"
  kill "$PID" 2>/dev/null || true
  sleep 4
else
  echo "  nothing on 8081"
fi

echo
echo "=== enable + start ==="
sudo -n systemctl enable -q frontdesk-vlm frontdesk-receiver frontdesk-mcp frontdesk-dashboard frontdesk-tunnel
sudo -n systemctl start frontdesk-vlm
echo "  waiting for the 19GB model to load..."
sleep 50
sudo -n systemctl start frontdesk-receiver frontdesk-mcp frontdesk-dashboard
sleep 6
sudo -n systemctl start frontdesk-tunnel
sleep 15

echo
echo "=== status ==="
for s in frontdesk-vlm frontdesk-receiver frontdesk-mcp frontdesk-dashboard frontdesk-tunnel; do
  printf "  %-24s %-10s %s\n" "$s" "$(systemctl is-active $s)" "$(systemctl is-enabled $s 2>/dev/null)"
done

echo
echo "=== listening ==="
ss -lnt 2>/dev/null | awk 'NR>1 {print $4}' | grep -E ':(8081|8310|8311|8313)$' | sort
