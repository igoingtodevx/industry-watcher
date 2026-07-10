#!/usr/bin/env python3
"""Smoke test for the live industry-watcher deployment.

Fetches https://ai-industry-watcher.vercel.app/data/latest.json,
computes the age of `generated_at`, prints it as a number of seconds.
Exit codes:
  0 = fresh (<= max_age_seconds)
  1 = stale
  2 = parse/transport error
"""
from __future__ import annotations
import datetime
import json
import sys
import urllib.request
import urllib.error

URL = "https://ai-industry-watcher.vercel.app/data/latest.json"
MAX_AGE_SECONDS = 1800  # 30 min


def main() -> int:
    try:
        with urllib.request.urlopen(URL, timeout=15) as r:
            body = r.read()
    except urllib.error.URLError as e:
        print(f"FETCH_FAIL: {e}", file=sys.stderr)
        return 2
    try:
        d = json.loads(body)
        ts_raw = d.get("generated_at")
        if not ts_raw:
            print("NO_TIMESTAMP", file=sys.stderr)
            return 2
        ts = datetime.datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        age = int((datetime.datetime.now(datetime.timezone.utc) - ts).total_seconds())
        print(age)
        if age > MAX_AGE_SECONDS:
            print(
                f"STALE: {age}s old (max {MAX_AGE_SECONDS})",
                file=sys.stderr,
            )
            return 1
        return 0
    except (json.JSONDecodeError, ValueError) as e:
        print(f"PARSE_FAIL: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
