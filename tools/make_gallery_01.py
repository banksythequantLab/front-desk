from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 800
BG   = (11, 16, 25)
FG   = (240, 244, 250)
MUTE = (138, 154, 176)
DIM  = (92, 108, 130)
ACC  = (64, 196, 168)
WARN = (232, 168, 80)
LINE = (38, 52, 74)

def font(s, b=False):
    for n in (("segoeuib.ttf","arialbd.ttf") if b else ("segoeui.ttf","arial.ttf")):
        for p in (r"C:\Windows\Fonts" + "\\" + n, n):
            try: return ImageFont.truetype(p, s)
            except OSError: continue
    raise SystemExit("no TrueType font")

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)
for x in range(0, W, 40): d.line([(x,0),(x,H)], fill=(16,22,33))
for y in range(0, H, 40): d.line([(0,y),(W,y)], fill=(16,22,33))
d.rectangle([0,0,W,6], fill=ACC)

d.text((70, 44), "What leaves the building", font=font(46, True), fill=FG)
d.text((72, 108), "Everything inside the boundary runs on hardware the firm owns.",
       font=font(23), fill=MUTE)

# ---- the boundary ----
BX, BY, BW, BH = 70, 170, 700, 470
d.rounded_rectangle([BX, BY, BX+BW, BY+BH], radius=16, outline=ACC, width=3)
d.text((BX+24, BY+18), "YOUR OFFICE", font=font(20, True), fill=ACC)

items = [
    ("Documents & matter files",  "never leave"),
    ("AI inference (all models)",  "never leaves"),
    ("Search index",               "never leaves"),
    ("Call transcripts",           "never leave"),
    ("Voice synthesis & cloning",  "never leaves"),
    ("Encrypted archive + replica","never leaves"),
]
for i, (label, note) in enumerate(items):
    y = BY + 70 + i*62
    d.rounded_rectangle([BX+24, y, BX+BW-24, y+48], radius=8, outline=LINE, width=2)
    d.ellipse([BX+44, y+18, BX+56, y+30], fill=ACC)
    d.text((BX+74, y+13), label, font=font(24, True), fill=FG)
    d.text((BX+BW-150, y+16), note, font=font(19), fill=DIM)

# ---- the one exception ----
EX, EY, EW, EH = 820, 300, 310, 210
d.rounded_rectangle([EX, EY, EX+EW, EY+EH], radius=14, outline=WARN, width=3)
d.text((EX+22, EY+20), "THE ONE EXCEPTION", font=font(18, True), fill=WARN)
d.text((EX+22, EY+56), "Telephony", font=font(30, True), fill=FG)
d.text((EX+22, EY+98), "Inbound calls arrive over", font=font(19), fill=MUTE)
d.text((EX+22, EY+124), "a carrier line, like every", font=font(19), fill=MUTE)
d.text((EX+22, EY+150), "office phone. The audio", font=font(19), fill=MUTE)
d.text((EX+22, EY+176), "is answered on the box.", font=font(19), fill=MUTE)

# connector
d.line([(BX+BW, EY+105), (EX, EY+105)], fill=WARN, width=3)
for t in range(0, 3):
    px = BX+BW+14 + t*14
    d.polygon([(px, EY+99), (px+9, EY+105), (px, EY+111)], fill=WARN)

d.text((820, 560), "No cloud AI service.", font=font(24, True), fill=ACC)
d.text((820, 596), "No vendor account.", font=font(24, True), fill=ACC)
d.text((820, 632), "No third-party disclosure.", font=font(24, True), fill=ACC)

d.text((70, 726), "B-AI BOX  ·  BANKSY AI LLC", font=font(19, True), fill=DIM)

img.save(r"B:\pitch\gallery-01-boundary.png", quality=95)
print("saved:", img.size)
