#!/usr/bin/env python3
"""
Normalise question-bank `options` to the shape the app actually renders.

Every bank but one stores options as a mapping:

    "options": {"A": "eosinophils", "B": "neutrophils"}

`uveitis-oq.json` instead stores an array of objects:

    "options": [{"id": "A", "text": "eosinophils"}, ...]

QuizCard does `Object.keys(question.options).sort()`, which on an array yields
"0","1","2","3", and then renders `options[key]` -- an object.  React throws
"Objects are not valid as a React child", so /quiz/uveitis-oq fails to load at
all and those 181 questions also crash any mock exam that happens to draw one.

This rewrites the array form into the mapping form in place.  It is lossless:
each entry's `id` becomes the key and its `text` the value, preserving order.
A .bak copy is written next to each file it changes.

Usage:  python scripts/normalize_option_shapes.py [--dry-run]
"""

import argparse
import glob
import io
import json
import os
import shutil
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "public", "data")


def convert(options):
    """[{'id': 'A', 'text': '...'}] -> {'A': '...'}; returns None if unconvertible."""
    out = {}
    for entry in options:
        if not isinstance(entry, dict):
            return None
        key, text = entry.get("id"), entry.get("text")
        if not isinstance(key, str) or not isinstance(text, str) or key in out:
            return None
        out[key] = text
    return out or None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    total_files = 0
    for path in sorted(glob.glob(os.path.join(DATA, "*.json"))):
        name = os.path.basename(path)
        if name == "manifest.json" or name.startswith("_"):
            continue
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, list):
            continue

        changed, failed = 0, []
        for q in data:
            opts = q.get("options")
            if not isinstance(opts, list):
                continue
            conv = convert(opts)
            if conv is None:
                failed.append(q.get("id"))
                continue
            if q.get("correctAnswer") not in conv:
                # Never silently orphan an answer key.
                failed.append(q.get("id"))
                continue
            q["options"] = conv
            changed += 1

        if not changed and not failed:
            continue
        total_files += 1
        print(f"{name}: {changed} converted, {len(failed)} left alone")
        if failed:
            print(f"   needs manual review: {failed}")
        if args.dry_run:
            continue
        shutil.copyfile(path, path + ".bak")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
        print(f"   written (backup at {name}.bak)")

    if not total_files:
        print("nothing to convert: every bank already uses the mapping shape")


if __name__ == "__main__":
    main()
