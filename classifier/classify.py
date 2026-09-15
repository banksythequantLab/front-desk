#!/usr/bin/env python3
"""
Front Desk doorstep classifier.

DESIGN NOTE - why this is two layers, not one:

A VLM asked "is this a process server?" will happily say yes. It has no way to
know. What it can actually see is whether a person is holding a large envelope,
whether they are facing the door, whether a package is on the step. Those are
perceptual facts.

So the model is only ever asked for OBSERVABLES. A deterministic rules layer
turns observables into a disposition. That split means:
  - wrong dispositions are debuggable (bad observation vs bad rule)
  - the rules are auditable, which matters when the output feeds a legal record
  - swapping models does not silently change legal behaviour

The model never sees the words "process server". If it starts guessing legal
categories on its own, that is a bug.

Env:
  FD_VLM_URL      default http://banksy-box-01.local:8081
  FD_VLM_BACKEND  llamacpp (default) or ollama
  FD_VLM_MODEL    only used by the ollama backend
  FD_VLM_MAX_EDGE default 1280 — see note below

PRE-PROCESSING NOTE:
Image tokens dominate the prompt. Measured on the box, a full-resolution phone
photo cost 4,319 prompt tokens and 17.1s; capping the long edge at 1568 cut it
to 1,611 tokens and 7.2s for identical output.

The cap is 1280 rather than lower because that is where small-feature detail
starts disappearing: at 1280 the model still reported indicator lights on a
device, at 1024 it stopped. Fine detail is the whole ballgame here — a manila
envelope versus a small box is the distinction possible_service rests on — so
we spend the extra second.
"""

import base64
import io
import json
import os
import sys

import requests
from PIL import Image, ImageOps

VLM_URL = os.environ.get("FD_VLM_URL", "http://banksy-box-01.local:8081")
BACKEND = os.environ.get("FD_VLM_BACKEND", "llamacpp").lower()
VLM_MODEL = os.environ.get("FD_VLM_MODEL", "qwen3-vl")
MAX_EDGE = int(os.environ.get("FD_VLM_MAX_EDGE", "1280"))
TIMEOUT = int(os.environ.get("FD_VLM_TIMEOUT", "180"))

OBSERVATION_PROMPT = """You are looking at a still frame from a doorbell camera.

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

REQUIRED_KEYS = [
    "person_count", "person_visible", "facing_door",
    "holding_flat_envelope_or_papers", "holding_parcel_or_box",
    "wearing_delivery_uniform", "parcel_on_ground", "vehicle_visible",
    "lighting", "image_quality", "notes",
]


def prep_image(path, max_edge=None):
    """Downscale, honour EXIF rotation, re-encode as JPEG. Returns bytes.

    Sending a phone-resolution frame wastes most of the prompt budget on image
    tokens for no accuracy gain — see PRE-PROCESSING NOTE above.
    """
    max_edge = max_edge or MAX_EDGE
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    w, h = im.size
    scale = min(1.0, max_edge / max(w, h))
    if scale < 1.0:
        im = im.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=85, optimize=True)
    return buf.getvalue(), im.size


def _strip_fence(text):
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if "\n" in text else text
    return text.strip()


def observe(image_path, model=None):
    """Ask the VLM for observables. Returns (observations, error)."""
    try:
        jpg, dims = prep_image(image_path)
    except Exception as e:
        return None, f"image prep failed: {e}"
    b64 = base64.b64encode(jpg).decode()

    try:
        if BACKEND == "ollama":
            r = requests.post(
                f"{VLM_URL}/api/generate",
                json={"model": model or VLM_MODEL, "prompt": OBSERVATION_PROMPT,
                      "images": [b64], "stream": False, "format": "json",
                      "options": {"temperature": 0}},
                timeout=TIMEOUT)
            raw = (r.json().get("response") or "") if r.status_code == 200 else ""
        else:
            r = requests.post(
                f"{VLM_URL}/v1/chat/completions",
                json={"messages": [{"role": "user", "content": [
                          {"type": "text", "text": OBSERVATION_PROMPT},
                          {"type": "image_url",
                           "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]}],
                      "temperature": 0, "max_tokens": 400},
                timeout=TIMEOUT)
            raw = (r.json()["choices"][0]["message"]["content"]
                   if r.status_code == 200 else "")
    except requests.RequestException as e:
        return None, f"vlm unreachable: {e}"
    except (KeyError, ValueError) as e:
        return None, f"unexpected vlm response shape: {e}"

    if r.status_code != 200:
        return None, f"vlm HTTP {r.status_code}: {r.text[:200]}"

    text = _strip_fence(raw)
    try:
        obs = json.loads(text)
    except json.JSONDecodeError:
        return None, f"vlm returned non-JSON: {text[:200]}"
    if not isinstance(obs, dict):
        return None, "vlm returned non-object"

    missing = [k for k in REQUIRED_KEYS if k not in obs]
    for k in missing:
        obs[k] = None
    if missing:
        obs["_missing_keys"] = missing
    obs["_sent_dims"] = list(dims)
    return obs, None


def _true(v):
    return v is True


def decide(obs, prior_parcel_on_ground=None):
    """Deterministic rules over observables -> disposition.

    prior_parcel_on_ground: whether a parcel was on the step in the PREVIOUS
    frame for this device. Package removal is a state change, not something
    visible in one frame, so it can only be asserted when we have both.

    Dispositions are operational, not legal conclusions. 'possible_service' means
    a human should look, not that service was effected.
    """
    if obs is None:
        return {"disposition": "error", "escalate": True,
                "why": "no observations available"}

    if obs.get("image_quality") == "obstructed" or not _true(obs.get("person_visible")):
        if _true(obs.get("parcel_on_ground")):
            return {"disposition": "parcel_present_no_person", "escalate": False,
                    "why": "parcel on ground, nobody visible"}
        return {"disposition": "no_person", "escalate": False,
                "why": "no person visible in frame"}

    papers = _true(obs.get("holding_flat_envelope_or_papers"))
    parcel = _true(obs.get("holding_parcel_or_box"))
    uniform = _true(obs.get("wearing_delivery_uniform"))
    facing = _true(obs.get("facing_door"))

    # Removal is a transition: parcel was there, now it is not, person present.
    if prior_parcel_on_ground is True and obs.get("parcel_on_ground") is False:
        return {"disposition": "parcel_removed", "escalate": True,
                "why": "parcel present in prior frame, absent now, person on step"}

    if parcel or uniform:
        return {"disposition": "delivery", "escalate": False,
                "why": "carrying a parcel or in delivery uniform"}

    if papers and facing and not uniform:
        return {"disposition": "possible_service", "escalate": True,
                "why": "person at door holding flat envelope or papers, no delivery uniform"}

    if facing:
        return {"disposition": "visitor", "escalate": True,
                "why": "person facing the door, nothing identifying carried"}

    return {"disposition": "passerby", "escalate": False,
            "why": "person visible but not oriented to the door"}


def classify(image_path, model=None, prior_parcel_on_ground=None):
    obs, err = observe(image_path, model)
    result = {
        "image": os.path.basename(image_path),
        "model": model or VLM_MODEL,
        "observations": obs,
        "error": err,
    }
    result.update(decide(obs, prior_parcel_on_ground))
    return result


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        print("\nusage: python classify.py <image> [more images...]")
        return 2
    rc = 0
    for path in sys.argv[1:]:
        out = classify(path)
        if out.get("error"):
            rc = 1
        print(json.dumps(out, indent=2))
    return rc


if __name__ == "__main__":
    sys.exit(main())
