#!/usr/bin/env python3
"""
venn_rootform_wordlist.py

Compares two word lists and writes their Venn diagram as three CSV files:

    A = 'root_form' of each record in dictionary_records_deduped.json
    B = 'word' attribute of each <item> in yami_wordlist.xml

    AnB.csv   column 'root_form'   entries in both A and B
    A-B.1.csv column 'root_form'           entries only in A, main forms
    A-B.2.csv columns 'root_form', 'main'  entries only in A that occur only
                                           as an alternate (after '~'),
                                           with the main form they belong to
    B-A.csv   column 'word'                entries only in B

A root_form with alternate spellings, such as 'agcin ~gcin', is split into
separate tokens ('agcin', 'gcin') before comparison, so each spelling is
checked against the wordlist on its own. Every such pair is also written to

    alt_spelling.csv   columns 'root_form', 'main', 'alternate'

(one row per alternate, so 'akcin ~kcin ~kecin' gives two rows).

A trailing grammar note after a space, such as the ' (kato)' in
'akmanan (kato)', is removed before comparison. Each such change is written to

    mod_spelling.csv   columns 'root_form', 'stripped', 'note'

Matching is case-insensitive by default, since the wordlist is all lowercase
(e.g. 'Aarva' in A matches 'aarva' in B). AnB and A-B list the original
root_form spelling; B-A lists the wordlist spelling.

Usage:
    python venn_rootform_wordlist.py [--dict DICT] [--wordlist XML] [--outdir DIR] [--case-sensitive]
"""

import argparse
import csv
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

HERE         = Path(__file__).parent
DEFAULT_DICT = HERE / "dictionary_records_deduped.json"
DEFAULT_XML  = HERE / "yami_wordlist.xml"


TRAILING_NOTE = re.compile(r"\s*(\([^()]*\))\s*$")


def split_alternates(root_form):
    """Split 'agcin ~gcin' into ['agcin', 'gcin'].

    Handles any number of variants ('akcin ~kcin ~kecin'), missing or extra
    spaces around '~' ('hawang~'awang', 'otwan ~ 'otwan'), and a trailing
    grammar note shared by all variants ('makaitkeh ~maka'itkeh (ji)' ->
    ['makaitkeh (ji)', "maka'itkeh (ji)"]). A root_form with no '~' comes
    back as a one-element list.
    """
    note = ""
    m = TRAILING_NOTE.search(root_form)
    if m and "~" in root_form[:m.start()]:
        note = " " + m.group(1)
        root_form = root_form[:m.start()]
    parts = [p.strip() for p in root_form.split("~")]
    return [p + note for p in parts if p]


SPACED_NOTE = re.compile(r"\s+(\([^()]*\))\s*$")


def strip_note(token):
    """Drop a trailing grammar note: 'akmanan (kato)' -> ('akmanan', '(kato)').

    The note must follow whitespace, so word-internal parentheses such as
    'peyoyaoya(n)' are left alone. Returns (token, None) when there is no note.
    """
    m = SPACED_NOTE.search(token)
    if not m or not token[:m.start()].strip():
        return token, None
    return token[:m.start()].strip(), m.group(1)


def load_root_forms(path):
    """Return (tokens, alt_pairs, alt_main, mod_pairs).

    tokens    set of root_form spellings, with '~' alternates split apart
              and trailing grammar notes such as ' (kato)' removed
    alt_pairs list of (root_form, main, alternate) for each '~' alternate
    alt_main  {alternate: main} for spellings that occur only after a '~'
              (never as a main form or a plain root_form)
    mod_pairs set of (original, stripped, note) for each note removed
    """
    with open(path, encoding="utf-8") as f:
        records = json.load(f)
    tokens, alt_pairs, seen = set(), [], set()
    main_tokens, alt_main, mod_pairs = set(), {}, set()
    for r in records:
        rf = r.get("root_form", "").strip()
        if not rf:
            continue
        parts = []
        for p in split_alternates(rf):
            stripped, note = strip_note(p)
            if note:
                mod_pairs.add((p, stripped, note))
            parts.append(stripped)
        tokens.update(parts)
        main_tokens.add(parts[0])
        for alt in parts[1:]:
            alt_main.setdefault(alt, parts[0])
        if len(parts) > 1 and rf not in seen:
            seen.add(rf)
            alt_pairs.extend((rf, parts[0], alt) for alt in parts[1:])
    alt_main = {k: v for k, v in alt_main.items() if k not in main_tokens}
    return tokens, alt_pairs, alt_main, mod_pairs


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

    a, alt_pairs, alt_main, mod_pairs = load_root_forms(args.dict)
    b = load_wordlist(args.wordlist)
    only_a, both, only_b = venn(a, b, args.case_sensitive)
    only_a_main = [x for x in only_a if x not in alt_main]
    only_a_alt  = [x for x in only_a if x in alt_main]

    args.outdir.mkdir(parents=True, exist_ok=True)
    with open(args.outdir / "alt_spelling.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["root_form", "main", "alternate"])
        w.writerows(sorted(alt_pairs, key=lambda p: p[0].casefold()))

    with open(args.outdir / "mod_spelling.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["root_form", "stripped", "note"])
        w.writerows(sorted(mod_pairs, key=lambda p: p[0].casefold()))

    outputs = [
        ("AnB.csv",   "root_form", both),
        ("A-B.1.csv", "root_form", only_a_main),
        ("B-A.csv",   "word",      only_b),
    ]
    for name, header, entries in outputs:
        write_csv(args.outdir / name, header, entries)

    # A-B.2: alternate spellings, with the main form they belong to
    with open(args.outdir / "A-B.2.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["root_form", "main"])
        w.writerows((x, alt_main[x]) for x in only_a_alt)

    print(f"A (root_form): {len(a)}   B (word): {len(b)}")
    print(f"A-B: {len(only_a)} (A-B.1 main: {len(only_a_main)}, A-B.2 alternate: {len(only_a_alt)})"
          f"   AnB: {len(both)}   B-A: {len(only_b)}")
    print(f"Alternate-spelling pairs: {len(alt_pairs)}   Notes stripped: {len(mod_pairs)}")
    print(f"Wrote AnB.csv, A-B.1.csv, A-B.2.csv, B-A.csv, alt_spelling.csv, mod_spelling.csv"
          f" to {args.outdir}")


if __name__ == "__main__":
    main()
