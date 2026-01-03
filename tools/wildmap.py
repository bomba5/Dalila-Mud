#!/usr/bin/env python3
import argparse
import collections
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WILD_DIR = os.path.join(ROOT, "lib", "world", "wild")
ZON_DIR = os.path.join(ROOT, "lib", "world", "zon")


def read_text(path):
    # Many world files are Latin-1; avoid decode errors.
    with open(path, "r", encoding="latin-1") as f:
        return f.read()


def parse_wild_table():
    path = os.path.join(WILD_DIR, "wild_table")
    lines = read_text(path).splitlines()
    i = 0
    ids = {}
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line == "$":
            break
        if not line.startswith("#"):
            i += 1
            continue
        try:
            wild_id = int(line[1:])
        except ValueError:
            raise SystemExit(f"Invalid wild id line: {line!r}")
        i += 1
        # Name (fread_string style)
        name_lines = []
        while i < len(lines):
            name_lines.append(lines[i])
            if lines[i].rstrip().endswith("~"):
                name_lines[-1] = name_lines[-1].rstrip()[:-1]
                i += 1
                break
            i += 1
        # Description
        desc_lines = []
        while i < len(lines):
            desc_lines.append(lines[i])
            if lines[i].rstrip().endswith("~"):
                desc_lines[-1] = desc_lines[-1].rstrip()[:-1]
                i += 1
                break
            i += 1
        if i >= len(lines):
            break
        sym_line = lines[i].strip()
        i += 1
        if not sym_line:
            raise SystemExit(f"Missing symbol line for wild id {wild_id}")
        symbol = sym_line.split()[0]
        if len(symbol) != 1:
            # Take first non-space char to be safe.
            symbol = symbol[0]
        ids[wild_id] = {
            "symbol": symbol,
            "name": "\n".join(name_lines).strip(),
        }
    if not ids:
        raise SystemExit("No wild_table entries found")
    return ids


def parse_zone_wilderness(zone):
    zon_path = os.path.join(ZON_DIR, f"{zone}.zon")
    if not os.path.exists(zon_path):
        raise SystemExit(f"Zone file not found: {zon_path}")
    lines = read_text(zon_path).splitlines()
    if len(lines) < 3:
        raise SystemExit(f"Zone file too short: {zon_path}")
    header = lines[2].strip()
    parts = header.split()
    if len(parts) < 3:
        raise SystemExit(f"Invalid zone header line: {header!r}")
    if len(parts) == 3:
        wilderness = 0
    elif len(parts) == 4:
        wilderness = int(parts[3])
    else:
        wilderness = int(parts[4])
    return wilderness


def map_dims_for_zone(zone):
    wilderness = parse_zone_wilderness(zone)
    if wilderness == 1:
        return (200, 200)
    if wilderness == 2:
        return (25, 17)
    raise SystemExit(f"Zone {zone} is not wilderness/miniwild (wilderness={wilderness})")


def read_map_ids(zone):
    map_path = os.path.join(WILD_DIR, f"{zone}.map")
    if not os.path.exists(map_path):
        raise SystemExit(f"Map file not found: {map_path}")
    width, height = map_dims_for_zone(zone)
    grid = []
    with open(map_path, "r", encoding="ascii") as f:
        for line in f:
            if not line.strip():
                continue
            row = [int(x) for x in line.strip().split()]
            grid.append(row)
    if len(grid) != height or any(len(r) != width for r in grid):
        raise SystemExit(
            f"Map {zone}.map has wrong size: "
            f"{len(grid)}x{len(grid[0]) if grid else 0}, expected {width}x{height}"
        )
    return grid


def write_map_ids(zone, grid):
    map_path = os.path.join(WILD_DIR, f"{zone}.map")
    with open(map_path, "w", encoding="ascii") as f:
        for row in grid:
            f.write(" ".join(str(v) for v in row) + "\n")


