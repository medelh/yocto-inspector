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


def build_indexes(root):
    provides_index = defaultdict(list)
    reverse_inherit = defaultdict(list)

    for f in find_files(root, [".bb", ".bbclass", ".bbappend"]):
        provides, inherits = parse_file(f)

        for p in provides:
            provides_index[p].append(f)

        for cls in inherits:
            reverse_inherit[cls].append(f)

    return provides_index, reverse_inherit


def find_bbappends(root, recipe_path):
    base = os.path.basename(recipe_path).split("_")[0]
    return [
        f for f in find_files(root, [".bbappend"])
        if os.path.basename(f).startswith(base)
    ]


def print_tree(path, level, label):
    indent = "  " * level
    print(f"{indent}└── {os.path.basename(path)} {label}")


def trace_upward(root, start_class, reverse_inherit, level, visited):
    if start_class in visited:
        return
    visited.add(start_class)

    users = reverse_inherit.get(start_class, [])
    for u in users:
        print_tree(u, level, "[INHERITS]")

        if u.endswith(".bb"):
            for app in find_bbappends(root, u):
                print_tree(app, level + 1, "[BBAPPEND]")

        if u.endswith(".bbclass"):
            cls = os.path.basename(u).replace(".bbclass", "")
            trace_upward(root, cls, reverse_inherit, level + 1, visited)


def search_target(root, target):
    provides_index, reverse_inherit = build_indexes(root)

    providers = provides_index.get(target, [])
    if not providers:
        print(f"No providers found for {target}")
        return

    for p in providers:
        print(f"\n{target}")
        print_tree(p, 0, "[DIRECT]")

        if p.endswith(".bbclass"):
            cls = os.path.basename(p).replace(".bbclass", "")
            trace_upward(root, cls, reverse_inherit, 1, set())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Yocto target reverse inheritance tracer")
    parser.add_argument("root", help="Yocto layers root")
    parser.add_argument("--target", required=True)

    args = parser.parse_args()
    search_target(args.root, args.target)
