# Front Desk

**A doorstep agent for a law office.** A Ring doorbell event arrives, a vision model
running on hardware in the building decides what it's looking at, and the answer reaches
you by voice, by screen, or not at all if it doesn't matter.

Built for the Amazon "Build, Ship, Shape" hackathon across three tracks — Ring, Alexa+,
and Fire TV — by one attorney who is also the customer.

---

## The problem

A process server arrives at a law office. Nobody is at the desk. A camera recorded it,
and that recording sits in a folder nobody opens until it matters — which is usually
after a deadline has already started running.

The general case is unglamorous: a small firm cannot staff a front desk, and the events
at its door have legal consequences that a generic "motion detected" notification does
not capture.

## What it does

```
Ring webhook ──► verify HMAC ──► ack in 27ms ──► queue
                                                  │
                          snapshot ──► downscale ──► vision model (local GPU)
                                                  │
                                    observables ──► deterministic rules
                                                  │
                    ┌─────────────────────────────┼─────────────────────────┐
                    ▼                             ▼                         ▼
              Alexa+ (MCP)                 Fire TV lobby              event store
           "who came by today?"          status and counts           append-only JSONL
```

## The design decision that matters

**The model is never asked whether someone is a process server.** It cannot know, and a
language model asked that question will answer it anyway.

It is asked only for *observables*: is a person visible, are they facing the door, are
they holding a flat envelope, are they in a delivery uniform. A separate deterministic
rules layer turns those facts into a disposition.

That split buys three things:

- **Wrong answers are debuggable.** A bad observation and a bad rule are different bugs.
- **The rules are auditable.** This output can feed a legal record, and "why did it
  decide that" has to have an answer in something other than model weights.
- **Swapping models can't silently change legal behaviour.**

`possible_service` means *a human should look*. It never means service was effected.
That is a legal conclusion a person makes.

## Privacy constraints, built in rather than bolted on

- **No images cross the Alexa+ boundary.** Tool responses carry dispositions and counts;
  `thumbnail_url`, `bounding_box` and raw payloads are stripped, with a test asserting it.
- **The lobby screen shows status and counts, never faces.** A waiting-room display is
  visible to other clients, and who visits a lawyer is itself sensitive.
- **The dashboard is LAN-bound and not tunnelled.** Ring has to reach the webhook
  receiver, so that is public. A lobby screen has no such reason, so it isn't.
- **Every MCP tool is read-only.** Nothing here unlocks, arms, or replies to anyone.
  A voice assistant that can open a door is a different product with a different risk
  profile.

## Running it

```bash
# receiver (public via tunnel — Ring must reach it)
FRONTDESK_HMAC_KEY=... FRONTDESK_STORE=events.jsonl python frontdesk.py

# Alexa+ surface: self-hosted MCP over Streamable HTTP
FRONTDESK_STORE=events.jsonl python mcp_server.py

# Fire TV lobby screen (LAN only)
FRONTDESK_STORE=events.jsonl python dashboard.py
```

The vision model runs on a separate box via llama.cpp's OpenAI-compatible endpoint;
point `FD_VLM_URL` at it. An `ollama` backend is also supported.

## Tests

```bash
python simulate_ring.py     # 12 — signatures, replay, tampering, key encodings
python test_oauth.py        # 12 — consent, single-use codes, client auth
python test_mcp.py          # 10 — real MCP client over Streamable HTTP
python classifier/test_rules.py   # 11 — rules layer, no model needed
python test_e2e.py          #  9 — webhook → snapshot → model → rules → MCP
```

The rules suite caught a real bug on its first run: a courier holding a letter — papers
plus uniform — fell through to `visitor` and would have been escalated as possible
service.

## Hardware

Runs on an AMD Strix Halo box: 32 cores, 128 GB unified memory, 5 SATA bays and 5 NVMe
slots. No ROCm — llama.cpp built against **Vulkan/RADV**, which was already present and
works. Measured on the same binary and model:

| | GPU (`-ngl 99`) | CPU (`-ngl 0`) | |
|---|---|---|---|
| prompt processing | 2,130 t/s | 1,080 t/s | 2.0x |
| token generation | 78 t/s | 34 t/s | 2.3x |

Image preprocessing caps the long edge at 1280px: a full-resolution frame cost 4,319
prompt tokens and 17.1s, versus 1,159 tokens and 5.8s. The cap is 1280 rather than lower
because small-feature detail starts disappearing at 1024 — and envelope-versus-parcel is
exactly a small-feature distinction.

## Honest status

- The classifier's **accuracy is not yet measured**. The pipeline is proven end to end;
  the hard case — manila envelope versus small box, at night, through Ring's watermark —
  needs a real evaluation set.
- Since 2026-06-08 every frame Ring returns carries an unremovable server-side watermark.
  `classifier/watermark.py` simulates it so the eval set matches production, but the
  simulation is an approximation until measured against a real watermarked frame.
- The signature header name and key encoding are **inferred, not documented**. The
  receiver accepts several candidates and records which verified.

See [FRICTION.md](FRICTION.md) for the full developer-experience log.

## License

MIT — see [LICENSE](LICENSE).
