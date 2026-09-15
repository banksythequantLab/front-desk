# Rebuild the hardware slide on Windows so fonts match the rest of the deck.
# Requires B:\pitch\10767.jpg (the original phone photo).
from PIL import Image, ImageOps, ImageEnhance, ImageDraw, ImageFont
import os, sys

SRC = r"B:\pitch\10767.jpg"
DST = r"B:\pitch\gallery-05-hardware.png"
if not os.path.exists(SRC):
    sys.exit(f"missing {SRC} - save the original photo there first")

BG=(11,16,25); FG=(240,244,250); MUTE=(138,154,176); DIM=(92,108,130); ACC=(64,196,168)

def font(s, b=False):
    for n in (("segoeuib.ttf","arialbd.ttf") if b else ("segoeui.ttf","arial.ttf")):
        for p in (r"C:\Windows\Fonts" + "\\" + n, n):
            try: return ImageFont.truetype(p, s)
            except OSError: continue
    raise SystemExit("no TrueType font")

src = ImageOps.exif_transpose(Image.open(SRC))
W, H = src.size
print("source:", src.size)
crop = src.crop((int(W*0.146), int(H*0.175), W, int(H*0.715)))
crop = ImageEnhance.Brightness(crop).enhance(1.14)
crop = ImageEnhance.Contrast(crop).enhance(1.15)

SLOT_W, SLOT_H = 560, 690
cw, ch = crop.size
sc = min(SLOT_W/cw, SLOT_H/ch)
crop = crop.resize((int(cw*sc), int(ch*sc)), Image.LANCZOS)

img = Image.new("RGB", (1200, 800), BG); d = ImageDraw.Draw(img)
for x in range(0,1200,40): d.line([(x,0),(x,800)], fill=(16,22,33))
for y in range(0,800,40): d.line([(0,y),(1200,y)], fill=(16,22,33))
d.rectangle([0,0,1200,6], fill=ACC)

px = 1130 - crop.size[0]; py = (800 - crop.size[1])//2 + 10
d.rounded_rectangle([px-10, py-10, px+crop.size[0]+10, py+crop.size[1]+10],
                    radius=12, outline=(38,52,74), width=2)
img.paste(crop, (px, py))

d.text((70,118), "This is the box.", font=font(46, True), fill=FG)
d.text((72,188), "Built for and running in a", font=font(26), fill=MUTE)
d.text((72,224), "working New York law practice.", font=font(26), fill=MUTE)
for i, t in enumerate(["32 cores  ·  128 GB unified memory",
                       "5 SATA bays + 5 NVMe  ·  up to 200 TB",
                       "Full-disk encrypted  ·  TPM unlock",
                       "Dual 10GbE  ·  no cloud dependency"]):
    d.text((72, 320+i*44), t, font=font(21), fill=FG if i < 2 else MUTE)
d.text((70,700), "B-AI BOX  ·  BANKSY AI LLC", font=font(19, True), fill=DIM)

img.save(DST)
print("saved:", DST, img.size)
