#!/usr/bin/env python3
"""Move Front Desk config and tunnel credentials from Vesper to the box.

Reads the machine environment on Vesper and writes a root-owned 0600
EnvironmentFile on the box over SFTP. Values are never printed, never passed as
shell arguments, and never written to a log — only their presence is reported.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from box import connect                                    # noqa: E402

REMOTE_ENV = "/opt/banksy/front-desk/.env"
KEYS = ["FRONTDESK_HMAC_KEY", "RING_CLIENT_ID", "RING_CLIENT_SECRET"]

FIXED = {
    "FRONTDESK_STORE": "/opt/banksy/front-desk/data/events.jsonl",
    "FD_GRANT_FILE": "/opt/banksy/front-desk/data/.grants.json",
    "FD_VLM_URL": "http://127.0.0.1:8081",
    "FD_MCP_BIND": "0.0.0.0",
    "FD_DASH_BIND": "0.0.0.0",
    "RING_REDIRECT_URI": "https://frontdesk.quantcity.org/oauth/callback",
}


def main():
    vals = {}
    missing = []
    for k in KEYS:
        v = os.environ.get(k)
        if not v:
            missing.append(k)
        else:
            vals[k] = v
    if missing:
        sys.exit(f"missing on this machine: {', '.join(missing)}")

    lines = [f"{k}={v}" for k, v in vals.items()]
    lines += [f"{k}={v}" for k, v in FIXED.items()]
    body = "\n".join(lines) + "\n"

    cli = connect()
    try:
        sftp = cli.open_sftp()
        sftp.mkdir("/opt/banksy/front-desk/data") if "data" not in sftp.listdir(
            "/opt/banksy/front-desk") else None
        with sftp.file(REMOTE_ENV, "w") as fh:
            fh.write(body)
        sftp.chmod(REMOTE_ENV, 0o600)
        st = sftp.stat(REMOTE_ENV)
        sftp.close()
        print(f"wrote {REMOTE_ENV}  mode={oct(st.st_mode)[-3:]}  {st.st_size} bytes")
        print(f"keys written: {', '.join(list(vals) + list(FIXED))}")
        print("(values not displayed)")
    finally:
        cli.close()


if __name__ == "__main__":
    main()
