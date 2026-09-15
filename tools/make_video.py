# Assemble the B-AI Box demo video: one slide per narration segment.
# 1080p, dark-padded to 16:9, H.264 + AAC.
import os, subprocess, sys

PITCH = r"B:\pitch"
VO    = os.path.join(PITCH, "vo")
WORK  = r"D:\front-desk\tools\_video"
OUT   = os.path.join(PITCH, "bai-box-demo.mp4")
os.makedirs(WORK, exist_ok=True)

SEGMENTS = [
    ("01_cover",       "bai-box-cover.png"),
    ("02_boundary",    "gallery-01-boundary.png"),
    ("03_hardware",    "gallery-05-hardware.png"),
    ("04_replication", "gallery-02-replication.png"),
    ("05_pricing",     "gallery-04-pricing.png"),
    ("06_close",       "gallery-03-benchmark.png"),
]

VF = ("scale=1920:1080:force_original_aspect_ratio=decrease,"
      "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x0B1019,setsar=1")

def run(args):
    p = subprocess.run(args, capture_output=True, text=True)
    if p.returncode != 0:
        print("FFMPEG FAILED:", " ".join(args[:6]), "...")
        print(p.stderr[-1200:])
        sys.exit(1)

missing = [img for _, img in SEGMENTS if not os.path.exists(os.path.join(PITCH, img))]
missing += [s + ".wav" for s, _ in SEGMENTS
            if not os.path.exists(os.path.join(VO, s + ".wav"))]
if missing:
    sys.exit("missing inputs: " + ", ".join(missing))

parts = []
for seg, img in SEGMENTS:
    wav = os.path.join(VO, seg + ".wav")
    mp4 = os.path.join(WORK, seg + ".mp4")
    run(["ffmpeg", "-y", "-loop", "1", "-i", os.path.join(PITCH, img),
         "-i", wav, "-vf", VF, "-r", "30",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-tune", "stillimage", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "1",
         "-shortest", mp4])
    parts.append(mp4)
    print("segment ok:", seg)

lst = os.path.join(WORK, "concat.txt")
with open(lst, "w", encoding="utf-8") as fh:
    for p in parts:
        fh.write("file '" + p.replace("\\", "/") + "'\n")

run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", OUT])
print("WROTE:", OUT)
