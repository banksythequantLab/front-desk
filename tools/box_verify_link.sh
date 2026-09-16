sudo -n systemctl restart frontdesk-receiver
sleep 6
echo "=== service ==="
systemctl is-active frontdesk-receiver
echo
echo "=== sign-in page renders with a fresh nonce? ==="
cd /opt/banksy/front-desk
set -a; . ./.env; set +a
NOW=$(( $(date +%s) * 1000 ))
NONCE=$(./.venv/bin/python -c "
import os, sys
sys.path.insert(0, '/opt/banksy/front-desk')
from ring_link import compute_nonce
print(compute_nonce($NOW, 'acct_probe'))
")
curl -s -m 10 "http://127.0.0.1:8310/oauth/authorize?nonce=$NONCE&time=$NOW" \
  | grep -o -E 'Sign in and link|Link your Ring account|Username' | sort -u | sed 's/^/  found: /'
echo
echo "=== stale link still refused ==="
OLD=$(( NOW - 700000 ))
curl -s -m 10 "http://127.0.0.1:8310/oauth/authorize?nonce=x&time=$OLD" \
  | grep -o -E 'Link expired' | head -1 | sed 's/^/  /'
echo
echo "=== operator password file ==="
ls -l data/.operator-password | awk '{print "  mode " $1 "  " $5 " bytes"}'
