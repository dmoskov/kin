#!/usr/bin/env python3
"""Analyze the web/js/ classic-script modules to plan an ES-module conversion.

Builds a symbol -> defining-file map for top-level definitions, then for each
file finds which *other* files' symbols it references. Also classifies the
shared mutable globals (top-level let reassigned across files). Output informs
the import wiring + state-module design for Phase 2.
"""

import re
from pathlib import Path

JS_DIR = Path(__file__).resolve().parent.parent / "web" / "js"
files = sorted(p for p in JS_DIR.glob("*.js") if p.name != "99-main.js")

# Browser/library globals that are NOT defined in our files.
EXTERNAL = {
    "window",
    "document",
    "console",
    "localStorage",
    "sessionStorage",
    "fetch",
    "setTimeout",
    "setInterval",
    "clearInterval",
    "clearTimeout",
    "Promise",
    "Math",
    "JSON",
    "Object",
    "Array",
    "Set",
    "Map",
    "Date",
    "String",
    "Number",
    "Boolean",
    "parseInt",
    "parseFloat",
    "isNaN",
    "RegExp",
    "Error",
    "alert",
    "confirm",
    "prompt",
    "navigator",
    "location",
    "history",
    "URL",
    "URLSearchParams",
    "FormData",
    "Blob",
    "FileReader",
    "Image",
    "atob",
    "btoa",
    "requestAnimationFrame",
    "encodeURIComponent",
    "decodeURIComponent",
    "d3",
    "L",
    "google",
    "structuredClone",
    "CustomEvent",
    "Event",
}

def_re = re.compile(r"^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)", re.M)
var_re = re.compile(r"^(?:const|let|var)\s+([A-Za-z_$][\w$]*)", re.M)
let_re = re.compile(r"^let\s+([A-Za-z_$][\w$]*)", re.M)

sym_to_file = {}
defs_by_file = {}
lets_by_file = {}
text_by_file = {}

for f in files:
    txt = f.read_text()
    text_by_file[f.name] = txt
    fns = set(def_re.findall(txt))
    vrs = set(var_re.findall(txt))
    lets = set(let_re.findall(txt))
    defs = fns | vrs
    defs_by_file[f.name] = defs
    lets_by_file[f.name] = lets
    for s in defs:
        sym_to_file.setdefault(s, []).append(f.name)

# Detect duplicate top-level symbols (would collide as ESM exports).
dupes = {s: fl for s, fl in sym_to_file.items() if len(fl) > 1}

# For each file, find references to symbols defined in OTHER files.
imports = {}
for f in files:
    txt = text_by_file[f.name]
    needed = {}
    for sym, deffiles in sym_to_file.items():
        if f.name in deffiles:
            continue  # defined locally
        if re.search(r"(?<![\w$.])" + re.escape(sym) + r"(?![\w$])", txt):
            # pick first defining file
            src = deffiles[0]
            needed.setdefault(src, set()).add(sym)
    imports[f.name] = needed

# Shared mutable globals: top-level `let` that is assigned (X = ) in a file
# OTHER than where it's declared.
cross_writes = {}
for sym, deffiles in sym_to_file.items():
    # only consider symbols declared with let somewhere
    declfile = None
    for fn in files:
        if sym in lets_by_file[fn.name]:
            declfile = fn.name
            break
    if not declfile:
        continue
    writers = set()
    assign_re = re.compile(r"(?<![\w$.])" + re.escape(sym) + r"\s*=(?!=)")
    for fn in files:
        if assign_re.search(text_by_file[fn.name]):
            writers.add(fn.name)
    if len(writers) > 1 or (writers and declfile not in writers):
        cross_writes[sym] = sorted(writers)

print("=== Files:", len(files))
print("=== Total top-level symbols:", len(sym_to_file))
print("\n=== Duplicate top-level symbols (collide as exports):")
for s, fl in sorted(dupes.items()):
    print(f"  {s}: {fl}")
if not dupes:
    print("  (none)")

print("\n=== Import edges per file (symbols needed from other files):")
total_edges = 0
for f in files:
    cnt = sum(len(v) for v in imports[f.name].values())
    total_edges += cnt
    print(f"  {f.name}: {cnt} symbols from {len(imports[f.name])} files")
print(f"  TOTAL import symbol-edges: {total_edges}")

print("\n=== Shared mutable globals written from multiple files (need state obj/setters):")
for s, w in sorted(cross_writes.items()):
    print(f"  {s}: written in {w}")
print(f"  count: {len(cross_writes)}")
