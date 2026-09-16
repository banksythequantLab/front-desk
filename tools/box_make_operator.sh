set -e
cd /opt/banksy/front-desk

if grep -q '^FD_ADMIN_PASSWORD_HASH=' .env 2>/dev/null; then
  echo "operator credentials already configured - not overwriting"
  echo "(delete the FD_ADMIN_* lines from .env first if you want to regenerate)"
  exit 0
fi

# Generate on the box. The plaintext goes to a 0600 file Derek reads himself;
# it is never printed here and never leaves this machine.
./.venv/bin/python - <<'PY'
import secrets, sys, os
sys.path.insert(0, "/opt/banksy/front-desk")
os.environ.setdefault("FRONTDESK_HMAC_KEY", "x")
from ring_link import make_password_hash

words = ["harbor","quartz","lantern","marble","cinder","willow","ember","fathom",
         "granite","thistle","vellum","cobalt","russet","pewter","juniper","saffron"]
pw = "-".join(secrets.choice(words) for _ in range(4)) + "-" + str(secrets.randbelow(9000) + 1000)

os.makedirs("/opt/banksy/front-desk/data", exist_ok=True)
with open("/opt/banksy/front-desk/data/.operator-password", "w") as fh:
    fh.write(pw + "\n")
os.chmod("/opt/banksy/front-desk/data/.operator-password", 0o600)

with open("/opt/banksy/front-desk/.env", "a") as fh:
    fh.write("FD_ADMIN_USER=dj@soltis.info\n")
    fh.write(f"FD_ADMIN_PASSWORD_HASH={make_password_hash(pw)}\n")

print("generated a 4-word passphrase, hashed it with pbkdf2-sha256 (310k iters)")
print("plaintext written to data/.operator-password (mode 600)")
PY

chmod 600 .env
echo
echo "=== .env keys now present (values hidden) ==="
cut -d= -f1 .env | sed 's/^/  /'
