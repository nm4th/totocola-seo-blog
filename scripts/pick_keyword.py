#!/usr/bin/env python3
"""Pick the next keyword to write about from data/keywords.csv.

Selection rule:
  status == "pending"
  ordered by priority (high > medium > low) then by id ascending.

Outputs to GitHub Actions:
  - Writes KEYWORD_ID, KEYWORD, SEARCH_INTENT, PRIORITY, NOTES to $GITHUB_OUTPUT
  - Prints a human-readable summary to stdout

Exits non-zero if no pending keyword is found.
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "keywords.csv"
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def main() -> int:
    if not CSV_PATH.exists():
        print(f"ERROR: {CSV_PATH} not found", file=sys.stderr)
        return 1

    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    pending = [r for r in rows if r["status"].strip() == "pending"]
    if not pending:
        print("ERROR: no pending keywords. Add a row to data/keywords.csv.", file=sys.stderr)
        return 2

    pending.sort(key=lambda r: (PRIORITY_ORDER.get(r["priority"].strip(), 99), int(r["id"])))
    pick = pending[0]

    print(f"Picked keyword id={pick['id']}: {pick['keyword']}")
    print(f"  intent={pick['search_intent']} priority={pick['priority']}")
    if pick["notes"]:
        print(f"  notes: {pick['notes']}")

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"keyword_id={pick['id']}\n")
            fh.write(f"keyword={pick['keyword']}\n")
            fh.write(f"search_intent={pick['search_intent']}\n")
            fh.write(f"priority={pick['priority']}\n")
            fh.write(f"notes={pick['notes']}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
