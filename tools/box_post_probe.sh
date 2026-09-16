echo "=== POST directly to the receiver, bypassing Cloudflare ==="
echo "--- no code (should be 400) ---"
curl -s -m 30 -o /tmp/a.txt -w "HTTP %{http_code}  %{time_total}s\n" \
  -X POST -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code" http://127.0.0.1:8310/oauth/token
echo "  body: $(cat /tmp/a.txt)"

echo
echo "--- WITH a code (this is what Ring sends) ---"
curl -s -m 120 -o /tmp/b.txt -w "HTTP %{http_code}  %{time_total}s\n" \
  -X POST -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code&code=probe_local_123" http://127.0.0.1:8310/oauth/token
echo "  body: $(cat /tmp/b.txt)"

echo
echo "=== what the receiver logged ==="
tail -6 logs/receiver.log

echo
echo "=== can the box even reach oauth.ring.com? ==="
curl -s -o /dev/null -m 20 -w "  oauth.ring.com/oauth/token  HTTP %{http_code}  %{time_total}s\n" \
  -X POST -d "grant_type=authorization_code&code=x" https://oauth.ring.com/oauth/token
