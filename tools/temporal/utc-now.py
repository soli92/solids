#!/usr/bin/env python3
"""
utc-now.py — Generatore canonico di timestamp UTC ISO-8601.
Cross-platform replacement per utc-now.sh (macOS / Linux / Windows).

ADR-030 §A: formato YYYY-MM-DDTHH:MM:SSZ (seconds) o
            YYYY-MM-DDTHH:MM:SS.sssZ (milliseconds).
Usato da: build-temporal-context.py, tutti i pattern EP-011 temporal
         (US-045, US-046, US-047).
Ref: [[temporal-awareness-multiagent-patterns]] §Pattern 1,
     [[temporal-awareness-llm]] §Knowledge cutoff

USO:
  python3 tools/temporal/utc-now.py [--precision=seconds|milliseconds]
  python3 tools/temporal/utc-now.py [--precision seconds|milliseconds]
"""
import sys
import argparse
from datetime import datetime, timezone


def utc_now_seconds() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_now_milliseconds() -> str:
    now = datetime.now(timezone.utc)
    ms = now.microsecond // 1000
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms:03d}Z"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Genera timestamp UTC ISO-8601 (ADR-030 §A).",
        add_help=True,
    )
    parser.add_argument(
        "--precision",
        choices=["seconds", "milliseconds"],
        default="seconds",
        help="Precisione timestamp: seconds (default) o milliseconds.",
    )
    args = parser.parse_args()

    if args.precision == "milliseconds":
        print(utc_now_milliseconds())
    else:
        print(utc_now_seconds())

    return 0


if __name__ == "__main__":
    sys.exit(main())
