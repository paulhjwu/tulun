"""Align Chang and CUNP89T verses for Ruth and Jonah.

Chang is the reference: each of its verses (or verse ranges such as "1-2")
becomes one entry, and the CUNP89T verses covered by that range are joined.

Output keys have the form BBCCCVVV-VVV (book, chapter, first verse, last verse),
e.g. "08001001-002" for Ruth 1:1-2 and "32004011-011" for Jonah 4:11.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent / "benchmark_data"

# Books in the order they appear in both files.
BOOKS = [("RUT", 8), ("JON", 32)]

TOKEN_RE = re.compile(
    r'<div class="majortitle-1">'
    r'|<span class="chaptermarker">\s*(?P<chapter>\d+)\s*</span>'
    r'|<span class="verse">\s*<sup class="versemarker">(?P<marker>.*?)</sup>(?P<body>.*?)</span>',
    re.DOTALL,
)
SECTIONHEAD_RE = re.compile(r'<div class="sectionhead-1">.*?</div>', re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
MARKER_RE = re.compile(r"(\d+)\s*(?:[-–]\s*(\d+))?")


def clean(body):
    body = SECTIONHEAD_RE.sub(" ", body)
    body = TAG_RE.sub(" ", body)
    return re.sub(r"\s+", " ", html.unescape(body)).strip()


def parse(path):
    """Return [(book_index, chapter, first_verse, last_verse, text), ...] in file order."""
    text = Path(path).read_text(encoding="utf-8")
    verses = []
    book, chapter, last_end = -1, None, 0
    for m in TOKEN_RE.finditer(text):
        if m.group("chapter"):
            if book < 0:
                book = 0
            chapter, last_end = int(m.group("chapter")), 0
        elif m.group("marker") is None:
            # <div class="majortitle-1"> starts a new book (CUNP89T only)
            book, chapter, last_end = book + 1, None, 0
        else:
            nums = MARKER_RE.search(m.group("marker"))
            first = int(nums.group(1))
            last = int(nums.group(2) or first)
            if last_end and first <= last_end:
                # verse numbering restarted with no chapter marker: new book, chapter 1
                # (Chang has no marker for Jonah 1)
                book, chapter = book + 1, 1
            elif chapter is None:
                chapter = 1
            last_end = last
            verses.append((book, chapter, first, last, clean(m.group("body"))))
    return verses


def align(chang_path, cunp_path):
    cunp = {}
    for book, chapter, first, last, text in parse(cunp_path):
        for v in range(first, last + 1):
            cunp.setdefault((book, chapter, v), []).append(text)

    used = set()
    aligned = {}
    for book, chapter, first, last, text in parse(chang_path):
        if book >= len(BOOKS):
            sys.exit(f"Chang has more than {len(BOOKS)} books (at chapter {chapter}:{first})")
        parts = []
        for v in range(first, last + 1):
            key = (book, chapter, v)
            if key in cunp:
                parts.extend(cunp[key])
                used.add(key)
            else:
                print(f"warning: CUNP89T has no {BOOKS[book][0]} {chapter}:{v}", file=sys.stderr)
        bb = BOOKS[book][1]
        aligned[f"{bb:02d}{chapter:03d}{first:03d}-{last:03d}"] = {
            "Chang": text,
            "CUNP89T": " ".join(parts),
        }

    for book, chapter, v in sorted(set(cunp) - used):
        print(f"warning: CUNP89T {BOOKS[book][0]} {chapter}:{v} not in Chang", file=sys.stderr)
    return aligned


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--chang", default=DATA_DIR / "Chang-RUT-JON.html")
    ap.add_argument("--cunp", default=DATA_DIR / "CUNP89T-RUT-JON.html")
    ap.add_argument("-o", "--output", default=DATA_DIR / "aligned-RUT-JON.json")
    args = ap.parse_args()

    aligned = align(args.chang, args.cunp)
    Path(args.output).write_text(
        json.dumps(aligned, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(aligned)} aligned entries to {args.output}")


if __name__ == "__main__":
    main()
