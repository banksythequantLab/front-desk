for s in frontdesk-vlm frontdesk-receiver frontdesk-mcp frontdesk-dashboard frontdesk-tunnel; do
  printf "  %-24s %-10s %s\n" "$s" "$(systemctl is-active $s)" "$(systemctl is-enabled $s 2>/dev/null)"
done
echo
echo "=== listening ==="
ss -lnt 2>/dev/null | awk 'NR>1 {print $4}' | grep -E ':(8081|8310|8311|8313)$' | sort
echo
echo "=== local health ==="
curl -s -m 8 http://127.0.0.1:8310/health; echo
curl -s -m 8 -o /dev/null -w "  vlm:8081  HTTP %{http_code}\n" http://127.0.0.1:8081/health
curl -s -m 8 -o /dev/null -w "  dash:8313 HTTP %{http_code}\n" http://127.0.0.1:8313/api/summary
echo
echo "=== any failures ==="
for s in frontdesk-vlm frontdesk-receiver frontdesk-mcp frontdesk-dashboard frontdesk-tunnel; do
  if [ "$(systemctl is-active $s)" != "active" ]; then
    echo "--- $s ---"
    sudo -n journalctl -u $s -n 12 --no-pager 2>/dev/null | tail -12
  fi
done
