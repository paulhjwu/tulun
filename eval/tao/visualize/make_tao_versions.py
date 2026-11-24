#!/usr/bin/env python3
"""
Render alignment_parallel.json in the Paratext "compare versions" layout of
Mark1-1Versions.html, writing ../TaoVersions.html.

The hyp text plays the role of the old version and the ref text the new one:

  * aligned tokens          -> replacement  (diffremove hyp + diffadd ref)
  * unaligned hyp tokens    -> deletion     (diffremove), consecutive ones chunked
  * unaligned ref tokens    -> addition     (diffadd),    consecutive ones chunked

A one-to-one alignment of two identical tokens is left as plain, unmarked text.

Usage: python make_tao_versions.py [alignment.json] [-o out.html]
"""
import argparse
import html
import json
import uuid
from itertools import groupby
from pathlib import Path

HERE = Path(__file__).parent
TEMPLATE = HERE / "Mark1-1Versions.html"
DEFAULT_IN = HERE / "alignment_parallel.json"
DEFAULT_OUT = HERE.parent / "TaoVersions.html"

BOOK_IDS = {"08": "RUT", "32": "JON"}


def diff_items(ref, hyp, pairs):
    """Linearise one verse pair into eq / rep / del / add items, in ref order."""
    r2h, h2r = {}, {}
    for r, h in pairs:
        r2h.setdefault(r, set()).add(h)
        h2r.setdefault(h, set()).add(r)

    # Replacement groups: walk the ref; a ref token joins the previous group
    # when it is adjacent to it and shares a hyp token with it (many-to-one).
    groups = []  # each: {"ref": [idx...], "hyp": set(idx)} or {"add": [idx...]}
    for i in range(len(ref)):
        hs = r2h.get(i)
        last = groups[-1] if groups else None
        if hs is None:
            if last and "add" in last:
                last["add"].append(i)
            else:
                groups.append({"add": [i]})
        elif last and "ref" in last and last["hyp"] & hs:
            last["ref"].append(i)
            last["hyp"] |= hs
        else:
            groups.append({"ref": [i], "hyp": set(hs)})

    # Show each hyp token once, in the first group that uses it; a group left
    # with nothing to remove keeps its hyp tokens so it stays a replacement.
    seen, first_group = set(), {}
    for g in groups:
        if "ref" not in g:
            continue
        fresh = g["hyp"] - seen
        for h in fresh:
            first_group[h] = id(g)
        seen |= g["hyp"]
        g["show"] = sorted(fresh or g["hyp"])

    # Unaligned hyp tokens: consecutive runs, anchored after the group holding
    # the hyp token that precedes the run (or at the verse start).
    after = {}  # id(group) or None -> [hyp idx...]
    unaligned = [j for j in range(len(hyp)) if j not in h2r]
    for _, run in groupby(enumerate(unaligned), key=lambda t: t[1] - t[0]):
        run = [j for _, j in run]
        after.setdefault(first_group.get(run[0] - 1), []).extend(run)

    def words(tokens, idxs):
        return " ".join(tokens[i] for i in idxs)

    items = []
    if None in after:
        items.append(("del", words(hyp, sorted(after[None]))))
    for g in groups:
        if "add" in g:
            items.append(("add", words(ref, g["add"])))
            continue
        old, new = words(hyp, g["show"]), words(ref, g["ref"])
        items.append(("eq", new) if old == new else ("rep", old, new))
        if id(g) in after:
            items.append(("del", words(hyp, sorted(after[id(g)]))))
    return items


def render_items(items, key):
    n = 0

    def span(cls, text):
        nonlocal n
        n += 1
        did = uuid.uuid5(uuid.NAMESPACE_URL, f"tao:{key}:{n}")
        return (f'<span class="changebar">&nbsp;</span><span class="{cls}">'
                f"{html.escape(text, quote=False)} <!--diffid:{did}--></span>")

    out = []
    for item in items:
        kind = item[0]
        if kind == "eq":
            out.append(html.escape(item[1], quote=False) + " ")
        elif kind == "rep":
            out.append(span("diffremove", item[1]) + span("diffadd", item[2]))
        elif kind == "del":
            out.append(span("diffremove", item[1]))
        else:
            out.append(span("diffadd", item[1]))
    return "".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("input", nargs="?", type=Path, default=DEFAULT_IN)
    ap.add_argument("-o", "--output", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))

    # Reuse the template's <head> (all of the Paratext CSS) verbatim.
    tpl = TEMPLATE.read_text(encoding="utf-16")
    head = tpl[: tpl.index("<body")].replace("<title></title>", "<title>TaoVersions</title>")

    body = []
    for book_num, book_entries in groupby(sorted(data), key=lambda k: k[:2]):
        book_entries = list(book_entries)
        book = BOOK_IDS.get(book_num, data[book_entries[0]]["book"][:3].upper())
        body.append(f'<div class="usfm"><div class="usfm_id" id="{book}_cv1_0" style="line-height:2;">'
                    f'<span class="marker">\\id</span> {book} - {html.escape(data[book_entries[0]]["book"])} </div>')
        for chapter, keys in groupby(book_entries, key=lambda k: int(data[k]["chapter"])):
            body.append(f'<div><div class="usfm_c"><span class="marker">\\c</span> {chapter}</div>')
            for key in keys:
                v = data[key]
                items = diff_items(v["ref"].split(), v["hyp"].split(), v["alignments"])
                first_verse = v["verses"].split("-")[0]
                body.append(
                    f'<div class="usfm_p" style="line-height:2;"><span class="marker">\\p</span> '
                    f'<span class="usfm_v" id="{book}_cv{chapter}_{first_verse}">'
                    f'<span class="marker">\\v</span> {v["verses"]}</span> '
                    f"{render_items(items, key)}</div>")
            body.append("</div>")
        body.append("</div>")

    args.output.write_text(
        head + '<body contenteditable="true">' + "".join(body) + "</body></html>\n",
        encoding="utf-8")
    print(f"Wrote {args.output} ({len(data)} verse entries)")


if __name__ == "__main__":
    main()
