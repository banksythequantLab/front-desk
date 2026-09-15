# Ring Partner API — developer friction log

Notes from building **Front Desk**, a doorstep agent for a law office, against the
Ring Partner API in September 2026. Every item below cost real debugging time and
is reproducible. Written as feedback, not complaint — the API is good, and these
are the places a first-time integrator loses an afternoon.

Environment: Developers Playground + the official `AmazonAppDev/ring-api-helloworld`
sample. Base `https://api.amazonvision.com`, OAuth at `oauth.ring.com`, scope
`ava.v1:read`.

---

## 1. Event history lives somewhere other than where you'd guess — and fails with 403

**Expected:** `GET /v1/devices/{id}/events`
**Actual:** `GET /v1/history/devices/{id}/events`

The intuitive path returns **403, not 404**. That single character of difference sent
us looking for a permissions problem that did not exist — checking scopes, re-minting
tokens, re-reading the OAuth docs — when the real answer was that the resource simply
lives elsewhere.

**Suggested fix:** return 404 for paths that don't exist. A 403 on a nonexistent route
tells the developer "you lack access to this thing" when the truth is "this thing isn't
here." If the 403 is deliberate (not leaking route existence), say so in the docs.

---

## 2. The Users API returns less than the documentation promises

**Documented:** Account ID, name, email, phone number.
**Actual response from `GET /v1/users/me`:** `email`, `first_name`, `last_name`.

No account ID, no phone. We had designed a device-to-account mapping around an
identifier that isn't returned.

**Suggested fix:** align the reference with the response, or mark the missing fields
as conditional and document what makes them appear.

---

## 3. Simulated events are indistinguishable from a plain live-view session

The Playground advertises Package, Vehicle, and Motion event simulation. We fired a
live-view simulation and then a "Package" simulation and compared what reached the API:

- both returned `event_type: "on_demand"`
- both returned `cv_detections: []`
- both reported a duration of **31,742 ms — identical to the millisecond**

That last detail is what gave it away: the simulations return a canned fixture.
`?include=cv_detections` returns HTTP 200 with no `included` array at all.

**Consequence:** CV detections cannot be developed or tested in the Playground. A
developer building on Ring's detection labels has no way to exercise that path before
going through full app registration and account linking.

**Suggested fix:** either return distinct fixtures per simulated event type with
populated `cv_detections`, or state plainly in the Playground UI that simulations do
not produce CV data. The current behaviour looks like a bug in your own integration
rather than a limitation.

---

## 4. The official sample does no signature verification

`AmazonAppDev/ring-api-helloworld` validates incoming webhooks with a bearer-token
check only. The documentation specifies HMAC signing. A developer who starts from the
sample — which is the documented starting point — ships an endpoint that accepts any
request carrying a shared secret, with no verification that the payload came from Ring
or arrived unmodified.

**Suggested fix:** add HMAC verification to the sample. It's ~15 lines and it's the
difference between a reference implementation and a reference vulnerability. We have
implemented it in this project and are happy to contribute it upstream.

---

## 5. The signature header name isn't stated anywhere we could find

Having decided to verify signatures, we could not determine **which header** carries
the signature. It isn't in the reference, the sample, or the Playground.

Our receiver now accepts any of four candidates and records which one matched, so the
first real delivery will tell us the answer empirically:

```
X-Ring-Signature · X-Amz-Vision-Signature · X-Signature · X-Hub-Signature-256
```

This is guesswork in a security-critical path, which is the worst place for it.

**Suggested fix:** document the header name and the exact bytes signed (raw body?
timestamp-prefixed? canonicalised?), with one worked example.

---

## 6. History events and webhook events are different data models

Events arriving by webhook use a JSON:API envelope — `meta` / `data` / `attributes`
with `source`, `source_type`, `timestamp`, `confidence`, `bounding_box`,
`thumbnail_url`. Events fetched from history do not share that shape.

Anyone who both receives webhooks and backfills from history needs **two normalizers**
and a merge step. This isn't wrong, but it isn't called out, and it's the kind of thing
you discover after writing the first one.

**Suggested fix:** a short doc section comparing the two shapes side by side, or a
note in each reference pointing at the other.

---

## 7. Watermarking changes the input distribution for anyone bringing their own model

Since 2026-06-08 every returned frame carries a server-side watermark (Ring logo,
device ID, app name, timestamp) that cannot be removed. The release notes do flag that
models may need retraining — credit where due, that warning is there and it is correct.

What's missing is anything to tune against: there's no sample watermarked frame, and
no specification of position, font, or opacity. We built a simulator to approximate it
so our evaluation set matches production, but it is an approximation, and any accuracy
delta between our simulated and real watermarks is unexplained until we have a real
watermarked snapshot.

**Suggested fix:** publish one or two example watermarked frames, or the overlay
geometry. For a "bring your own model" platform, the exact pixels you stamp onto every
frame are part of the API contract.

---

## What worked well

- **The Developers Playground is excellent.** One-click 30-minute tokens with no app
  registration or account linking removed the single biggest barrier to a first call.
  We were reading real device capability JSON within minutes.
- **`GET /v1/devices/{id}/configurations` is underrated.** Motion zones as normalized
  polygon vertices plus privacy zones let us wake the classifier only for the doorstep
  region, and gave us a genuine privacy feature for a law office rather than a
  checkbox. This deserves more prominence in the docs than it currently gets.
- **Rate limiting is honest.** 100 TPS per client_id with a real `Retry-After` on 429
  is exactly what you want and is clearly documented.
- **No SDK is the right call.** Plain HTTP with a clear reference beat a thin wrapper
  we'd have to fight.
