import os, sys, requests

OUT = r"B:\pitch\vo"
os.makedirs(OUT, exist_ok=True)
REF = r"B:\freeclone-backend\derek-voice.wav"
URL = "http://johnson:8300/api/clone"

SEGMENTS = [
    ("01_cover",
     "I'm Derek Soltis, a litigator admitted in the Southern and Eastern Districts "
     "of New York. I built B-AI Box because I couldn't ethically use the AI tools "
     "that would have saved me ten hours a week."),

    ("02_boundary",
     "A-B-A Formal Opinion five twelve says that before client information goes into "
     "a self-learning AI tool, you need that client's informed consent, and boilerplate "
     "in an engagement letter doesn't count. In February, a federal court in my own "
     "district held that a defendant lost privilege and work product by using a consumer "
     "AI tool. Ethics rules risk discipline. Waiver risks the case."),

    ("03_hardware",
     "So everything runs here instead. Private AI, an encrypted five-bay file server, "
     "and an AI receptionist that answers the phone. Thirty-two cores, a hundred "
     "twenty-eight gigabytes of unified memory. The voice you're hearing right now was "
     "synthesized on my own hardware, not a cloud service."),

    ("04_replication",
     "When a firm asks what happens if the box dies, the answer isn't cloud backup. "
     "It's a second box at a partner's office, replicating. The backup target is hardware "
     "the firm already owns. No cloud provider anywhere in the recovery path."),

    ("05_pricing",
     "Seventy-four ninety-five for the box, ninety-nine a month for the line and support. "
     "Bring your own hardware for seven-fifty. Or start on the cloud tier and step off it."),

    ("06_close",
     "Seven hundred thousand solo and small-firm attorneys have this problem. So does "
     "nearly every independent medical, dental, and optometry practice. I'm raising a "
     "pre-seed round. This is B-AI Box."),
]

def clone(text, name):
    with open(REF, "rb") as f:
        r = requests.post(
            URL,
            files={"prompt_audio": ("ref.wav", f, "audio/wav")},
            data={"text": text, "lang": "en"},
            timeout=1200,
        )
    if r.status_code != 200 or len(r.content) < 2000:
        print(f"FAIL {name}: HTTP {r.status_code} len={len(r.content)}")
        print(r.text[:400])
        return False
    p = os.path.join(OUT, name + ".wav")
    with open(p, "wb") as fh:
        fh.write(r.content)
    print(f"ok {name}: {len(r.content):,} bytes")
    return True

if __name__ == "__main__":
    bad = 0
    for name, text in SEGMENTS:
        if not clone(text, name):
            bad += 1
    print(f"done. failures={bad}")
    sys.exit(1 if bad else 0)
