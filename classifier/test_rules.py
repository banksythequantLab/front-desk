#!/usr/bin/env python3
"""Rules-layer tests. No VLM required - decide() is pure."""

from classify import decide

BASE = dict(person_visible=True, facing_door=True,
            holding_flat_envelope_or_papers=False, holding_parcel_or_box=False,
            wearing_delivery_uniform=False, parcel_on_ground=False,
            image_quality="clear")

CASES = [
    ("courier with box", {**BASE, "holding_parcel_or_box": True,
                          "wearing_delivery_uniform": True}, None, "delivery"),
    ("uniform, no box", {**BASE, "wearing_delivery_uniform": True}, None, "delivery"),
    ("papers at door", {**BASE, "holding_flat_envelope_or_papers": True},
     None, "possible_service"),
    ("papers + uniform", {**BASE, "holding_flat_envelope_or_papers": True,
                          "wearing_delivery_uniform": True}, None, "delivery"),
    ("empty handed at door", {**BASE}, None, "visitor"),
    ("walking past", {**BASE, "facing_door": False}, None, "passerby"),
    ("nobody, parcel on step", {**BASE, "person_visible": False,
                                "parcel_on_ground": True}, None,
     "parcel_present_no_person"),
    ("nobody, nothing", {**BASE, "person_visible": False}, None, "no_person"),
    ("parcel gone, person there", {**BASE}, True, "parcel_removed"),
    ("obstructed lens", {**BASE, "image_quality": "obstructed"}, None, "no_person"),
    ("null observations", None, None, "error"),
]


def run():
    passed = 0
    for name, obs, prior, want in CASES:
        got = decide(obs, prior)
        hit = got["disposition"] == want
        passed += hit
        tag = "PASS" if hit else "FAIL"
        print(f"  [{tag}] {name:<26} -> {got['disposition']:<26} "
              f"escalate={got['escalate']}")
    print(f"\n{passed}/{len(CASES)} rule cases passed")
    return 0 if passed == len(CASES) else 1


if __name__ == "__main__":
    raise SystemExit(run())
