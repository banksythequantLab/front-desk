cd /opt/banksy/front-desk
echo "=== services ==="
for s in frontdesk-receiver frontdesk-tunnel; do
  printf "  %-22s %-8s since %s\n" "$s" "$(systemctl is-active $s)" \
    "$(systemctl show -p ActiveEnterTimestamp --value $s)"
done

echo
echo "=== public reachability right now ==="
curl -s -m 15 -o /dev/null -w "  health           HTTP %{http_code}\n" https://frontdesk.quantcity.org/health
curl -s -m 15 -o /dev/null -w "  oauth/token POST HTTP %{http_code} (400 = reachable, no code)\n" \
  -X POST -d "" https://frontdesk.quantcity.org/oauth/token
curl -s -m 15 -o /dev/null -w "  oauth/authorize  HTTP %{http_code}\n" \
  "https://frontdesk.quantcity.org/oauth/authorize?nonce=z&time=$(( $(date +%s) * 1000 ))"

echo
echo "=== did that external probe show up in the log? ==="
tail -4 logs/receiver.log

echo
echo "=== tunnel: any inbound requests logged? ==="
grep -c -E 'GET|POST' logs/tunnel.log 2>/dev/null || echo 0
tail -5 logs/tunnel.log 2>/dev/null

echo
echo "=== log line count ==="
wc -l logs/receiver.log
