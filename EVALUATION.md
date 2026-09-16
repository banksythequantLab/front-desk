# Evaluation — first measured run

20 real doorstep frames, classified on a local Qwen3-VL-30B-A3B via llama.cpp/Vulkan.
Dispositions come from the deterministic rules layer; the model is only ever asked for
observables.

```
accuracy            18/20   (90%)
possible_service    3/3     (recall - zero misses)
latency             median 4.2s   max 5.6s
```

| expected | n | correct |
|---|---|---|
| delivery | 11 | 9 |
| **possible_service** | **3** | **3** |
| no_person | 2 | 2 |
| visitor | 2 | 2 |
| passerby | 1 | 1 |
| parcel_removed | 1 | 1 |

## Zero misses

Every error in this run is a false alarm. `possible_service` recall is 3/3 — nothing that
should have been flagged for review went unflagged.

That asymmetry is the point. A false alarm costs a lawyer ten seconds of attention. A miss
costs a deadline that started running without anyone knowing. The rules layer is built to
fail in the first direction, and on this set it does.

It is also not indiscriminate: nine deliveries, two visitors, a passerby, two empty frames
and a resident retrieving a package all classified correctly. The system discriminates, and
where it is wrong it is wrong toward caution.

## The two failures are the same failure

Both are `delivery -> possible_service`: a postal carrier in plain clothes holding
letters, with no truck, bag, scanner or logo in frame. The model's own description of one
of them:

> a person wearing a white t-shirt and a bucket hat stands outside a building, holding
> papers, with a car parked in the background

**This is not a prompt-tuning failure.** We tried: the observation prompt was expanded to
count a logo cap, a courier satchel, a hi-vis vest or a handheld scanner as a uniform, and
two new observables were added (`carrying_courier_bag_or_scanner`,
`delivery_vehicle_visible`). Net effect across the set was zero — one frame fixed, one
broken.

The reason is that **the distinguishing evidence is not in the frame.** A person in a
t-shirt holding papers at a door is visually a process server and visually a mail carrier.
A human shown that single image could not reliably tell them apart either. Tuning further
would teach the model to guess confidently, which is worse than the current behaviour, not
better.

The real fix is more context, not a better prompt:
- the marked vehicle that was in frame ten seconds earlier
- arrival history — the same figure at 11am every weekday is a mail carrier
- Ring's own event metadata across a sequence rather than a single snapshot

## The errors are in the safe direction

Every failure in this run is a **false alarm, never a miss**. The system flags a mail
carrier for human review rather than letting a possible service of process pass unnoticed.

For a law office that is the correct way to be wrong, and it is a property of the rules
layer rather than an accident: `possible_service` requires papers AND facing the door AND
no courier markings, and it means *a human should look* — never that service was effected.

## What the transition rule bought

One frame in the set is the resident retrieving a package that had been left on the step.
From a single image that is indistinguishable from a person at the door holding a flat
object, and it classified as `possible_service` until the harness could express prior-frame
state.

With `prior_parcel=true` the rules layer returns `parcel_removed` correctly. Parcel removal
was deliberately designed as a cross-frame transition that can never be asserted from one
image — this set is the evidence that the design was right, and that a single-frame
classifier would have raised a false alarm on one of the most common events at any door.

## Known gaps

- **20 frames is small.** Every number here has wide error bars. Three positive
  `possible_service` examples is enough to show the path works end to end, not enough to
  bound recall with any confidence.
- **No watermarked comparison yet.** `--compare` runs each frame clean and
  watermark-stamped, but the stamp is a simulation of Ring's overlay, not the real thing.
- **Daylight-heavy.** Two night frames, no IR frames.

## Reproducing

```bash
python eval.py <dir> --compare --json results.json
```

Labels come from filename prefixes or a `labels.csv` of
`filename,expected[,prior_parcel]`.
