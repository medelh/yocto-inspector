#!/usr/bin/env python3

import os
import re
import argparse
from collections import defaultdict

PROVIDES_RE = re.compile(r'^\s*(R?PROVIDES)(?::\w+)?\s*([+]?=)\s*"([^"]+)"')
INHERIT_RE = re.compile(r'^\s*inherit\s+(.+)')


def find_files(root, suffixes):
    for base, _, files in os.walk(root):
        for f in files:
            if any(f.endswith(s) for s in suffixes):
                yield os.path.join(base, f)


def parse_file(path):
    provides = []
    inherits = []

    try:
        with open(path, "r", errors="ignore") as f:
            for line in f:
                m = PROVIDES_RE.match(line)
                if m:
                    provides += m.group(3).split()

                m = INHERIT_RE.match(line)
                if m:
                    inherits += m.group(1).split()
    except IOError:
        pass

    return provides, inherits


def find_bbappends(root, recipe_name):
    matches = []
    for f in find_files(root, [".bbappend"]):
        if os.path.basename(f).startswith(recipe_name):
            matches.append(f)
    return matches


def resolve_classes(root, class_names):
    paths = []
    for cls in class_names:
        for f in find_files(root, [".bbclass"]):
            if os.path.basename(f) == f"{cls}.bbclass":
                paths.append(f)
    return paths


def investigate_recipe(root, recipe_path):
    collected = defaultdict(list)
    visited = set()

    def walk(path, origin):
        if path in visited:
            return
        visited.add(path)

        provides, inherits = parse_file(path)
        for p in provides:
            collected[p].append(origin + [path])

        cls_paths = resolve_classes(root, inherits)
        for c in cls_paths:
            walk(c, origin + [path])

    recipe_name = os.path.basename(recipe_path).split("_")[0]

    walk(recipe_path, [])

    for append in find_bbappends(root, recipe_name):
        walk(append, [])

    return collected


def scan_virtual_provides(root):
    results = defaultdict(list)

    for f in find_files(root, [".bb", ".bbappend", ".bbclass"]):
        provides, _ = parse_file(f)
        for p in provides:
            if p.startswith("virtual/"):
                results[p].append(f)

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Yocto PROVIDES inspector")
    parser.add_argument("root", help="Yocto layers root")
    parser.add_argument("--scan-virtual", action="store_true")
    parser.add_argument("--recipe", help="Recipe to investigate")

    args = parser.parse_args()

    if args.scan_virtual:
        virt = scan_virtual_provides(args.root)
        for v, files in virt.items():
            print(f"\n{v}")
            for f in files:
                print(f"  - {f}")

    if args.recipe:
        info = investigate_recipe(args.root, args.recipe)
        for prov, chains in info.items():
            print(f"\nPROVIDES: {prov}")
            for chain in chains:
                for f in chain:
                    print(f"  -> {f}")
