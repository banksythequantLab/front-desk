cd /opt/banksy/front-desk
./.venv/bin/python - <<'PY'
from PIL import Image
im = Image.open("data/ring_snapshot.jpg")
print("size:", im.size, "mode:", im.mode)
# Downscale a copy so it can be pulled back to Vesper for viewing
c = im.copy()
c.thumbnail((900, 900), Image.LANCZOS)
c.save("data/ring_snapshot_small.jpg", quality=82)
print("preview written: data/ring_snapshot_small.jpg")
PY

echo
echo "=== run it through the classifier - first REAL Ring frame ==="
set -a; . ./.env; set +a
./.venv/bin/python - <<'PY'
import json, sys, time
sys.path.insert(0, "/opt/banksy/front-desk/classifier")
from classify import classify
t0 = time.time()
out = classify("/opt/banksy/front-desk/data/ring_snapshot.jpg")
print(f"elapsed {time.time()-t0:.1f}s")
obs = out.get("observations") or {}
print("disposition :", out.get("disposition"), "| escalate", out.get("escalate"))
print("error       :", out.get("error"))
print("sent dims   :", obs.get("_sent_dims"))
print("notes       :", obs.get("notes"))
print("lighting    :", obs.get("lighting"), "| quality:", obs.get("image_quality"))
PY
