# Front Desk — operations runbook

Everything runs on **banksy-box-01** (`192.168.68.72`, `banksy-box-01.local`).
Vesper is a dev machine only; nothing production lives there.

---

## Credentials — where they are

| What | Where | Notes |
|---|---|---|
| Ring Client ID / Secret / HMAC key | `/opt/banksy/front-desk/.env` on the box, mode 600 | Loaded by systemd via `EnvironmentFile`. Ring shows these **once** — there is no regenerate; rotation means deleting the app and creating a new one. |
| Operator sign-in password | `/opt/banksy/front-desk/data/.operator-password`, mode 600 | Move to a password manager and `shred -u` the file. Username is `FD_ADMIN_USER` in `.env`. |
| Ring OAuth tokens (after linking) | `/opt/banksy/front-desk/data/.tokens.json`, mode 600 | Written by the linking flow. Gitignored. |
| Cloudflare tunnel credentials | `/opt/banksy/front-desk/deploy/cloudflared/`, mode 600 | Tunnel `47ad9753-bc7c-4070-b7d2-22147dc94f79`. |

Nothing above is in git. `.gitignore` covers `.env`, `*.jsonl`, `.tokens.json`,
`.grants.json`, logs and `eval_set/`.

To see which keys are set without printing values:

```bash
cut -d= -f1 /opt/banksy/front-desk/.env
```

---

## Services

```bash
systemctl status frontdesk-vlm          # vision model  :8081
systemctl status frontdesk-receiver     # Ring webhooks :8310
systemctl status frontdesk-mcp          # Alexa+ (MCP)  :8311
systemctl status frontdesk-dashboard    # Fire TV       :8313  LAN only
systemctl status frontdesk-tunnel       # frontdesk.quantcity.org

sudo systemctl restart frontdesk-receiver
sudo journalctl -u frontdesk-receiver -n 50 --no-pager
```

All five are `enabled` and `Restart=always`, so they survive reboots.

Logs: `/opt/banksy/front-desk/logs/{receiver,mcp,dashboard,tunnel,vlm_server}.log`

---

## Health checks

```bash
curl -s https://frontdesk.quantcity.org/health          # public, via tunnel
curl -s http://127.0.0.1:8081/health                    # vision model
curl -s http://127.0.0.1:8313/api/summary               # dashboard data
```

Healthy receiver looks like:
`{"ok": true, "hmac_configured": true, "classifier": "on", "records_stored": N}`

---

## From Vesper — driving the box

`ssh.exe` is broken under Desktop Commander (exits 255, no output). Use paramiko:

```powershell
cd D:\front-desk\tools
python box.py "uptime; free -g"
python box.py -f some_script.sh
$env:BOX_HOST='192.168.68.72'      # if mDNS is flaky
```

**Never** use `pkill -f <pattern>` in a script run this way — `box.py` sends the
whole script as the remote command line, so the pattern matches its own shell
and kills the session. Kill by listening port instead.

---

## Tests

```bash
cd /opt/banksy/front-desk
./.venv/bin/python simulate_ring.py        # 12 — signatures, replay, tampering
./.venv/bin/python test_ring_link.py       # 31 — nonce, sign-in, token refresh
./.venv/bin/python test_mcp.py             # 10 — real MCP client
./.venv/bin/python test_e2e.py             #  9 — webhook -> model -> rules -> MCP
cd classifier && ../.venv/bin/python test_rules.py   # 11 — rules, no model needed
```

Tests bind 8410-8412 so they never collide with the running services.

---

## Classifier

```bash
# score a labelled set; --compare also runs watermark-stamped copies
./.venv/bin/python eval.py /path/to/images --compare --json results.json
```

Labels: filename prefix (`delivery_01.png`) or `labels.csv` with
`filename,expected[,prior_parcel]`.

Current: 18/20 (90%), `possible_service` recall 3/3, zero misses.

---

## Ring documentation

Ring runs a knowledge MCP server. It has settled several things this project was
guessing at — ask it before assuming.

```bash
./.venv/bin/python tools/ringdocs.py "webhook retry policy"
./.venv/bin/python tools/ringdocs.py --doc amazon_vision_api/notifications.md --chars 12000
```

---

## Settled Ring facts (confirmed, not inferred)

- Signature header is **`X-Signature`**, value `sha256=<lowercase hex>`
- Signing key is used as **UTF-8 bytes** — do NOT base64-decode it
- Same key, two encodings: **hex** for webhook signatures, **URL-safe base64** for nonces
- Account ID comes from `GET /v1/users/me` → `data.id`
- Account linking POST **and** PATCH are both required; the PATCH is what makes it live
- Webhooks need HTTP 200 **within 5 seconds**; retries run out to 1 hour
- Motion events fire only inside configured detection zones
- Private apps: single environment, max 5 accounts, no per-account disconnect,
  cannot be converted to public

---

## Known blockers

- **Account linking incomplete.** Ring has never called our Token Exchange URL.
  Possibly the connected account's subscription tier; support case pending.
- **Outbound calls to `oauth.ring.com` get Cloudflare error 1010** (403) from
  Python's `urllib`. Likely needs a real User-Agent or `requests`. Untested fix.
- **The watermark simulation is unvalidated** against a real Ring frame.