def build_symbol_maps(wild_table, grid):
    id_to_symbol = {k: v["symbol"] for k, v in wild_table.items()}
    symbol_ids = collections.defaultdict(set)
    symbol_entries = collections.defaultdict(list)
    for wild_id, meta in wild_table.items():
        symbol = meta["symbol"]
        symbol_ids[symbol].add(wild_id)
        symbol_entries[symbol].append((wild_id, meta["name"]))

    # For this map, pick the most common id per symbol.
    counts = collections.Counter()
    for row in grid:
        for wild_id in row:
            symbol = id_to_symbol.get(wild_id)
            if symbol is not None:
                counts[(symbol, wild_id)] += 1
    preferred = {}
    for (symbol, wild_id), count in counts.items():
        if symbol not in preferred or count > preferred[symbol][1]:
            preferred[symbol] = (wild_id, count)
    symbol_to_id = {sym: wid for sym, (wid, _cnt) in preferred.items()}
    return id_to_symbol, symbol_ids, symbol_entries, symbol_to_id


def export_symbols(zone, out_path):
    wild_table = parse_wild_table()
    grid = read_map_ids(zone)
    id_to_symbol, symbol_ids, symbol_entries, symbol_to_id = build_symbol_maps(wild_table, grid)

    width, height = map_dims_for_zone(zone)
    lines = []
    for y in range(height):
        row = grid[y]
        line = "".join(id_to_symbol.get(v, "?") for v in row)
        lines.append(line)
    with open(out_path, "w", encoding="ascii") as f:
        f.write("\n".join(lines) + "\n")

    # Emit a legend to stderr for quick reference.
    sys.stderr.write("Symbol legend (symbol -> ids used in wild_table):\n")
    for sym in sorted(symbol_ids.keys()):
        ids = sorted(symbol_ids[sym])
        default = symbol_to_id.get(sym)
        marker = f" (default {default})" if default is not None else ""
        sys.stderr.write(f"  {sym} -> {ids}{marker}\n")


def import_symbols(zone, in_path, symbol_map_path=None):
    wild_table = parse_wild_table()
    grid = read_map_ids(zone)
    id_to_symbol, symbol_ids, symbol_entries, symbol_to_id = build_symbol_maps(wild_table, grid)

    # Load user overrides if provided.
    if symbol_map_path:
        overrides = {}
        for line in read_text(symbol_map_path).splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) != 2:
                raise SystemExit(f"Invalid symbol map line: {line!r}")
            sym, wid = parts[0], int(parts[1])
            overrides[sym] = wid
        symbol_to_id.update(overrides)

    width, height = map_dims_for_zone(zone)
    with open(in_path, "r", encoding="ascii") as f:
        lines = [line.rstrip("\n") for line in f if line.strip()]
    if len(lines) != height or any(len(line) != width for line in lines):
        raise SystemExit(
            f"Symbol map has wrong size: "
            f"{len(lines)}x{len(lines[0]) if lines else 0}, expected {width}x{height}"
        )

    new_grid = []
    for y in range(height):
        row = []
        for x, sym in enumerate(lines[y]):
            if sym in symbol_to_id:
                row.append(symbol_to_id[sym])
                continue
            ids = sorted(symbol_ids.get(sym, []))
            if len(ids) == 1:
                row.append(ids[0])
                continue
            if len(ids) == 0:
                raise SystemExit(f"Unknown symbol '{sym}' at {x},{y}.")
            entries = sorted(symbol_entries.get(sym, []))
            preview = ", ".join(f"{wid}:{name}" for wid, name in entries)
            raise SystemExit(
                f"Ambiguous symbol '{sym}' at {x},{y}. "
                f"Candidates: {preview}. "
                f"Provide a symbol map with a preferred id."
            )
        new_grid.append(row)
    write_map_ids(zone, new_grid)


def main():
    parser = argparse.ArgumentParser(
        description="Edit wilderness/miniwild maps using ASCII symbols."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    exp = sub.add_parser("export", help="Export a map to ASCII symbols.")
    exp.add_argument("zone", type=int, help="Zone number (e.g. 21200).")
    exp.add_argument("--out", required=True, help="Output ASCII map file path.")

    imp = sub.add_parser("import", help="Import ASCII symbols into a map.")
    imp.add_argument("zone", type=int, help="Zone number (e.g. 21200).")
    imp.add_argument("--in", dest="in_path", required=True, help="Input ASCII map file path.")
    imp.add_argument(
        "--symbol-map",
        dest="symbol_map_path",
        help="Optional symbol->id overrides file.",
    )

    args = parser.parse_args()

    if args.cmd == "export":
        export_symbols(args.zone, args.out)
        return
    if args.cmd == "import":
        import_symbols(args.zone, args.in_path, args.symbol_map_path)
        return


if __name__ == "__main__":
    main()
