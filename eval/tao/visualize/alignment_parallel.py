#!/usr/bin/env python3
"""
alignment_parallel.py

Reads sorted.csv, takes the parallel verses in its 'ref' (Chang) and 'hyp'
(CUNP89T) columns, aligns them word-by-word using awesome-align, and writes
the results to alignment_parallel.json.

Output keys are the 'key' column of the CSV (BBCCCVVV-VVV), in CSV order:

    { key: {
          "book": ..., "chapter": ..., "verses": ...,
          "ref": "...", "hyp": "...",
          "alignments": [[ref_idx, hyp_idx], ...]
    }}

Usage:
    python alignment_parallel.py [--input INPUT] [--model MODEL] [--output OUTPUT] [--batch-size N]
"""

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

INPUT_CSV   = Path(__file__).parent / "sorted.csv"
DEFAULT_OUT = Path(__file__).parent / "alignment_parallel.json"

MODEL_ALIASES = {
    "mbert": "bert-base-multilingual-cased",
    "xlmr":  "xlm-roberta-base",
}


# ── awesome-align helpers ─────────────────────────────────────────────────

def normalize_model_name(name: str) -> str:
    return MODEL_ALIASES.get(name.lower(), name)


def check_awesome_align() -> bool:
    return shutil.which("awesome-align") is not None


def run_awesome_align(input_file: str, output_file: str, model: str, batch_size: int) -> bool:
    cmd = [
        "awesome-align",
        "--output_file", output_file,
        "--model_name_or_path", model,
        "--data_file", input_file,
        "--extraction", "softmax",
        "--batch_size", str(batch_size),
    ]
    return subprocess.run(cmd).returncode == 0


def parse_alignments(line: str) -> list[tuple[int, int]]:
    """Parse awesome-align output such as '0-0 1-2 2-1' into [(0, 0), (1, 2), (2, 1)]."""
    pairs = []
    for item in line.split():
        s, _, t = item.partition("-")
        if s.isdigit() and t.isdigit():
            pairs.append((int(s), int(t)))
    return pairs


# ── Step 1: collect verse pairs from sorted.csv ───────────────────────────

def collect_verse_pairs(csv_path: str) -> list[dict]:
    """
    Return one dict per CSV row that has both a non-empty 'ref' and 'hyp',
    with whitespace collapsed so the word indices match awesome-align's.
    """
    pairs = []
    with open(csv_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            ref = " ".join((row.get("ref") or "").split())
            hyp = " ".join((row.get("hyp") or "").split())
            if ref and hyp:
                pairs.append({
                    "key":    row["key"],
                    "book":   row["book"],
                    "chapter": row["chapter"],
                    "verses": row["verses"],
                    "ref":    ref,
                    "hyp":    hyp,
                })
    return pairs


# ── Step 2: write awesome-align input file ────────────────────────────────

def write_corpus(pairs: list[dict], corpus_path: str) -> None:
    """Write 'ref ||| hyp' lines — one per verse pair."""
    with open(corpus_path, "w", encoding="utf-8") as f:
        for p in pairs:
            f.write(f"{p['ref']} ||| {p['hyp']}\n")


# ── Step 3: parse alignments and build output dict ────────────────────────

def build_result(pairs: list[dict], align_path: str) -> dict:
    """Merge the verse pairs with the awesome-align output, keyed by 'key'."""
    with open(align_path, encoding="utf-8") as f:
        align_lines = f.readlines()

    result: dict = {}
    for i, p in enumerate(pairs):
        raw_align = align_lines[i].strip() if i < len(align_lines) else ""
        align_pairs = parse_alignments(raw_align)

        n_ref = len(p["ref"].split())
        n_hyp = len(p["hyp"].split())
        alignments = [
            [s, t]
            for s, t in sorted(align_pairs, key=lambda a: a[0])
            if s < n_ref and t < n_hyp
        ]

        result[p["key"]] = {
            "book":       p["book"],
            "chapter":    p["chapter"],
            "verses":     p["verses"],
            "ref":        p["ref"],
            "hyp":        p["hyp"],
            "alignments": alignments,
        }

    return result


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Align the ref/hyp verses of sorted.csv with awesome-align")
    parser.add_argument("--input",      default=str(INPUT_CSV),
                        help="CSV with 'ref' and 'hyp' columns (default: sorted.csv)")
    parser.add_argument("--model",      default="bert-base-multilingual-cased",
                        help="HuggingFace model name or path (default: bert-base-multilingual-cased)")
    parser.add_argument("--output",     default=str(DEFAULT_OUT),
                        help="Output JSON file (default: alignment_parallel.json)")
    parser.add_argument("--batch-size", type=int, default=32,
                        help="Batch size for awesome-align (default: 32)")
    args = parser.parse_args()

    model = normalize_model_name(args.model)
    if model != args.model:
        print(f"Model alias: '{args.model}' → '{model}'")

    if not check_awesome_align():
        print("Error: awesome-align is not installed or not on PATH.")
        print("Install it with: pip install awesome-align")
        sys.exit(1)

    print(f"Loading {args.input} …")
    pairs = collect_verse_pairs(args.input)
    print(f"Verses with both ref + hyp: {len(pairs)}")

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as corpus_tmp, \
         tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as align_tmp:
        corpus_path = corpus_tmp.name
        align_path  = align_tmp.name

    try:
        print("Writing parallel corpus …")
        write_corpus(pairs, corpus_path)

        print(f"Running awesome-align (model: {model}, batch_size: {args.batch_size}) …")
        if not run_awesome_align(corpus_path, align_path, model, args.batch_size):
            print("awesome-align failed. Exiting.")
            sys.exit(1)

        print("Parsing alignments …")
        result = build_result(pairs, align_path)

        total_pairs = sum(len(v["alignments"]) for v in result.values())
        print(f"Aligned verses : {len(result)}")
        print(f"Total word pairs: {total_pairs}")

        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"Output written → {args.output}")

    finally:
        for p in (corpus_path, align_path):
            if os.path.exists(p):
                os.unlink(p)


if __name__ == "__main__":
    main()
