cd /opt/banksy/front-desk
sudo -n cp deploy/frontdesk-telemetry.service /etc/systemd/system/
sudo -n systemctl daemon-reload
sudo -n systemctl enable -q frontdesk-telemetry
sudo -n systemctl restart frontdesk-telemetry
sleep 8

echo "=== all services ==="
for s in frontdesk-vlm frontdesk-receiver frontdesk-poller frontdesk-mcp \
         frontdesk-dashboard frontdesk-tunnel frontdesk-telemetry; do
  printf "  %-24s %-8s %s\n" "$s" "$(systemctl is-active $s)" "$(systemctl is-enabled $s 2>/dev/null)"
done

echo
echo "=== telemetry log ==="
tail -3 logs/telemetry.log

echo
echo "=== poller: did the 416 retry help? ==="
tail -6 logs/poller.log
