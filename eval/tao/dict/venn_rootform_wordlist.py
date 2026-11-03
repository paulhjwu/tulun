#!/usr/bin/env python3
"""
venn_rootform_wordlist.py

Compares two word lists and writes their Venn diagram as three CSV files:

    A = 'root_form' of each record in dictionary_records_deduped.json
    B = 'word' attribute of each <item> in yami_wordlist.xml

    AnB.csv   column 'root_form'   entries in both A and B
    A-B.csv   column 'root_form'   entries only in A
    B-A.csv   column 'word'        entries only in B

Matching is case-insensitive by default, since the wordlist is all lowercase
(e.g. 'Aarva' in A matches 'aarva' in B). AnB and A-B list the original
root_form spelling; B-A lists the wordlist spelling.

Usage:
    python venn_rootform_wordlist.py [--dict DICT] [--wordlist XML] [--outdir DIR] [--case-sensitive]
"""

import argparse
import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path

HERE         = Path(__file__).parent
DEFAULT_DICT = HERE / "dictionary_records_deduped.json"
DEFAULT_XML  = HERE / "yami_wordlist.xml"


def load_root_forms(path):
    with open(path, encoding="utf-8") as f:
        records = json.load(f)
    return {r["root_form"].strip() for r in records if r.get("root_form", "").strip()}


def load_wordlist(path):
    root = ET.parse(path).getroot()
    return {w.strip() for item in root.iter("item") if (w := item.get("word", "")).strip()}


def venn(a, b, case_sensitive=False):
    key = (lambda s: s) if case_sensitive else str.casefold
    a_keys = {key(x) for x in a}
    b_keys = {key(x) for x in b}
    only_a = sorted((x for x in a if key(x) not in b_keys), key=key)
    both   = sorted((x for x in a if key(x) in b_keys), key=key)
    only_b = sorted((x for x in b if key(x) not in a_keys), key=key)
    return only_a, both, only_b


def write_csv(path, header, entries):
    # utf-8-sig so Excel shows the non-ASCII entries correctly
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow([header])
        w.writerows([x] for x in entries)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dict", type=Path, default=DEFAULT_DICT, help="dictionary records JSON (A)")
    ap.add_argument("--wordlist", type=Path, default=DEFAULT_XML, help="wordlist XML (B)")
    ap.add_argument("--outdir", type=Path, default=HERE, help="directory for the three CSV files")
    ap.add_argument("--case-sensitive", action="store_true", help="compare spellings exactly")
    args = ap.parse_args()

    a = load_root_forms(args.dict)
    b = load_wordlist(args.wordlist)
    only_a, both, only_b = venn(a, b, args.case_sensitive)

    args.outdir.mkdir(parents=True, exist_ok=True)
    outputs = [
        ("AnB.csv", "root_form", both),
        ("A-B.csv", "root_form", only_a),
        ("B-A.csv", "word",      only_b),
    ]
    for name, header, entries in outputs:
        write_csv(args.outdir / name, header, entries)

    print(f"A (root_form): {len(a)}   B (word): {len(b)}")
    print(f"A-B: {len(only_a)}   AnB: {len(both)}   B-A: {len(only_b)}")
    print(f"Wrote {', '.join(name for name, _, _ in outputs)} to {args.outdir}")


if __name__ == "__main__":
    main()
