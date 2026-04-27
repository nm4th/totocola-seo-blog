#!/usr/bin/env python3
"""Check generated article body against 薬機法 / 景表法 NG patterns.

Usage:
    python scripts/check_compliance.py output/<slug>.md

Exits 0 if no NG patterns found, otherwise 1 with a list of hits.
The list is intentionally conservative — tune NG_PATTERNS as needed.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# (pattern, reason). Patterns are matched against the raw article body.
NG_PATTERNS: list[tuple[str, str]] = [
    # 医薬品的効能の断定
    (r"治る", "治癒の断定（薬機法）"),
    (r"効く(?!く)", "効能の断定（薬機法）"),
    (r"効果がある", "効果の断定（薬機法）"),
    (r"治療(?!院|薬)", "治療表現（薬機法）"),
    (r"血圧が下がる", "医薬品的効能（薬機法）"),
    (r"血糖値が下がる", "医薬品的効能（薬機法）"),
    (r"免疫力が(上がる|高まる)", "医薬品的効能（薬機法）"),
    (r"アンチエイジング", "アンチエイジング表現（薬機法）"),
    (r"若返る", "若返り表現（薬機法）"),
    (r"シミが消える", "医薬品的効能（薬機法）"),
    (r"痩せる(?!と言われ)", "ダイエット効能の断定（景表法/薬機法）"),
    (r"ダイエットできる", "ダイエット効能の断定（景表法/薬機法）"),
    # 根拠なき最上級
    (r"日本一", "最上級表現（景表法）"),
    (r"世界一", "最上級表現（景表法）"),
    (r"No\.?\s*1", "最上級表現（景表法）"),
    (r"最高(?!の|です)", "最上級表現（景表法）"),
    (r"絶対に(治る|効く|痩せる)", "断定的効能表現（薬機法）"),
]


def check(text: str) -> list[tuple[str, str, str]]:
    hits: list[tuple[str, str, str]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for pat, reason in NG_PATTERNS:
            m = re.search(pat, line)
            if m:
                hits.append((f"L{line_no}", m.group(0), reason))
    return hits


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: check_compliance.py <article.md>", file=sys.stderr)
        return 64

    path = Path(argv[1])
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 1

    text = path.read_text(encoding="utf-8")
    hits = check(text)

    if not hits:
        print(f"OK: {path} — no NG patterns matched")
        return 0

    print(f"NG: {path} — {len(hits)} pattern(s) matched")
    for loc, match, reason in hits:
        print(f"  {loc}: '{match}'  ({reason})")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
