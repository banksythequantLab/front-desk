from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 800  # 3:2
BG    = (11, 16, 25)
FG    = (240, 244, 250)
MUTE  = (138, 154, 176)
DIM   = (90, 106, 128)
ACC   = (64, 196, 168)
LINE  = (38, 52, 74)

def font(size, bold=False):
    names = ("segoeuib.ttf", "arialbd.ttf") if bold else ("segoeui.ttf", "arial.ttf")
    for n in names:
        for p in (r"C:\Windows\Fonts" + "\\" + n, n):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    raise SystemExit("no TrueType font found - refusing bitmap fallback")

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

for x in range(0, W, 40):
    d.line([(x, 0), (x, H)], fill=(16, 22, 33), width=1)
for y in range(0, H, 40):
    d.line([(0, y), (W, y)], fill=(16, 22, 33), width=1)
d.rectangle([0, 0, W, 6], fill=ACC)


# ---------------- icons (48x48 box at ox,oy) ----------------

def ic_ai(ox, oy):
    d.rounded_rectangle([ox+8, oy+8, ox+40, oy+40], radius=5, outline=ACC, width=3)
    d.rectangle([ox+18, oy+18, ox+30, oy+30], fill=ACC)
    for i in range(3):
        p = ox + 14 + i*10
        d.line([(p, oy), (p, oy+8)], fill=ACC, width=3)
        d.line([(p, oy+40), (p, oy+48)], fill=ACC, width=3)
        q = oy + 14 + i*10
        d.line([(ox, q), (ox+8, q)], fill=ACC, width=3)
        d.line([(ox+40, q), (ox+48, q)], fill=ACC, width=3)

def ic_phone(ox, oy):
    d.rounded_rectangle([ox+13, oy+4, ox+35, oy+44], radius=6, outline=ACC, width=3)
    d.line([(ox+20, oy+12), (ox+28, oy+12)], fill=ACC, width=3)
    d.ellipse([ox+21, oy+33, ox+27, oy+39], fill=ACC)

def ic_voice(ox, oy):
    hs = [10, 20, 34, 44, 34, 20, 10]
    for i, h in enumerate(hs):
        x = ox + 4 + i*7
        d.line([(x, oy+24-h//2), (x, oy+24+h//2)], fill=ACC, width=4)

def ic_nas(ox, oy):
    for i in range(3):
        y = oy + 6 + i*14
        d.rounded_rectangle([ox+4, y, ox+44, y+10], radius=2, outline=ACC, width=2)
        d.ellipse([ox+36, y+3, ox+41, y+8], fill=ACC)

def ic_doc(ox, oy):
    d.rounded_rectangle([ox+10, oy+4, ox+38, oy+44], radius=4, outline=ACC, width=3)
    for i in range(4):
        y = oy + 14 + i*7
        d.line([(ox+17, y), (ox+31, y)], fill=ACC, width=2)

def ic_replica(ox, oy):
    d.rounded_rectangle([ox+2, oy+10, ox+20, oy+38], radius=4, outline=ACC, width=3)
    d.rounded_rectangle([ox+28, oy+10, ox+46, oy+38], radius=4, outline=ACC, width=3)
    d.line([(ox+21, oy+20), (ox+27, oy+20)], fill=ACC, width=3)
    d.line([(ox+21, oy+28), (ox+27, oy+28)], fill=ACC, width=3)


# ---------------- header ----------------
d.text((70, 52), "B-AI BOX", font=font(72, True), fill=FG)
d.line([(74, 140), (74+146, 140)], fill=ACC, width=4)
d.text((70, 156), "Everything runs in your office. Nothing goes to the cloud.",
       font=font(26), fill=MUTE)

# ---------------- capability grid ----------------
TILES = [
    (ic_ai,      "Private AI",      "Runs on your hardware"),
    (ic_phone,   "AI Receptionist", "Answers, screens, books"),
    (ic_voice,   "Voice Cloning",   "Your voice, made in-house"),
    (ic_nas,     "Encrypted NAS",   "5 bays, up to 200 TB"),
    (ic_doc,     "Transcription",   "Calls and files, searchable"),
    (ic_replica, "Offsite Replica", "Backup you own"),
]

COLW, ROWH, GAP, MX = 336, 218, 26, 70
for i, (icon, title, sub) in enumerate(TILES):
    cx = MX + (i % 3) * (COLW + GAP)
    cy = 228 + (i // 3) * (ROWH + GAP)
    d.rounded_rectangle([cx, cy, cx+COLW, cy+ROWH], radius=12, outline=LINE, width=2)
    icon(cx + 28, cy + 30)
    d.text((cx + 28, cy + 104), title, font=font(31, True), fill=FG)
    d.text((cx + 28, cy + 148), sub, font=font(21), fill=DIM)

# ---------------- footer ----------------
d.text((70, 726), "BANKSY AI LLC", font=font(20, True), fill=MUTE)
d.text((262, 727), "Legal  ·  Medical  ·  Dental  ·  Optometry",
       font=font(19), fill=DIM)

img.save(r"B:\pitch\bai-box-cover.png", quality=95)
print("saved:", img.size)
