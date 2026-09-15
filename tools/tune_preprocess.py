#!/usr/bin/env python3
"""Find the right pre-processing size for doorstep frames.

Image tokens dominate the prompt, so the max edge we send drives both latency
and cost. Sweep sizes, measure tokens and wall time, and check the observation
contract still holds at each one.
"""
import base64, io, json, sys, time
import requests
from PIL import Image, ImageOps

URL = "http://banksy-box-01.local:8081/v1/chat/completions"
SRC = sys.argv[1] if len(sys.argv) > 1 else r"B:\pitch\10767.jpg"
SIZES = [1568, 1280, 1024, 768, 512]

sys.path.insert(0, r"D:\front-desk\classifier")
from classify import OBSERVATION_PROMPT, REQUIRED_KEYS, decide


def prep(path, max_edge, quality=85):
    """Downscale to max_edge, honour EXIF rotation, re-encode as JPEG."""
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    w, h = im.size
    scale = min(1.0, max_edge / max(w, h))
    if scale < 1.0:
        im = im.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue(), im.size


def ask(jpg_bytes):
    b64 = base64.b64encode(jpg_bytes).decode()
    payload = {"messages": [{"role": "user", "content": [
        {"type": "text", "text": OBSERVATION_PROMPT},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
    ]}], "temperature": 0, "max_tokens": 400}
    t0 = time.time()
    r = requests.post(URL, json=payload, timeout=900)
    dt = time.time() - t0
    r.raise_for_status()
    body = r.json()
    txt = body["choices"][0]["message"]["content"].strip()
    if txt.startswith("```"):
        txt = txt.strip("`")
        txt = txt.split("\n", 1)[1] if "\n" in txt else txt
    return txt, body.get("usage", {}), dt


print(f"source: {SRC}\n")
print(f"{'max_edge':>9} {'dims':>12} {'KB':>6} {'ptok':>6} {'sec':>6} {'keys':>6}  disposition")
print("-" * 68)

rows = []
for edge in SIZES:
    jpg, dims = prep(SRC, edge)
    try:
        txt, usage, dt = ask(jpg)
    except Exception as e:
        print(f"{edge:>9} {'x'.join(map(str,dims)):>12} {len(jpg)//1024:>6}  ERROR {e}")
        continue
    try:
        obs = json.loads(txt)
        ok = sum(1 for k in REQUIRED_KEYS if k in obs)
        disp = decide(obs)["disposition"]
        note = obs.get("notes", "")[:44]
    except json.JSONDecodeError:
        ok, disp, note = 0, "PARSE_FAIL", txt[:44]
    rows.append((edge, usage.get("prompt_tokens"), dt, ok, disp))
    print(f"{edge:>9} {'x'.join(map(str,dims)):>12} {len(jpg)//1024:>6} "
          f"{usage.get('prompt_tokens'):>6} {dt:>6.1f} {ok:>4}/11  {disp}")
    print(f"{'':>9} note: {note}")

if rows:
    base = rows[0]
    print("\nrelative to", base[0], "px:")
    for edge, ptok, dt, ok, disp in rows:
        print(f"  {edge:>5}px  tokens {ptok/base[1]*100:5.1f}%   time {dt/base[2]*100:5.1f}%")
