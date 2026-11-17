#!/usr/bin/env python3
"""
split_ab1_by_source.py

Splits A-B.1.csv (output of venn_rootform_wordlist.py) by whether each token
is a 'root' of a record in dictionary_records.json that has a non-empty
'source':

    A-B-1.1.csv   column 'root_form'   token is a root of a sourced record
    A-B-1.2.csv   column 'root_form'   token is not (no record, or only
                                       records with an empty 'source')

Roots are normalized the same way as root_forms in venn_rootform_wordlist.py
before matching: 'agcin ~gcin' is split into 'agcin' and 'gcin', and a
trailing grammar note such as ' (kato)' is removed. Matching is
case-insensitive by default.

Usage:
    python split_ab1_by_source.py [--dict JSON] [--input CSV] [--outdir DIR] [--case-sensitive]
"""

import argparse
import csv
import json
from pathlib import Path

from venn_rootform_wordlist import split_alternates, strip_note, write_csv

HERE          = Path(__file__).parent
DEFAULT_DICT  = HERE / "dictionary_records.json"
DEFAULT_INPUT = HERE / "A-B.1.csv"


def load_sourced_roots(path):
    """Normalized roots of every record whose 'source' is non-empty."""
    with open(path, encoding="utf-8") as f:
        records = json.load(f)
    roots = set()
    for r in records:
        root = r.get("root", "").strip()
        if not root or not r.get("source", "").strip():
            continue
        for part in split_alternates(root):
            roots.add(strip_note(part)[0])
    return roots


def load_tokens(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = csv.reader(f)
        next(rows, None)  # header
        return [row[0] for row in rows if row and row[0].strip()]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dict", type=Path, default=DEFAULT_DICT, help="dictionary records JSON")
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="A-B.1.csv to split")
    ap.add_argument("--outdir", type=Path, default=HERE, help="directory for the two CSV files")
    ap.add_argument("--case-sensitive", action="store_true", help="compare spellings exactly")
    args = ap.parse_args()

    key = (lambda s: s) if args.case_sensitive else str.casefold
    sourced = {key(r) for r in load_sourced_roots(args.dict)}
    tokens = load_tokens(args.input)

    with_source    = [t for t in tokens if key(t) in sourced]
    without_source = [t for t in tokens if key(t) not in sourced]

    args.outdir.mkdir(parents=True, exist_ok=True)
    write_csv(args.outdir / "A-B-1.1.csv", "root_form", with_source)
    write_csv(args.outdir / "A-B-1.2.csv", "root_form", without_source)

    print(f"{args.input.name}: {len(tokens)}   sourced roots: {len(sourced)}")
    print(f"A-B-1.1 (root with source): {len(with_source)}   "
          f"A-B-1.2 (no sourced root): {len(without_source)}")
    print(f"Wrote A-B-1.1.csv, A-B-1.2.csv to {args.outdir}")


if __name__ == "__main__":
    main()
