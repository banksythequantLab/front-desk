#!/usr/bin/env python3
"""Score the classifier against a labelled doorstep set.

LABELLING — two options, lowest friction first:

  1. Filename prefix. Name files after the disposition you expect:
       delivery_01.jpg  possible_service_03.jpg  passerby_02.jpg
     Underscores in the disposition are fine; the trailing _NN is stripped.

  2. labels.csv in the image directory, which overrides prefixes:
       filename,expected
       IMG_4821.jpg,possible_service

WATERMARK COMPARISON (--compare):
Every frame Ring returns carries an unremovable server-side watermark. Ring's
own release notes warn models may need retraining because of it. This mode runs
each image twice — clean, then watermark-stamped — and reports whether the
watermark changed the answer. If it did, tuning on clean images is measuring the
wrong distribution.

Usage:
  python eval.py B:\\front-desk\\eval_raw
  python eval.py B:\\front-desk\\eval_raw --compare
"""

import argparse
import csv
import json
import os
import re
import sys
import tempfile
import time
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "classifier"))
from classify import classify, decide, observe          # noqa: E402
from watermark import stamp                             # noqa: E402
from PIL import Image                                   # noqa: E402

EXTS = {".jpg", ".jpeg", ".png", ".webp"}
KNOWN = {"delivery", "possible_service", "visitor", "passerby", "parcel_removed",
         "parcel_present_no_person", "no_person", "no_snapshot", "error"}


def expected_for(name, overrides):
    if name in overrides:
        return overrides[name]
    stem = os.path.splitext(name)[0].lower()
    stem = re.sub(r"[-_ ]?\d+$", "", stem)
    stem = stem.replace("-", "_").replace(" ", "_")
    return stem if stem in KNOWN else None


def load_overrides(d):
    path = os.path.join(d, "labels.csv")
    if not os.path.exists(path):
        return {}
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("filename") and row.get("expected"):
                out[row["filename"].strip()] = row["expected"].strip()
    return out


def run_one(path):
    t0 = time.time()
    out = classify(path)
    out["_sec"] = time.time() - t0
    return out


def run_stamped(path):
    """Classify the same frame with a simulated Ring watermark burned in."""
    fd, tmp = tempfile.mkstemp(suffix=".jpg", prefix="fd_wm_")
    os.close(fd)
    try:
        stamp(Image.open(path)).save(tmp, quality=92)
        return run_one(tmp)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def confusion(rows):
    m = defaultdict(Counter)
    for r in rows:
        m[r["expected"]][r["got"]] += 1
    return m


def print_confusion(m):
    labels = sorted(set(m) | {g for row in m.values() for g in row})
    w = max((len(x) for x in labels), default=8) + 2
    print("\n  expected \\ predicted")
    print("  " + " " * w + "".join(f"{l[:10]:>12}" for l in labels))
    for exp in labels:
        line = f"  {exp:<{w}}"
        for got in labels:
            n = m[exp][got]
            line += f"{(str(n) if n else '.'):>12}"
        print(line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("directory")
    ap.add_argument("--compare", action="store_true",
                    help="also run watermark-stamped copies and report the delta")
    ap.add_argument("--json", help="write full results to this path")
    args = ap.parse_args()

    d = args.directory
    if not os.path.isdir(d):
        sys.exit(f"not a directory: {d}")
    overrides = load_overrides(d)
    files = sorted(f for f in os.listdir(d)
                   if os.path.splitext(f)[1].lower() in EXTS)
    if not files:
        sys.exit(f"no images in {d}")

    rows, unlabelled, flips = [], [], []
    print(f"scoring {len(files)} image(s) from {d}")
    if args.compare:
        print("watermark comparison enabled - each image runs twice\n")
    else:
        print()

    for name in files:
        path = os.path.join(d, name)
        exp = expected_for(name, overrides)
        if exp is None:
            unlabelled.append(name)
            continue

        clean = run_one(path)
        got = clean.get("disposition")
        hit = got == exp
        row = {"file": name, "expected": exp, "got": got, "hit": hit,
               "sec": round(clean["_sec"], 1),
               "escalate": clean.get("escalate"),
               "error": clean.get("error"),
               "notes": (clean.get("observations") or {}).get("notes")}

        line = f"  [{'PASS' if hit else 'FAIL'}] {name:<30} {exp:<24} -> {got:<24} {row['sec']:>5}s"

        if args.compare:
            wm = run_stamped(path)
            row["got_watermarked"] = wm.get("disposition")
            row["watermark_flip"] = wm.get("disposition") != got
            if row["watermark_flip"]:
                flips.append(row)
                line += f"   WATERMARK->{wm.get('disposition')}"
        print(line)
        if not hit and row["notes"]:
            print(f"         saw: {row['notes'][:88]}")
        rows.append(row)

    if not rows:
        sys.exit("\nno labelled images found - see the labelling note in this file's docstring")

    hits = sum(1 for r in rows if r["hit"])
    print(f"\n  accuracy: {hits}/{len(rows)}  ({hits/len(rows)*100:.0f}%)")
    times = [r["sec"] for r in rows]
    print(f"  latency : median {sorted(times)[len(times)//2]:.1f}s  max {max(times):.1f}s")

    # Escalation behaviour matters more than raw accuracy here: missing a
    # possible_service is materially worse than a false alarm.
    svc = [r for r in rows if r["expected"] == "possible_service"]
    if svc:
        caught = sum(1 for r in svc if r["got"] == "possible_service")
        print(f"  possible_service recall: {caught}/{len(svc)}"
              f"   <- the one that matters; a miss is a missed service of process")

    print_confusion(confusion(rows))

    if args.compare:
        print(f"\n  watermark flips: {len(flips)}/{len(rows)}")
        if flips:
            print("  the watermark changed the answer on:")
            for r in flips:
                print(f"    {r['file']}: {r['got']} -> {r['got_watermarked']}")
            print("  => tuning on clean frames is measuring a distribution that does not exist")
        else:
            print("  => no measurable watermark effect on this set")

    if unlabelled:
        print(f"\n  {len(unlabelled)} unlabelled (no disposition prefix, no labels.csv row):")
        for n in unlabelled[:8]:
            print(f"    {n}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=2)
        print(f"\n  wrote {args.json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
