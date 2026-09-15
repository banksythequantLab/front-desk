#!/usr/bin/env python3
"""Run a command on banksy-box-01 over paramiko.

Vesper's OpenSSH binaries exit 255 with zero output when invoked through
Desktop Commander, so ssh.exe is not usable here. paramiko is pure Python
and bypasses them entirely.

Always address the box by HOSTNAME, not IP: it is on DHCP and moved from
.58 to .72 across a reboot. banksy-box-01.local resolves via mDNS when
forced to IPv4.

Usage:
    python box.py "uname -a; free -g"
    python box.py -f script.sh          # run a local script file on the box
"""

import os
import sys

import paramiko

HOST = os.environ.get("BOX_HOST", "banksy-box-01.local")
USER = os.environ.get("BOX_USER", "banksiai")
KEY = os.environ.get("BOX_KEY", os.path.expanduser(r"~\.ssh\vesper_banksybox"))


def connect():
    key = paramiko.Ed25519Key.from_private_key_file(KEY)
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, pkey=key, timeout=20)
    return cli


def run(cmd, timeout=900):
    cli = connect()
    try:
        _, out, err = cli.exec_command(cmd, timeout=timeout, get_pty=False)
        so = out.read().decode(errors="replace")
        se = err.read().decode(errors="replace")
        rc = out.channel.recv_exit_status()
    finally:
        cli.close()
    return rc, so, se


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    if len(sys.argv) < 2:
        print(__doc__.strip())
        return 2
    if sys.argv[1] == "-f":
        with open(sys.argv[2], encoding="utf-8") as fh:
            cmd = fh.read()
    else:
        cmd = " ".join(sys.argv[1:])
    rc, so, se = run(cmd)
    if so:
        print(so, end="")
    if se.strip():
        print("--- STDERR ---")
        print(se, end="")
    return rc


if __name__ == "__main__":
    sys.exit(main())
