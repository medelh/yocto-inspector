#!/usr/bin/env python3

import os
import re
import argparse
from collections import defaultdict

PROVIDES_RE = re.compile(r'^\s*(R?PROVIDES)(?::\w+)?\s*([+]?=)\s*"([^"]+)"')
INHERIT_RE = re.compile(r'^\s*inherit\s+(.+)')
REQUIRE_RE = re.compile(r'^\s*require\s+(.+)')
INCLUDE_RE = re.compile(r'^\s*include\s+(.+)')


def find_files(root, suffixes):
    for base, _, files in os.walk(root):
        for f in files:
            if any(f.endswith(s) for s in suffixes):
                yield os.path.join(base, f)


def resolve_path(file_path, include_path, root):
    """Resolve a require/include path relative to the including file and root."""
    candidates = []
    
    # 1. Relative to the file that includes it
    file_dir = os.path.dirname(file_path)
    candidates.append(os.path.join(file_dir, include_path))
    
    # 2. Relative to root
    candidates.append(os.path.join(root, include_path))
    
    # 3. Try with .inc extension if not already present
    if not include_path.endswith('.inc'):
        candidates.append(os.path.join(file_dir, include_path + '.inc'))
        candidates.append(os.path.join(root, include_path + '.inc'))
    
    # Return first existing candidate
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    
    return None


def parse_file_recursive(path, root, visited_files=None, depth=0):
    """Recursively parse a file and all its requires/includes to extract provides and inherits."""
    if visited_files is None:
        visited_files = set()
    
    # Prevent infinite loops
    if path in visited_files or depth > 20:
        return [], []
    
    visited_files.add(path)
    
    provides = []
    inherits = []
    
    try:
        with open(path, "r", errors="ignore") as f:
            for line in f:
                # Parse PROVIDES
                m = PROVIDES_RE.match(line)
                if m:
                    provides += m.group(3).split()
                
                # Parse inherit
                m = INHERIT_RE.match(line)
                if m:
                    inherits += m.group(1).split()
                
                # Parse require
                m = REQUIRE_RE.match(line)
                if m:
                    req_path = m.group(1).strip()
                    resolved = resolve_path(path, req_path, root)
                    if resolved:
                        sub_provides, sub_inherits = parse_file_recursive(resolved, root, visited_files, depth + 1)
                        provides += sub_provides
                        inherits += sub_inherits
                
                # Parse include (optional, doesn't fail if missing)
                m = INCLUDE_RE.match(line)
                if m:
                    inc_path = m.group(1).strip()
                    resolved = resolve_path(path, inc_path, root)
                    if resolved:
                        sub_provides, sub_inherits = parse_file_recursive(resolved, root, visited_files, depth + 1)
                        provides += sub_provides
                        inherits += sub_inherits
    except IOError:
        pass
    
    return provides, inherits


def build_indexes(root):
    """Build provides and reverse inherit indexes, including transitive resolution."""
    provides_index = defaultdict(list)
    reverse_inherit = defaultdict(list)
    
    # Process all recipe and class files
    for f in find_files(root, [".bb", ".bbclass", ".bbappend", "inc"]):
        provides, inherits = parse_file_recursive(f, root)
        
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
