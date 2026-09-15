from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 800
BG   = (11, 16, 25)
FG   = (240, 244, 250)
MUTE = (138, 154, 176)
DIM  = (92, 108, 130)
ACC  = (64, 196, 168)
WARN = (232, 168, 80)
COOL = (96, 150, 220)
LINE = (38, 52, 74)

def font(s, b=False):
    for n in (("segoeuib.ttf","arialbd.ttf") if b else ("segoeui.ttf","arial.ttf")):
        for p in (r"C:\Windows\Fonts" + "\\" + n, n):
            try: return ImageFont.truetype(p, s)
            except OSError: continue
    raise SystemExit("no TrueType font")

def canvas(title, sub):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for x in range(0, W, 40): d.line([(x,0),(x,H)], fill=(16,22,33))
    for y in range(0, H, 40): d.line([(0,y),(W,y)], fill=(16,22,33))
    d.rectangle([0,0,W,6], fill=ACC)
    d.text((70, 44), title, font=font(46, True), fill=FG)
    d.text((72, 108), sub, font=font(23), fill=MUTE)
    return img, d

def footer(d):
    d.text((70, 736), "B-AI BOX  ·  BANKSY AI LLC", font=font(19, True), fill=DIM)


# ============ 02 — two-box replication ============
img, d = canvas("Disaster recovery without the cloud",
                "Every on-prem product gets asked what happens when the box dies.")

def unit(x, y, w, h, tag, tagcol, name, cap, cfg, role):
    d.rounded_rectangle([x, y, x+w, y+h], radius=14, outline=tagcol, width=3)
    d.text((x+24, y+22), tag, font=font(18, True), fill=tagcol)
    d.text((x+24, y+56), name, font=font(32, True), fill=FG)
    d.text((x+24, y+108), cap, font=font(40, True), fill=tagcol)
    d.text((x+24, y+164), cfg, font=font(20), fill=MUTE)
    d.text((x+24, y+196), role, font=font(20), fill=DIM)

unit(70, 205, 430, 260, "PRIMARY", ACC, "The office",
     "150 TB", "5 x 30 TB striped", "Maximum capacity and speed")
unit(700, 205, 430, 260, "REPLICA", COOL, "Partner's location",
     "120 TB", "5 x 30 TB single-parity", "Survives a drive failure")

d.line([(505, 335), (695, 335)], fill=MUTE, width=3)
for t in range(3):
    px = 560 + t*40
    d.polygon([(px, 329), (px+10, 335), (px, 341)], fill=MUTE)
d.text((524, 288), "encrypted replication", font=font(19), fill=MUTE)

d.rounded_rectangle([70, 510, 1130, 600], radius=12, outline=LINE, width=2)
d.text((100, 528), "The backup target is hardware the firm already owns.",
       font=font(28, True), fill=ACC)
d.text((100, 566), "No cloud provider anywhere in the disaster-recovery path.",
       font=font(21), fill=MUTE)

d.text((70, 634), "The second box is sold to a partner as their own AI assistant —",
       font=font(22), fill=FG)
d.text((70, 666), "a full product sale, not a discount. Recurring doubles to $2,376/year.",
       font=font(22), fill=FG)
footer(d)
img.save(r"B:\pitch\gallery-02-replication.png", quality=95)
print("02 saved")


# ============ 03 — benchmark ============
img, d = canvas("The GPU was never being used",
                "Same binary, same model. One group membership was the difference.")

def bars(ox, oy, title, unit_lbl, gpu, cpu, gain):
    d.text((ox, oy), title, font=font(26, True), fill=FG)
    d.text((ox, oy+36), unit_lbl, font=font(18), fill=DIM)
    maxv = float(max(gpu, cpu))
    BARW, MAXH, BASE = 92, 250, oy + 340
    for i, (lbl, val, col) in enumerate((("GPU", gpu, ACC), ("CPU", cpu, (70, 88, 112)))):
        bx = ox + 40 + i*150
        bh = int(MAXH * (val / maxv))
        d.rounded_rectangle([bx, BASE-bh, bx+BARW, BASE], radius=6, fill=col)
        d.text((bx, BASE-bh-40), f"{val:,}", font=font(30, True), fill=FG)
        d.text((bx+22, BASE+14), lbl, font=font(21, True), fill=MUTE)
    d.line([(ox, BASE), (ox+380, BASE)], fill=LINE, width=2)
    d.text((ox+300, oy+236), gain, font=font(42, True), fill=ACC)
    d.text((ox+302, oy+286), "faster", font=font(20), fill=MUTE)

bars(90,  190, "Prompt processing", "tokens / second", 2130, 1080, "2.0x")
bars(640, 190, "Token generation",  "tokens / second",   78,   34, "2.3x")

d.rounded_rectangle([70, 630, 1130, 712], radius=12, outline=WARN, width=2)
d.text((100, 648), "The service account was not in the render group, so /dev/kfd could not",
       font=font(21), fill=MUTE)
d.text((100, 676), "be opened. No error was raised. Everything silently ran on CPU for weeks.",
       font=font(21), fill=MUTE)
footer(d)
img.save(r"B:\pitch\gallery-03-benchmark.png", quality=95)
print("03 saved")


# ============ 04 — pricing ladder ============
img, d = canvas("Four ways in",
                "Priced so a practice can enter at any level of commitment.")

TIERS = [
    ("Cloud Personal AI",  "—",        "$249/mo", "No hardware. Premium on purpose.",       300, COOL),
    ("Bring your own HW",  "$750",     "$99/mo",  "Reuse a server you already own.",        380, COOL),
    ("B-AI Box",           "$7,495",   "$99/mo",  "The full guarantee. 4 TB base.",         470, ACC),
    ("Flagship pair",      "$29,980",  "$198/mo", "270 TB across two firm-owned boxes.",    560, ACC),
]

x0, y0, rowh, gap = 70, 190, 96, 14
for i, (name, up, mo, note, barw, col) in enumerate(TIERS):
    y = y0 + i*(rowh+gap)
    d.rounded_rectangle([x0, y, x0+1060, y+rowh], radius=12, outline=LINE, width=2)
    d.rectangle([x0+2, y+2, x0+8, y+rowh-2], fill=col)
    d.text((x0+34, y+18), name, font=font(29, True), fill=FG)
    d.text((x0+34, y+58), note, font=font(19), fill=DIM)
    d.text((x0+620, y+22), up, font=font(31, True), fill=FG)
    d.text((x0+620, y+62), "up front", font=font(16), fill=DIM)
    d.text((x0+830, y+22), mo, font=font(31, True), fill=col)
    d.text((x0+830, y+62), "recurring", font=font(16), fill=DIM)

d.text((70, 618), "No discount on units one through four. At five boxes, 10% off the fleet.",
       font=font(23, True), fill=ACC)
d.text((70, 656), "The recurring line attaches to every tier that isn't the cloud product —",
       font=font(20), fill=MUTE)
d.text((70, 684), "$1,188/year per deployed box.", font=font(20), fill=MUTE)
footer(d)
img.save(r"B:\pitch\gallery-04-pricing.png", quality=95)
print("04 saved")
