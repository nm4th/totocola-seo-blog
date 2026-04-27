#!/usr/bin/env python3
"""Update a row in data/keywords.csv after a run.

Usage:
    python scripts/update_keyword_status.py <id> <status> [--url URL]

Statuses recognised:
    pending | in_progress | published | failed

If status == "published" and --url is given, article_url and published_at are filled.
On failure (status == "failed"), the row is reset back to "pending" so it will be
retried next run — failed history is recorded in notes.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "keywords.csv"
ALLOWED = {"pending", "in_progress", "published", "failed"}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("id", help="row id to update")
    p.add_argument("status", choices=sorted(ALLOWED))
    p.add_argument("--url", default="", help="article URL (when status=published)")
    args = p.parse_args()

    if not CSV_PATH.exists():
        print(f"ERROR: {CSV_PATH} not found", file=sys.stderr)
        return 1

    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    target = None
    for r in rows:
        if r["id"] == args.id:
            target = r
            break
    if target is None:
        print(f"ERROR: id={args.id} not found in {CSV_PATH}", file=sys.stderr)
        return 1

    today = dt.datetime.utcnow().strftime("%Y-%m-%d")

    if args.status == "published":
        target["status"] = "published"
        if args.url:
            target["article_url"] = args.url
        target["published_at"] = today
    elif args.status == "failed":
        # leave status pending so it can be retried; record failure in notes
        existing_notes = target.get("notes", "")
        marker = f"[failed {today}]"
        if marker not in existing_notes:
            target["notes"] = (existing_notes + " " + marker).strip()
        target["status"] = "pending"
    else:
        target["status"] = args.status

    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Updated id={args.id}: status={target['status']} url={target.get('article_url','')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
