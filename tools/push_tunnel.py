#!/usr/bin/env python3
"""Copy the frontdesk cloudflared tunnel credentials to the box.

The credentials JSON is a secret. It is streamed over SFTP and never printed.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from box import connect                                    # noqa: E402

TUNNEL_ID = "47ad9753-bc7c-4070-b7d2-22147dc94f79"
LOCAL = os.path.expanduser(rf"~\.ssh\..").replace("\\.ssh\\..", "")
CRED = rf"C:\Users\solti\.cloudflared\{TUNNEL_ID}.json"
REMOTE_DIR = "/opt/banksy/front-desk/deploy/cloudflared"
REMOTE_CRED = f"{REMOTE_DIR}/{TUNNEL_ID}.json"
REMOTE_CFG = f"{REMOTE_DIR}/config.yml"

CONFIG = f"""tunnel: {TUNNEL_ID}
credentials-file: {REMOTE_CRED}
protocol: quic
ingress:
  - hostname: frontdesk.quantcity.org
    service: http://127.0.0.1:8310
  - service: http_status:404
"""


def main():
    if not os.path.exists(CRED):
        sys.exit(f"credentials not found: {CRED}")
    data = open(CRED, "rb").read()

    cli = connect()
    try:
        sftp = cli.open_sftp()
        for d in ("/opt/banksy/front-desk/deploy", REMOTE_DIR):
            try:
                sftp.mkdir(d)
            except IOError:
                pass
        with sftp.file(REMOTE_CRED, "wb") as fh:
            fh.write(data)
        sftp.chmod(REMOTE_CRED, 0o600)
        with sftp.file(REMOTE_CFG, "w") as fh:
            fh.write(CONFIG)
        sftp.chmod(REMOTE_CFG, 0o644)
        print(f"credentials -> {REMOTE_CRED}  ({len(data)} bytes, mode 600)")
        print(f"config      -> {REMOTE_CFG}")
        print("(contents not displayed)")
        sftp.close()
    finally:
        cli.close()


if __name__ == "__main__":
    main()
