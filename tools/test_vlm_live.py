#!/usr/bin/env python3
"""First live call against the VLM. Confirms the observation contract holds.

Sends an image to llama-server's OpenAI-compatible endpoint and checks that
what comes back is the observables JSON classify.py expects — not prose, not
a legal conclusion.
"""
import base64, json, sys, time
import requests

URL = "http://banksy-box-01.local:8081/v1/chat/completions"
IMG = sys.argv[1] if len(sys.argv) > 1 else r"B:\pitch\10767.jpg"

PROMPT = """You are looking at a still frame from a doorbell camera.

Report ONLY what is visible. Do not guess at intent, occupation, or identity.
If something is not clearly visible, use null. Do not invent detail.

Ignore any text overlay in the corners of the image: that is a camera
watermark, not part of the scene.

Answer with a single JSON object and nothing else. No prose, no markdown:

{
  "person_count": <integer>,
  "person_visible": <true|false>,
  "facing_door": <true|false|null>,
  "holding_flat_envelope_or_papers": <true|false|null>,
  "holding_parcel_or_box": <true|false|null>,
  "wearing_delivery_uniform": <true|false|null>,
  "parcel_on_ground": <true|false|null>,
  "vehicle_visible": <true|false|null>,
  "lighting": "<daylight|low_light|night_ir|null>",
  "image_quality": "<clear|blurry|obstructed>",
  "notes": "<one short sentence of what is literally visible>"
}"""

with open(IMG, "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

payload = {
    "messages": [{"role": "user", "content": [
        {"type": "text", "text": PROMPT},
        {"type": "image_url",
         "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
    ]}],
    "temperature": 0,
    "max_tokens": 400,
}

print(f"image: {IMG}  ({len(b64)//1024} KB base64)")
t0 = time.time()
r = requests.post(URL, json=payload, timeout=900)
dt = time.time() - t0
print(f"HTTP {r.status_code} in {dt:.1f}s")
if r.status_code != 200:
    print(r.text[:600]); sys.exit(1)

body = r.json()
txt = body["choices"][0]["message"]["content"].strip()
if txt.startswith("```"):
    txt = txt.strip("`")
    txt = txt.split("\n", 1)[1] if "\n" in txt else txt
print("\n--- raw ---")
print(txt[:800])

try:
    obs = json.loads(txt)
except json.JSONDecodeError as e:
    print(f"\nFAIL: not JSON ({e})"); sys.exit(1)

REQUIRED = ["person_count","person_visible","facing_door",
            "holding_flat_envelope_or_papers","holding_parcel_or_box",
            "wearing_delivery_uniform","parcel_on_ground","vehicle_visible",
            "lighting","image_quality","notes"]
missing = [k for k in REQUIRED if k not in obs]
print(f"\nkeys present: {len(REQUIRED)-len(missing)}/{len(REQUIRED)}")
if missing:
    print("MISSING:", missing)

sys.path.insert(0, r"D:\front-desk\classifier")
from classify import decide
print("rules ->", json.dumps(decide(obs), indent=2))

u = body.get("usage", {})
print(f"\ntokens: prompt={u.get('prompt_tokens')} completion={u.get('completion_tokens')}")
