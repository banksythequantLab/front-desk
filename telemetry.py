#!/usr/bin/env python3
"""Fleet health telemetry to CloudWatch.

WHAT THIS SENDS, AND WHAT IT NEVER SENDS:
Metadata about the appliance only - uptime, model latency, disk free, whether
services are alive, and counts of classifications by disposition. It never
sends a frame, a transcript, a caller's number, a device name, or any part of
an event's content.

That line is the product. An appliance whose pitch is "nothing leaves the
building" can still report that it is healthy, and being able to say "we can
tell you your box is unwell without ever seeing what is on it" is a stronger
claim than refusing to monitor at all.

Dimensions carry a BoxId only - an opaque hash, not a customer name, so a
fleet can be monitored without the metrics revealing who is who.

Env:
  AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_DEFAULT_REGION
  FD_BOX_ID          opaque id for this appliance (default: hostname hash)
  FD_TELEMETRY_SECS  publish interval, default 300
"""

import hashlib
import hmac
import json
import logging
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone

NAMESPACE = os.environ.get("FD_CW_NAMESPACE", "FrontDesk/Fleet")
INTERVAL = int(os.environ.get("FD_TELEMETRY_SECS", "300"))
REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
STORE = os.environ.get("FRONTDESK_STORE", "data/events.jsonl")
VLM_URL = os.environ.get("FD_VLM_URL", "http://127.0.0.1:8081")

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("telemetry")

BOX = os.environ.get("FD_BOX_ID") or hashlib.sha256(
    socket.gethostname().encode()).hexdigest()[:12]


def uptime_seconds():
    try:
        with open("/proc/uptime") as fh:
            return float(fh.read().split()[0])
    except OSError:
        return None


def disk_free_gb(path="/opt/banksy"):
    try:
        return shutil.disk_usage(path).free / (1024 ** 3)
    except OSError:
        return None


def memory_available_gb():
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / (1024 ** 2)
    except OSError:
        pass
    return None


def service_active(name):
    try:
        out = subprocess.run(["systemctl", "is-active", name],
                             capture_output=True, text=True, timeout=10)
        return 1.0 if out.stdout.strip() == "active" else 0.0
    except Exception:                                       # noqa: BLE001
        return 0.0


def vlm_latency_ms():
    """Round-trip to the vision server's health endpoint - not an inference."""
    t0 = time.time()
    try:
        with urllib.request.urlopen(VLM_URL + "/health", timeout=10):
            pass
        return (time.time() - t0) * 1000
    except Exception:                                       # noqa: BLE001
        return None


def classification_counts(hours=24):
    """Counts by disposition. Counts only - never the events themselves."""
    counts = Counter()
    if not os.path.exists(STORE):
        return counts
    cutoff = time.time() - hours * 3600
    try:
        with open(STORE, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("record_type") != "classification":
                    continue
                ts = rec.get("classified_at")
                if ts:
                    try:
                        t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        if t.timestamp() < cutoff:
                            continue
                    except ValueError:
                        pass
                counts[(rec.get("verdict") or {}).get("disposition", "unknown")] += 1
    except OSError:
        pass
    return counts


def _sign(key, msg):
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def put_metrics(metrics):
    """PutMetricData via a hand-rolled SigV4 POST.

    boto3 would be one import, but it is a large dependency for a single API
    call on an appliance that deliberately keeps its footprint small.
    """
    ak = os.environ.get("AWS_ACCESS_KEY_ID")
    sk = os.environ.get("AWS_SECRET_ACCESS_KEY")
    if not (ak and sk):
        return False, "AWS credentials not configured"

    host = "monitoring." + REGION + ".amazonaws.com"
    now = datetime.now(timezone.utc)
    amzdate = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")

    params = ["Action=PutMetricData", "Version=2010-08-01",
              "Namespace=" + urllib.parse.quote(NAMESPACE, safe="")]
    for i, (name, value, unit) in enumerate(metrics, start=1):
        p = "MetricData.member." + str(i) + "."
        params.append(p + "MetricName=" + urllib.parse.quote(name, safe=""))
        params.append(p + "Value=" + str(value))
        params.append(p + "Unit=" + unit)
        params.append(p + "Dimensions.member.1.Name=BoxId")
        params.append(p + "Dimensions.member.1.Value=" + BOX)
    body = "&".join(sorted(params))

    canonical = "\n".join([
        "POST", "/", "",
        "content-type:application/x-www-form-urlencoded; charset=utf-8",
        "host:" + host, "x-amz-date:" + amzdate, "",
        "content-type;host;x-amz-date",
        hashlib.sha256(body.encode()).hexdigest()])
    scope = datestamp + "/" + REGION + "/monitoring/aws4_request"
    to_sign = "\n".join(["AWS4-HMAC-SHA256", amzdate, scope,
                         hashlib.sha256(canonical.encode()).hexdigest()])
    k = _sign(("AWS4" + sk).encode(), datestamp)
    k = _sign(k, REGION)
    k = _sign(k, "monitoring")
    k = _sign(k, "aws4_request")
    sig = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()

    auth = ("AWS4-HMAC-SHA256 Credential=" + ak + "/" + scope +
            ", SignedHeaders=content-type;host;x-amz-date, Signature=" + sig)
    req = urllib.request.Request(
        "https://" + host + "/", data=body.encode(), method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                 "X-Amz-Date": amzdate, "Authorization": auth, "Host": host})
    try:
        with urllib.request.urlopen(req, timeout=30):
            return True, ""
    except urllib.error.HTTPError as e:
        return False, "HTTP " + str(e.code) + ": " + e.read()[:200].decode(errors="replace")
    except Exception as e:                                  # noqa: BLE001
        return False, str(e)


def collect():
    m = []
    up = uptime_seconds()
    if up is not None:
        m.append(("UptimeSeconds", round(up), "Seconds"))
    df = disk_free_gb()
    if df is not None:
        m.append(("DiskFreeGB", round(df, 2), "Gigabytes"))
    ma = memory_available_gb()
    if ma is not None:
        m.append(("MemoryAvailableGB", round(ma, 2), "Gigabytes"))
    lat = vlm_latency_ms()
    if lat is not None:
        m.append(("VisionLatencyMs", round(lat, 1), "Milliseconds"))
    m.append(("VisionUp", 1.0 if lat is not None else 0.0, "None"))

    for svc, label in (("frontdesk-receiver", "ReceiverUp"),
                       ("frontdesk-poller", "PollerUp"),
                       ("frontdesk-mcp", "McpUp"),
                       ("frontdesk-tunnel", "TunnelUp")):
        m.append((label, service_active(svc), "None"))

    counts = classification_counts()
    m.append(("Classifications24h", sum(counts.values()), "Count"))
    # Only the disposition that matters operationally. The rest stay local.
    m.append(("NeedsReview24h", counts.get("possible_service", 0), "Count"))
    return m


def main():
    log.info("telemetry for box %s -> %s (%s), every %ss",
             BOX, NAMESPACE, REGION, INTERVAL)
    while True:
        metrics = collect()
        ok, err = put_metrics(metrics)
        if ok:
            log.info("published %d metrics", len(metrics))
        else:
            log.warning("publish failed: %s", err)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "once":
        ms = collect()
        for name, value, unit in ms:
            print("  %-22s %s %s" % (name, value, unit))
        ok, err = put_metrics(ms)
        print("publish:", "ok" if ok else err)
    else:
        main()
