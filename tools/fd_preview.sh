cd /opt/banksy/front-desk
./.venv/bin/python - <<'PY'
from PIL import Image
im = Image.open("data/frontdoor.jpg")
print("size:", im.size)
c = im.copy()
c.thumbnail((900, 900), Image.LANCZOS)
c.save("data/frontdoor_small.jpg", quality=84)
print("preview written")
PY
