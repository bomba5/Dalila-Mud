#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WILD_DIR = os.path.join(ROOT, "lib", "world", "wild")
ZON_DIR = os.path.join(ROOT, "lib", "world", "zon")
WLD_DIR = os.path.join(ROOT, "lib", "world", "wld")
MOB_DIR = os.path.join(ROOT, "lib", "world", "mob")
OBJ_DIR = os.path.join(ROOT, "lib", "world", "obj")

ROOM_INDEX = None
ZONE_INDEX = None
MOB_INDEX = None
OBJ_INDEX = None


def read_text(path):
    with open(path, "r", encoding="latin-1") as f:
        return f.read()


def parse_wild_table():
    path = os.path.join(WILD_DIR, "wild_table")
    lines = read_text(path).splitlines()
    i = 0
    entries = []
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
        name_lines = []
        while i < len(lines):
            name_lines.append(lines[i])
            if lines[i].rstrip().endswith("~"):
                name_lines[-1] = name_lines[-1].rstrip()[:-1]
                i += 1
                break
            i += 1
        # description (skip)
        while i < len(lines):
            if lines[i].rstrip().endswith("~"):
                i += 1
                break
            i += 1
        if i >= len(lines):
            break
        sym_line = lines[i].strip()
        i += 1
        if not sym_line:
            continue
        sym_parts = sym_line.split()
        symbol = sym_parts[0]
        if len(symbol) != 1:
            symbol = symbol[0]
        color = 0
        if len(sym_parts) >= 2:
            try:
                color = int(sym_parts[1])
            except ValueError:
                color = 0
        entries.append({
            "id": wild_id,
            "symbol": symbol,
            "name": " ".join(name_lines).strip(),
            "color": color,
        })
    if not entries:
        raise SystemExit("No wild_table entries found")
    return entries


def parse_zone_file(path):
    lines = read_text(path).splitlines()
    if len(lines) < 3:
        return None
    m = re.match(r"^#(\d+)", lines[0].strip())
    if not m:
        return None
    number = int(m.group(1))
    name_line = lines[1].strip()
    name = name_line[:-1] if name_line.endswith("~") else name_line
    header = lines[2].strip()
    parts = header.split()
    if len(parts) < 3:
        return None
    if len(parts) == 3:
        top = int(parts[0])
        bottom = number * 100
        wilderness = 0
    elif len(parts) == 4:
        top = int(parts[0])
        bottom = number * 100
        wilderness = int(parts[3])
    else:
        bottom = int(parts[0])
        top = int(parts[1])
        wilderness = int(parts[4])
    return {"number": number, "name": name, "wilderness": wilderness, "bottom": bottom, "top": top}


def build_zone_index():
    zones = []
    for name in os.listdir(ZON_DIR):
        if not name.endswith(".zon"):
            continue
        info = parse_zone_file(os.path.join(ZON_DIR, name))
        if info:
            info["path"] = os.path.join(ZON_DIR, name)
            zones.append(info)
    zones.sort(key=lambda z: z["number"])
    return zones


def find_zone_for_vnum(vnum):
    global ZONE_INDEX
    if ZONE_INDEX is None:
        ZONE_INDEX = build_zone_index()
    for zone in ZONE_INDEX:
        if zone["bottom"] <= vnum <= zone["top"]:
            return zone
    return None


def search_zones(query, limit=50):
    if not query:
        return []
    q = query.lower()
    zones = build_zone_index()
    results = []
    for z in zones:
        if q in str(z["number"]).lower() or q in (z["name"] or "").lower():
            results.append({
                "number": z["number"],
                "name": z["name"],
                "wilderness": z["wilderness"],
            })
            if len(results) >= limit:
                break
    return results


def zone_first_room(zone_num):
    info = parse_zone_file(os.path.join(ZON_DIR, f"{zone_num}.zon"))
    if not info:
        return None, "Zone not found."
    if info["wilderness"] != 0:
        return None, "Zone is wilderness."
    rooms = load_zone_rooms(zone_num)
    if not rooms:
        return None, "No rooms found in zone."
    return min(rooms.keys()), None


def map_dims_for_zone(zone):
    zon_path = os.path.join(ZON_DIR, f"{zone}.zon")
    info = parse_zone_file(zon_path)
    if not info:
        raise ValueError(f"Zone {zone} not found")
    if info["wilderness"] == 1:
        return info, 200, 200, 400, 400
    if info["wilderness"] == 2:
        return info, 25, 17, 40, 40
    raise ValueError(f"Zone {zone} is not wilderness/miniwild")


def read_map_ids(zone):
    map_path = os.path.join(WILD_DIR, f"{zone}.map")
    if not os.path.exists(map_path):
        raise ValueError(f"Map file not found: {map_path}")
    info, width, height, xoff, yoff = map_dims_for_zone(zone)
    grid = []
    with open(map_path, "r", encoding="ascii") as f:
        for line in f:
            if not line.strip():
                continue
            grid.append([int(x) for x in line.strip().split()])
    if len(grid) != height or any(len(r) != width for r in grid):
        raise ValueError(
            f"Map {zone}.map has wrong size: "
            f"{len(grid)}x{len(grid[0]) if grid else 0}, expected {width}x{height}"
        )
    return info, width, height, xoff, yoff, grid


def write_map_ids(zone, grid):
    map_path = os.path.join(WILD_DIR, f"{zone}.map")
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup_path = f"{map_path}.bak-{timestamp}"
    if os.path.exists(map_path):
        shutil.copy2(map_path, backup_path)
    with open(map_path, "w", encoding="ascii") as f:
        for row in grid:
            f.write(" ".join(str(v) for v in row) + "\n")
    return backup_path


def _room_vnum_from_cell(zone, x, y, xoff, yoff, wilderness):
    vx = xoff + x
    vy = yoff + y
    if wilderness == 1:
        return 1000000 + (vy * 1000) + vx
    return (zone * 100) + (vy * 100) + vx


def parse_wild_table_full():
    path = os.path.join(WILD_DIR, "wild_table")
    lines = read_text(path).splitlines()
    i = 0
    entries = {}
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
        name_lines = []
        while i < len(lines):
            name_lines.append(lines[i])
            if lines[i].rstrip().endswith("~"):
                name_lines[-1] = name_lines[-1].rstrip()[:-1]
                i += 1
                break
            i += 1
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
        symbol = sym_line.split()[0] if sym_line else "?"
        # move/alt/can_enter line
        if i < len(lines):
            i += 1
        # sector_type/room_flags line
        sector_type = 0
        room_flags = 0
        if i < len(lines):
            parts = lines[i].strip().split()
            if len(parts) >= 2:
                sector_type = int(parts[0])
                room_flags = int(parts[1])
            i += 1
        entries[wild_id] = {
            "name": " ".join(name_lines).strip(),
            "description": "\n".join(desc_lines).strip(),
            "symbol": symbol[0],
            "sector_type": sector_type,
            "room_flags": room_flags,
        }
    if not entries:
        raise SystemExit("No wild_table entries found")
    return entries


def split_wld_blocks(lines):
    starts = []
    for idx, line in enumerate(lines):
        if line.startswith("#") and line[1:].strip().isdigit():
            starts.append(idx)
    blocks = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(lines)
        blocks.append((start, end))
    return blocks


def split_vnum_blocks(lines):
    return split_wld_blocks(lines)


def parse_exit_list(lines):
    exits = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("D") and len(line) > 1 and line[1].isdigit():
            dir_num = int(line[1])
            if i + 3 < len(lines):
                to_line = lines[i + 3].strip()
                parts = to_line.split()
                if len(parts) >= 3:
                    try:
                        to_vnum = int(parts[2])
                        exits.append({"dir": dir_num, "to_vnum": to_vnum})
                    except ValueError:
                        pass
            i += 4
            continue
        i += 1
    return exits


def read_tilde_string(lines, idx):
    parts = []
    while idx < len(lines):
        line = lines[idx]
        if line.rstrip().endswith("~"):
            parts.append(line.rstrip()[:-1])
            idx += 1
            break
        parts.append(line)
        idx += 1
    return "\n".join(parts), idx


def write_tilde_string(value):
    if value is None:
        value = ""
    text = str(value)
    parts = text.splitlines()
    if not parts:
        return ["~"]
    parts[-1] = f"{parts[-1]}~"
    return parts


def parse_entity_block(block_lines, count=4):
    idx = 0
    fields = []
    for _ in range(count):
        if idx >= len(block_lines):
            raise ValueError("Missing required string field.")
        val, idx = read_tilde_string(block_lines, idx)
        fields.append(val)
    raw = block_lines[idx:]
    return fields, raw


def _parse_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_int_list(parts, min_len=None, max_len=None):
    values = []
    for p in parts:
        try:
            values.append(int(p))
        except ValueError:
            break
    if min_len is not None and len(values) < min_len:
        raise ValueError("Not enough numeric values.")
    if max_len is not None and len(values) > max_len:
        values = values[:max_len]
    return values


def parse_mob_block(block_lines):
    idx = 0
    strings = {}
    strings["keywords"], idx = read_tilde_string(block_lines, idx)
    strings["short"], idx = read_tilde_string(block_lines, idx)
    strings["long"], idx = read_tilde_string(block_lines, idx)
    strings["description"], idx = read_tilde_string(block_lines, idx)
    unused = []
    for _ in range(3):
        val, idx = read_tilde_string(block_lines, idx)
        unused.append(val)
    if idx >= len(block_lines):
        raise ValueError("Missing mob header line.")
    header = block_lines[idx].strip()
    idx += 1
    parts = header.split()
    if len(parts) < 9:
        raise ValueError("Invalid mob header line.")
    flags = {
        "act_flags": parts[0],
        "aff_flags": parts[1],
        "alignment": _parse_int(parts[2]),
        "reserved1": _parse_int(parts[3]),
        "reserved2": _parse_int(parts[4]),
        "reserved3": _parse_int(parts[5]),
        "master_id": _parse_int(parts[6]),
        "clan_id": _parse_int(parts[7]),
        "type": parts[8][0] if parts[8] else "S",
    }
    if idx + 2 >= len(block_lines):
        raise ValueError("Missing mob stats lines.")
    line1 = block_lines[idx].strip()
    idx += 1
    m = re.match(
        r"^\s*(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)d(-?\d+)\+(-?\d+)\s+(-?\d+)d(-?\d+)\+(-?\d+)\s*$",
        line1,
    )
    if not m:
        raise ValueError("Invalid mob stats line.")
    stats = {
        "level": _parse_int(m.group(1)),
        "thac0": _parse_int(m.group(2)),
        "armor": _parse_int(m.group(3)),
        "hp_num": _parse_int(m.group(4)),
        "hp_size": _parse_int(m.group(5)),
        "hp_bonus": _parse_int(m.group(6)),
        "dam_num": _parse_int(m.group(7)),
        "dam_size": _parse_int(m.group(8)),
        "dam_bonus": _parse_int(m.group(9)),
    }
    line2 = block_lines[idx].strip()
    idx += 1
    parts = _parse_int_list(line2.split(), min_len=2, max_len=2)
    stats["gold"] = parts[0]
    stats["exp"] = parts[1]
    line3 = block_lines[idx].strip()
    idx += 1
    parts = _parse_int_list(line3.split(), min_len=3, max_len=3)
    stats["position"] = parts[0]
    stats["default_position"] = parts[1]
    stats["sex"] = parts[2]
    especs = []
    if flags["type"].upper() == "E":
        while idx < len(block_lines):
            line = block_lines[idx].rstrip()
            idx += 1
            if line == "E":
                break
            if ":" in line:
                key, value = line.split(":", 1)
                especs.append({"key": key.strip(), "value": value.strip()})
            else:
                especs.append({"key": line.strip(), "value": ""})
    triggers = []
    unknown_lines = []
    while idx < len(block_lines):
        line = block_lines[idx].strip()
        idx += 1
        if not line:
            continue
        if line.startswith("T "):
            parts = line.split()
            if len(parts) >= 2:
                triggers.append(_parse_int(parts[1]))
            else:
                unknown_lines.append(line)
            continue
        unknown_lines.append(line)
    return {
        "strings": strings,
        "unused_strings": unused,
        "flags": flags,
        "stats": stats,
        "especs": especs,
        "triggers": triggers,
        "unknown_lines": unknown_lines,
    }


def serialize_mob_block(data):
    strings = data.get("strings", {})
    unused = data.get("unused_strings", [])
    flags = data.get("flags", {})
    stats = data.get("stats", {})
    lines = []
    lines += write_tilde_string(strings.get("keywords", ""))
    lines += write_tilde_string(strings.get("short", ""))
    lines += write_tilde_string(strings.get("long", ""))
    lines += write_tilde_string(strings.get("description", ""))
    for i in range(3):
        value = unused[i] if i < len(unused) else ""
        lines += write_tilde_string(value)
    act_flags = flags.get("act_flags", "0")
    aff_flags = flags.get("aff_flags", "0")
    alignment = _parse_int(flags.get("alignment", 0))
    reserved1 = _parse_int(flags.get("reserved1", 0))
    reserved2 = _parse_int(flags.get("reserved2", 0))
    reserved3 = _parse_int(flags.get("reserved3", 0))
    master_id = _parse_int(flags.get("master_id", -1))
    clan_id = _parse_int(flags.get("clan_id", -1))
    mob_type = (flags.get("type", "S") or "S").upper()[0]
    lines.append(
        f"{act_flags} {aff_flags} {alignment} {reserved1} {reserved2} {reserved3} {master_id} {clan_id} {mob_type}"
    )
    level = _parse_int(stats.get("level", 1))
    thac0 = _parse_int(stats.get("thac0", 20))
    armor = _parse_int(stats.get("armor", 0))
    hp_num = _parse_int(stats.get("hp_num", 1))
    hp_size = _parse_int(stats.get("hp_size", 1))
    hp_bonus = _parse_int(stats.get("hp_bonus", 0))
    dam_num = _parse_int(stats.get("dam_num", 1))
    dam_size = _parse_int(stats.get("dam_size", 1))
    dam_bonus = _parse_int(stats.get("dam_bonus", 0))
    lines.append(
        f"{level} {thac0} {armor} {hp_num}d{hp_size}+{hp_bonus} {dam_num}d{dam_size}+{dam_bonus}"
    )
    gold = _parse_int(stats.get("gold", 0))
    exp = _parse_int(stats.get("exp", 0))
    lines.append(f"{gold} {exp}")
    position = _parse_int(stats.get("position", 0))
    default_position = _parse_int(stats.get("default_position", 0))
    sex = _parse_int(stats.get("sex", 0))
    lines.append(f"{position} {default_position} {sex}")
    if mob_type == "E":
        for espec in data.get("especs", []):
            key = str(espec.get("key", "")).strip()
            value = str(espec.get("value", "")).strip()
            if not key and not value:
                continue
            if value:
                lines.append(f"{key}: {value}")
            else:
                lines.append(f"{key}:")
        lines.append("E")
    for trig in data.get("triggers", []):
        lines.append(f"T {_parse_int(trig, 0)}")
    for line in data.get("unknown_lines", []):
        if line:
            lines.append(str(line))
    return lines


def parse_obj_block(block_lines):
    idx = 0
    strings = {}
    strings["keywords"], idx = read_tilde_string(block_lines, idx)
    strings["short"], idx = read_tilde_string(block_lines, idx)
    strings["description"], idx = read_tilde_string(block_lines, idx)
    strings["action"], idx = read_tilde_string(block_lines, idx)
    if idx >= len(block_lines):
        raise ValueError("Missing object header line.")
    line1 = block_lines[idx].strip()
    idx += 1
    parts = line1.split()
    if len(parts) < 3:
        raise ValueError("Invalid object header line.")
    flags = {
        "type": _parse_int(parts[0]),
        "extra_flags": parts[1],
        "wear_flags": parts[2],
    }
    if idx >= len(block_lines):
        raise ValueError("Missing object values line.")
    line2 = block_lines[idx].strip()
    idx += 1
    values = _parse_int_list(line2.split(), min_len=4, max_len=6)
    line2_count = len(values)
    while len(values) < 6:
        values.append(0)
    if idx >= len(block_lines):
        raise ValueError("Missing object cost line.")
    line3 = block_lines[idx].strip()
    idx += 1
    costs = _parse_int_list(line3.split(), min_len=3, max_len=6)
    line3_count = len(costs)
    while len(costs) < 6:
        costs.append(0)
    extras = []
    affects = []
    bitvector = None
    triggers = []
    unknown_lines = []
    while idx < len(block_lines):
        line = block_lines[idx].strip()
        idx += 1
        if not line:
            continue
        if line == "E":
            keyword, idx = read_tilde_string(block_lines, idx)
            desc, idx = read_tilde_string(block_lines, idx)
            extras.append({"keyword": keyword, "description": desc})
            continue
        if line == "A":
            if idx >= len(block_lines):
                break
            parts = _parse_int_list(block_lines[idx].split(), min_len=2, max_len=2)
            idx += 1
            affects.append({"location": parts[0], "modifier": parts[1]})
            continue
        if line == "C":
            if idx >= len(block_lines):
                break
            parts = _parse_int_list(block_lines[idx].split(), min_len=4, max_len=4)
            idx += 1
            bitvector = parts
            continue
        if line.startswith("T "):
            parts = line.split()
            if len(parts) >= 2:
                triggers.append(_parse_int(parts[1]))
            else:
                unknown_lines.append(line)
            continue
        unknown_lines.append(line)
    return {
        "strings": strings,
        "flags": flags,
        "values": {
            "value0": values[0],
            "value1": values[1],
            "value2": values[2],
            "value3": values[3],
            "curr_slots": values[4],
            "total_slots": values[5],
            "has_slots": line2_count >= 6,
        },
        "costs": {
            "weight": costs[0],
            "cost": costs[1],
            "cost_per_day": costs[2],
            "min_level": costs[3],
            "material_type": costs[4],
            "material_num": costs[5],
            "has_min_level": line3_count >= 4,
            "has_material": line3_count >= 6,
        },
        "extras": extras,
        "affects": affects,
        "bitvector": bitvector,
        "triggers": triggers,
        "unknown_lines": unknown_lines,
    }


def serialize_obj_block(data):
    strings = data.get("strings", {})
    flags = data.get("flags", {})
    values = data.get("values", {})
    costs = data.get("costs", {})
    lines = []
    lines += write_tilde_string(strings.get("keywords", ""))
    lines += write_tilde_string(strings.get("short", ""))
    lines += write_tilde_string(strings.get("description", ""))
    lines += write_tilde_string(strings.get("action", ""))
    obj_type = _parse_int(flags.get("type", 0))
    extra_flags = flags.get("extra_flags", "0")
    wear_flags = flags.get("wear_flags", "0")
    lines.append(f"{obj_type} {extra_flags} {wear_flags}")
    val_list = [
        _parse_int(values.get("value0", 0)),
        _parse_int(values.get("value1", 0)),
        _parse_int(values.get("value2", 0)),
        _parse_int(values.get("value3", 0)),
    ]
    if values.get("has_slots"):
        val_list.append(_parse_int(values.get("curr_slots", 0)))
        val_list.append(_parse_int(values.get("total_slots", 0)))
    lines.append(" ".join(str(v) for v in val_list))
    cost_list = [
        _parse_int(costs.get("weight", 0)),
        _parse_int(costs.get("cost", 0)),
        _parse_int(costs.get("cost_per_day", 0)),
    ]
    if costs.get("has_min_level") or costs.get("has_material"):
        cost_list.append(_parse_int(costs.get("min_level", -1)))
    if costs.get("has_material"):
        cost_list.append(_parse_int(costs.get("material_type", 0)))
        cost_list.append(_parse_int(costs.get("material_num", 0)))
    lines.append(" ".join(str(v) for v in cost_list))
    for extra in data.get("extras", []):
        lines.append("E")
        lines += write_tilde_string(extra.get("keyword", ""))
        lines += write_tilde_string(extra.get("description", ""))
    for aff in data.get("affects", []):
        lines.append("A")
        loc = _parse_int(aff.get("location", 0))
        mod = _parse_int(aff.get("modifier", 0))
        lines.append(f"{loc} {mod}")
    bitvector = data.get("bitvector", None)
    if bitvector:
        lines.append("C")
        parts = []
        for i in range(4):
            parts.append(str(_parse_int(bitvector[i] if i < len(bitvector) else 0)))
        lines.append(" ".join(parts))
    for trig in data.get("triggers", []):
        lines.append(f"T {_parse_int(trig, 0)}")
    for line in data.get("unknown_lines", []):
        if line:
            lines.append(str(line))
    return lines


def parse_room_block(block_lines):
    idx = 0
    name, idx = read_tilde_string(block_lines, idx)
    desc, idx = read_tilde_string(block_lines, idx)
    if idx >= len(block_lines):
        raise ValueError("Room block missing header line.")
    header = block_lines[idx].strip()
    idx += 1
    parts = header.split()
    if len(parts) < 3:
        raise ValueError("Invalid room header line.")
    zone_num = int(parts[0])
    room_flags = int(parts[1])
    sector_type = int(parts[2])

    exits = []
    extras = []
    other_lines = []
    tail_lines = []

    while idx < len(block_lines):
        line = block_lines[idx].strip()
        if line.startswith("D") and len(line) > 1 and line[1].isdigit():
            dir_num = int(line[1])
            idx += 1
            keyword, idx = read_tilde_string(block_lines, idx)
            edesc, idx = read_tilde_string(block_lines, idx)
            if idx >= len(block_lines):
                raise ValueError("Malformed exit block.")
            nums = block_lines[idx].strip().split()
            idx += 1
            if len(nums) < 4:
                raise ValueError("Malformed exit numbers.")
            exit_info, key, to_room, to_room_key = map(int, nums[:4])
            exits.append({
                "dir": dir_num,
                "keyword": keyword,
                "description": edesc,
                "exit_info": exit_info,
                "key": key,
                "to_room": to_room,
                "to_room_key": to_room_key,
            })
            continue
        if line == "E":
            idx += 1
            keyword, idx = read_tilde_string(block_lines, idx)
            edesc, idx = read_tilde_string(block_lines, idx)
            extras.append({"keyword": keyword, "description": edesc})
            continue
        if line.startswith("S"):
            tail_lines = block_lines[idx + 1 :]
            break
        other_lines.append(block_lines[idx])
        idx += 1

    return {
        "name": name,
        "description": desc,
        "zone": zone_num,
        "room_flags": room_flags,
        "sector_type": sector_type,
        "exits": exits,
        "extras": extras,
        "other_lines": other_lines,
        "tail_lines": tail_lines,
    }


def build_room_block(vnum, data):
    lines = []
    lines.append(f"#{vnum}")
    lines.append(f"{data['name']}~")
    lines.append(f"{data['description']}")
    lines.append("~")
    lines.append(f"{data['zone']} {data['room_flags']} {data['sector_type']}")
    for ex in data["exits"]:
        lines.append(f"D{ex['dir']}")
        lines.append(f"{ex['keyword']}~")
        lines.append(f"{ex['description']}~")
        lines.append(f"{ex['exit_info']} {ex['key']} {ex['to_room']} {ex['to_room_key']}")
    for exd in data["extras"]:
        lines.append("E")
        lines.append(f"{exd['keyword']}~")
        lines.append(f"{exd['description']}~")
    lines.extend(data["other_lines"])
    lines.append("S")
    lines.extend(data["tail_lines"])
    return lines


def build_room_index():
    index = {}
    for base in (WLD_DIR, os.path.join(WILD_DIR)):
        if not os.path.isdir(base):
            continue
        for name in os.listdir(base):
            if not name.endswith(".wld"):
                continue
            path = os.path.join(base, name)
            lines = read_text(path).splitlines()
            blocks = split_wld_blocks(lines)
            for start, end in blocks:
                vnum_line = lines[start].strip()
                if not vnum_line.startswith("#"):
                    continue
                vnum = int(vnum_line[1:])
                index[vnum] = {
                    "path": path,
                    "start": start,
                    "end": end,
                    "lines": lines,
                }
    return index


def build_entity_index(dir_path, ext):
    index = {}
    if not os.path.isdir(dir_path):
        return index
    for name in os.listdir(dir_path):
        if not name.endswith(ext):
            continue
        path = os.path.join(dir_path, name)
        lines = read_text(path).splitlines()
        blocks = split_vnum_blocks(lines)
        for start, end in blocks:
            vnum_line = lines[start].strip()
            if not vnum_line.startswith("#"):
                continue
            vnum = int(vnum_line[1:])
            index[vnum] = {
                "path": path,
                "start": start,
                "end": end,
                "lines": lines,
            }
    return index


def search_mobs(query, limit=50):
    if not query:
        return []
    q = query.lower()
    results = []
    index = build_entity_index(MOB_DIR, ".mob")
    for vnum, entry in index.items():
        block_lines = entry["lines"][entry["start"] + 1 : entry["end"]]
        try:
            data = parse_mob_block(block_lines)
        except Exception:
            continue
        strings = data.get("strings", {})
        fields = [
            strings.get("keywords", ""),
            strings.get("short", ""),
            strings.get("long", ""),
            strings.get("description", ""),
        ]
        if any(q in (f or "").lower() for f in fields):
            results.append({
                "vnum": vnum,
                "name": strings.get("short", "") or strings.get("keywords", ""),
            })
            if len(results) >= limit:
                break
    return results


def search_objects(query, limit=50):
    if not query:
        return []
    q = query.lower()
    results = []
    index = build_entity_index(OBJ_DIR, ".obj")
    for vnum, entry in index.items():
        block_lines = entry["lines"][entry["start"] + 1 : entry["end"]]
        try:
            data = parse_obj_block(block_lines)
        except Exception:
            continue
        strings = data.get("strings", {})
        fields = [
            strings.get("keywords", ""),
            strings.get("short", ""),
            strings.get("description", ""),
            strings.get("action", ""),
        ]
        if any(q in (f or "").lower() for f in fields):
            results.append({
                "vnum": vnum,
                "name": strings.get("short", "") or strings.get("keywords", ""),
            })
            if len(results) >= limit:
                break
    return results


def search_rooms(query, limit=50):
    if not query:
        return []
    q = query.lower()
    results = []
    index = build_room_index()
    for vnum, entry in index.items():
        block_lines = entry["lines"][entry["start"] + 1 : entry["end"]]
        try:
            data = parse_room_block(block_lines)
        except Exception:
            continue
        fields = [
            data.get("name", ""),
            data.get("description", ""),
        ]
        if any(q in (f or "").lower() for f in fields):
            results.append({
                "vnum": vnum,
                "name": data.get("name", ""),
            })
            if len(results) >= limit:
                break
    return results


def load_room_by_vnum(vnum):
    global ROOM_INDEX
    if ROOM_INDEX is None:
        ROOM_INDEX = build_room_index()
    entry = ROOM_INDEX.get(vnum)
    if not entry:
        return None
    block_lines = entry["lines"][entry["start"] + 1 : entry["end"]]
    data = parse_room_block(block_lines)
    data["vnum"] = vnum
    data["path"] = entry["path"]
    return data


def load_mob_by_vnum(vnum):
    global MOB_INDEX
    if MOB_INDEX is None:
        MOB_INDEX = build_entity_index(MOB_DIR, ".mob")
    entry = MOB_INDEX.get(vnum)
    if not entry:
        return None
    block_lines = entry["lines"][entry["start"] + 1 : entry["end"]]
    data = parse_mob_block(block_lines)
    data["vnum"] = vnum
    data["path"] = entry["path"]
    return data


def save_mob_by_vnum(vnum, data):
    global MOB_INDEX
    if MOB_INDEX is None:
        MOB_INDEX = build_entity_index(MOB_DIR, ".mob")
    entry = MOB_INDEX.get(vnum)
    if not entry:
        raise ValueError("VNUM not found in data files.")
    lines = entry["lines"]
    block = [f"#{vnum}"]
    block.extend(serialize_mob_block(data))
    lines[entry["start"] : entry["end"]] = block
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup_path = f"{entry['path']}.bak-{timestamp}"
    shutil.copy2(entry["path"], backup_path)
    with open(entry["path"], "w", encoding="latin-1") as f:
        f.write("\n".join(lines) + "\n")
    MOB_INDEX = None
    return backup_path


def load_obj_by_vnum(vnum):
    global OBJ_INDEX
    if OBJ_INDEX is None:
        OBJ_INDEX = build_entity_index(OBJ_DIR, ".obj")
    entry = OBJ_INDEX.get(vnum)
    if not entry:
        return None
    block_lines = entry["lines"][entry["start"] + 1 : entry["end"]]
    data = parse_obj_block(block_lines)
    data["vnum"] = vnum
    data["path"] = entry["path"]
    return data


def save_obj_by_vnum(vnum, data):
    global OBJ_INDEX
    if OBJ_INDEX is None:
        OBJ_INDEX = build_entity_index(OBJ_DIR, ".obj")
    entry = OBJ_INDEX.get(vnum)
    if not entry:
        raise ValueError("VNUM not found in data files.")
    lines = entry["lines"]
    block = [f"#{vnum}"]
    block.extend(serialize_obj_block(data))
    lines[entry["start"] : entry["end"]] = block
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup_path = f"{entry['path']}.bak-{timestamp}"
    shutil.copy2(entry["path"], backup_path)
    with open(entry["path"], "w", encoding="latin-1") as f:
        f.write("\n".join(lines) + "\n")
    OBJ_INDEX = None
    return backup_path


def load_zone_rooms(zone_num):
    rooms = {}
    for base in (WLD_DIR,):
        if not os.path.isdir(base):
            continue
        for name in os.listdir(base):
            if not name.endswith(".wld"):
                continue
            path = os.path.join(base, name)
            lines = read_text(path).splitlines()
            blocks = split_wld_blocks(lines)
            for start, end in blocks:
                vnum_line = lines[start].strip()
                if not vnum_line.startswith("#"):
                    continue
                vnum = int(vnum_line[1:])
                block_lines = lines[start + 1 : end]
                try:
                    data = parse_room_block(block_lines)
                except Exception:
                    continue
                if data["zone"] != zone_num:
                    continue
                rooms[vnum] = data
    return rooms


def build_zone_grid(zone_num):
    rooms = load_zone_rooms(zone_num)
    if not rooms:
        return {"rooms": [], "edges": [], "external": [], "min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0}
    coords = {}
    used = set()

    dir_vec = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}

    def bfs(start_vnum, start_x, start_y):
        queue = [start_vnum]
        coords[start_vnum] = (start_x, start_y)
        used.add(start_vnum)
        while queue:
            v = queue.pop(0)
            x, y = coords[v]
            for ex in rooms[v]["exits"]:
                if ex["dir"] not in dir_vec:
                    continue
                to_room = ex["to_room"]
                if to_room not in rooms:
                    continue
                dx, dy = dir_vec[ex["dir"]]
                nx, ny = x + dx, y + dy
                if to_room not in coords:
                    coords[to_room] = (nx, ny)
                    used.add(to_room)
                    queue.append(to_room)

    remaining = sorted(rooms.keys())
    offset_x = 0
    for vnum in remaining:
        if vnum in coords:
            continue
        bfs(vnum, offset_x, 0)
        xs = [c[0] for c in coords.values()]
        if xs:
            offset_x = max(xs) + 3

    xs = [c[0] for c in coords.values()]
    ys = [c[1] for c in coords.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    out = []
    for vnum, (x, y) in coords.items():
        out.append({
            "vnum": vnum,
            "x": x - min_x,
            "y": y - min_y,
            "name": rooms[vnum]["name"],
        })
    edges = []
    external = []
    for vnum, (x, y) in coords.items():
        for ex in rooms[vnum]["exits"]:
            if ex["dir"] not in dir_vec:
                to_room = ex["to_room"]
                if to_room <= 0:
                    continue
                zone = find_zone_for_vnum(to_room)
                external.append({
                    "from_vnum": vnum,
                    "to_vnum": to_room,
                    "x1": x - min_x,
                    "y1": y - min_y,
                    "dir": ex["dir"],
                    "to_zone": zone["number"] if zone else None,
                    "to_zone_name": zone["name"] if zone else "",
                })
                continue
            to_room = ex["to_room"]
            if to_room not in coords:
                if to_room <= 0:
                    continue
                zone = find_zone_for_vnum(to_room)
                external.append({
                    "from_vnum": vnum,
                    "to_vnum": to_room,
                    "x1": x - min_x,
                    "y1": y - min_y,
                    "dir": ex["dir"],
                    "to_zone": zone["number"] if zone else None,
                    "to_zone_name": zone["name"] if zone else "",
                })
                continue
            tx, ty = coords[to_room]
            edges.append({
                "from_vnum": vnum,
                "to_vnum": to_room,
                "x1": x - min_x,
                "y1": y - min_y,
                "x2": tx - min_x,
                "y2": ty - min_y,
                "dir": ex["dir"],
            })
    return {
        "rooms": out,
        "edges": edges,
        "external": external,
        "min_x": min_x,
        "min_y": min_y,
        "max_x": max_x,
        "max_y": max_y,
    }


def save_room_by_vnum(vnum, data):
    global ROOM_INDEX
    if ROOM_INDEX is None:
        ROOM_INDEX = build_room_index()
    entry = ROOM_INDEX.get(vnum)
    if not entry:
        raise ValueError("Room vnum not found in .wld files.")
    path = entry["path"]
    lines = entry["lines"]
    new_block = build_room_block(vnum, data)
    lines[entry["start"] : entry["end"]] = new_block
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup_path = f"{path}.bak-{timestamp}"
    shutil.copy2(path, backup_path)
    with open(path, "w", encoding="latin-1") as f:
        f.write("\n".join(lines) + "\n")
    ROOM_INDEX = None
    return backup_path


def list_room_spawns(vnum):
    zone = find_zone_for_vnum(vnum)
    if not zone:
        return []
    lines = read_text(zone["path"]).splitlines()
    spawns = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("*"):
            continue
        if line.startswith(("M ", "O ")):
            parts = line.split()
            if len(parts) >= 5:
                cmd = parts[0]
                if_flag = int(parts[1])
                arg1 = int(parts[2])
                arg2 = int(parts[3])
                arg3 = int(parts[4])
                if arg3 == vnum:
                    spawns.append({
                        "cmd": cmd,
                        "if_flag": if_flag,
                        "vnum": arg1,
                        "max": arg2,
                    })
    return spawns


def add_room_spawn(vnum, cmd, obj_vnum, max_count):
    zone = find_zone_for_vnum(vnum)
    if not zone:
        raise ValueError("Zone not found for vnum.")
    lines = read_text(zone["path"]).splitlines()
    insert_at = len(lines)
    for i, line in enumerate(lines):
        if line.strip() in ("S", "$"):
            insert_at = i
            break
    if cmd not in ("M", "O"):
        raise ValueError("Only M/O spawns are supported.")
    new_line = f"{cmd} 0 {obj_vnum} {max_count} {vnum}\t(auto)"
    lines.insert(insert_at, new_line)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup_path = f"{zone['path']}.bak-{timestamp}"
    shutil.copy2(zone["path"], backup_path)
    with open(zone["path"], "w", encoding="latin-1") as f:
        f.write("\n".join(lines) + "\n")
    return backup_path


def parse_zone_resets(zone_path):
    lines = read_text(zone_path).splitlines()
    resets = []
    for line in lines:
        raw = line.rstrip("\n")
        line = line.strip()
        if not line or line.startswith("*") or line in ("S", "$"):
            continue
        parts = line.split()
        if not parts:
            continue
        if len(parts[0]) != 1:
            continue
        cmd = parts[0]
        if cmd not in ("M", "O", "E", "G", "P", "D", "R"):
            continue
        if cmd in ("M", "O", "E", "P", "D"):
            if len(parts) >= 5:
                resets.append({
                    "cmd": cmd,
                    "if_flag": int(parts[1]),
                    "arg1": int(parts[2]),
                    "arg2": int(parts[3]),
                    "arg3": int(parts[4]),
                    "raw": raw,
                })
        else:
            if len(parts) >= 4:
                resets.append({
                    "cmd": cmd,
                    "if_flag": int(parts[1]),
                    "arg1": int(parts[2]),
                    "arg2": int(parts[3]),
                    "arg3": None,
                    "raw": raw,
                })
    return resets


def list_room_resets(vnum):
    zone = find_zone_for_vnum(vnum)
    if not zone:
        return []
    resets = parse_zone_resets(zone["path"])
    room_resets = []
    for r in resets:
        if r["cmd"] in ("M", "O") and r["arg3"] == vnum:
            room_resets.append(r)
        elif r["cmd"] == "D" and r["arg1"] == vnum:
            room_resets.append(r)
        elif r["cmd"] == "R" and r["arg2"] == vnum:
            room_resets.append(r)
    return room_resets


def append_zone_reset(vnum, cmd, if_flag, arg1, arg2, arg3, comment):
    zone = find_zone_for_vnum(vnum)
    if not zone:
        raise ValueError("Zone not found for vnum.")
    lines = read_text(zone["path"]).splitlines()
    insert_at = len(lines)
    for i, line in enumerate(lines):
        if line.strip() in ("S", "$"):
            insert_at = i
            break
    cmd = cmd.upper()
    if cmd in ("M", "O", "E", "P", "D"):
        line = f"{cmd} {if_flag} {arg1} {arg2} {arg3}"
    else:
        line = f"{cmd} {if_flag} {arg1} {arg2}"
    if comment:
        line = f"{line}\t({comment})"
    lines.insert(insert_at, line)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup_path = f"{zone['path']}.bak-{timestamp}"
    shutil.copy2(zone["path"], backup_path)
    with open(zone["path"], "w", encoding="latin-1") as f:
        f.write("\n".join(lines) + "\n")
    return backup_path
def load_zone_exits(zone):
    wld_path = os.path.join(WILD_DIR, f"{zone}.wld")
    if not os.path.exists(wld_path):
        return {}
    lines = read_text(wld_path).splitlines()
    blocks = split_wld_blocks(lines)
    exit_map = {}
    for start, end in blocks:
        vnum_line = lines[start].strip()
        if not vnum_line.startswith("#"):
            continue
        vnum = int(vnum_line[1:])
        block_lines = lines[start + 1 : end]
        exits = parse_exit_list(block_lines)
        if exits:
            exit_map[vnum] = exits
    return exit_map


def update_wld_exit(zone, vnum, dir_num, to_vnum, match_to_vnum=None):
    wld_path = os.path.join(WILD_DIR, f"{zone}.wld")
    lines = []
    has_dollar = False
    if os.path.exists(wld_path):
        lines = read_text(wld_path).splitlines()
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip() == "":
                continue
            if lines[i].strip() == "$":
                has_dollar = True
                lines = lines[:i]
            break
    else:
        lines = []
        has_dollar = True

    blocks = split_wld_blocks(lines)
    start = end = None
    for bstart, bend in blocks:
        if lines[bstart].strip() == f"#{vnum}":
            start, end = bstart, bend
            break

    if start is None:
        # Create a minimal room block based on wild_table entry.
        info, width, height, xoff, yoff = map_dims_for_zone(zone)
        grid_info = read_map_ids(zone)[5]
        # derive cell coords
        if info["wilderness"] == 1:
            vy = (vnum - 1000000) // 1000
            vx = (vnum - 1000000) % 1000
        else:
            vy = (vnum - zone * 100) // 100
            vx = (vnum - zone * 100) % 100
        gx = vx - xoff
        gy = vy - yoff
        if not (0 <= gx < width and 0 <= gy < height):
            raise ValueError("VNUM is not within this zone map bounds.")
        wild_id = grid_info[gy][gx]
        wild_table = parse_wild_table_full()
        meta = wild_table.get(wild_id, None)
        if not meta:
            raise ValueError("Unknown wild_table entry for this cell.")
        room_flags = meta["room_flags"]
        sector_type = meta["sector_type"]
        name = meta["name"]
        desc = meta["description"]
        block = [
            f"#{vnum}",
            f"{name}~",
            f"{desc}",
            "~",
            f"{zone} {room_flags} {sector_type}",
            f"D{dir_num}",
            "~",
            "~",
            f"0 0 {to_vnum} 0",
            "S",
        ]
        lines.extend(block)
    else:
        block_lines = lines[start:end]
        # Find existing exit block for dir
        i = 0
        replaced = False
        while i < len(block_lines):
            line = block_lines[i].strip()
            if line.startswith("D") and len(line) > 1 and line[1].isdigit():
                if int(line[1]) == dir_num:
                    if i + 3 >= len(block_lines):
                        raise ValueError("Malformed exit block.")
                    current_to = None
                    parts = block_lines[i + 3].strip().split()
                    if len(parts) >= 3:
                        try:
                            current_to = int(parts[2])
                        except ValueError:
                            current_to = None
                    if to_vnum is None:
                        # remove 4-line block
                        if match_to_vnum is None or current_to == match_to_vnum:
                            del block_lines[i:i+4]
                            replaced = True
                    else:
                        block_lines[i + 3] = f"0 0 {to_vnum} 0"
                        replaced = True
                    break
                i += 4
                continue
            i += 1
        if not replaced and to_vnum is not None:
            # Insert before 'S' line.
            insert_at = len(block_lines)
            for idx, line in enumerate(block_lines):
                if line.strip().startswith("S"):
                    insert_at = idx
                    break
            new_block = [
                f"D{dir_num}",
                "~",
                "~",
                f"0 0 {to_vnum} 0",
            ]
            block_lines[insert_at:insert_at] = new_block
        lines[start:end] = block_lines

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    if os.path.exists(wld_path):
        backup_path = f"{wld_path}.bak-{timestamp}"
        shutil.copy2(wld_path, backup_path)
    else:
        backup_path = ""
    if has_dollar:
        lines.append("$")
    with open(wld_path, "w", encoding="latin-1") as f:
        f.write("\n".join(lines) + "\n")
    return backup_path

HOME_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>World Editor</title>
  <style>
    body { margin: 0; font-family: monospace; background: #101417; color: #e6e6e6; }
    main { max-width: 700px; margin: 80px auto; padding: 20px; }
    .btn { background: #1b2230; color: #e6e6e6; border: 1px solid #2a2f35; padding: 10px 14px; cursor: pointer; display: inline-block; margin-right: 10px; text-decoration: none; }
    .meta { font-size: 12px; opacity: 0.8; margin-top: 12px; }
  </style>
</head>
<body>
  <main>
    <h2>World Editor</h2>
    <div>
      <a class="btn" href="/wild">Edit Wild/Miniwild</a>
      <a class="btn" href="/room">Edit Zone/Rooms</a>
      <a class="btn" href="/mob">Edit Mob</a>
      <a class="btn" href="/obj">Edit Object</a>
    </div>
    <div class="meta">Use the zone editor for non‑wild zones and zone maps.</div>
  </main>
</body>
</html>
"""

HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Wild/Miniwild Editor</title>
  <style>
    body { margin: 0; font-family: monospace; background: #101417; color: #e6e6e6; }
    header { padding: 10px 14px; border-bottom: 1px solid #2a2f35; display: flex; gap: 12px; align-items: center; }
    main { display: grid; grid-template-columns: 320px 1fr 320px; height: calc(100vh - 48px); }
    #map-wrap { overflow: auto; background: #0c0f12; }
    #map { image-rendering: pixelated; display: block; background: #0c0f12; }
    #exits { border-right: 1px solid #2a2f35; padding: 10px; overflow: auto; }
    #palette { border-left: 1px solid #2a2f35; padding: 10px; overflow: auto; }
    .row { display: flex; gap: 10px; align-items: center; }
    .spacer { flex: 1; }
    .btn { background: #1b2230; color: #e6e6e6; border: 1px solid #2a2f35; padding: 6px 10px; cursor: pointer; }
    .btn:disabled { opacity: 0.5; cursor: default; }
    .palette-item { padding: 6px; border: 1px solid #2a2f35; margin-bottom: 6px; cursor: pointer; }
    .palette-item.active { border-color: #7cc7ff; background: #17202a; }
    .meta { font-size: 12px; opacity: 0.8; }
    .status { font-size: 12px; opacity: 0.8; }
    select, input { background: #0f141a; color: #e6e6e6; border: 1px solid #2a2f35; padding: 4px; }
  </style>
</head>
<body>
  <header>
    <div class="row">
      <label>Zone</label>
      <select id="zoneSelect"></select>
      <button id="loadBtn" class="btn">Load</button>
    </div>
    <div class="row">
      <label>Mode</label>
      <button id="modePaint" class="btn">Paint</button>
      <button id="modeQuery" class="btn">Query</button>
      <button id="modeSelect" class="btn">Select</button>
      <button id="selectionApply" class="btn">Fill Selection</button>
      <button id="selectionClear" class="btn">Clear Selection</button>
    </div>
    <div class="row">
      <label>Zoom</label>
      <button id="zoomOut" class="btn">-</button>
      <input id="cellSize" type="number" min="4" max="24" value="10" style="width:60px">
      <button id="zoomIn" class="btn">+</button>
    </div>
    <div class="spacer"></div>
    <div class="status" id="status">Idle</div>
    <a class="btn" href="/help" target="_blank">Help</a>
    <button id="saveBtn" class="btn">Save</button>
  </header>
  <main>
    <aside id="exits">
      <div class="meta" id="cellTitle">Cell (none)</div>
      <div class="meta" id="cellInfo" style="white-space:pre-wrap; background:#0f141a; border:1px solid #2a2f35; padding:6px;">No cell selected.</div>
      <div class="status" id="status">Idle</div>
      <div class="row" style="margin:6px 0;">
        <button id="cellClear" class="btn">Clear Selection</button>
      </div>
      <div class="row" style="margin:6px 0;">
        <select id="exitDir" style="width:90px">
          <option value="0">North</option>
          <option value="1">East</option>
          <option value="2">South</option>
          <option value="3">West</option>
          <option value="4">Up</option>
          <option value="5">Down</option>
        </select>
        <input id="exitTarget" type="number" placeholder="Target vnum" style="width:160px">
      </div>
      <div class="row" style="margin-bottom:8px;">
        <button id="exitSet" class="btn">Set Exit</button>
        <button id="exitDel" class="btn">Remove Exit</button>
      </div>
      <div class="meta">Exits</div>
      <div id="exitList" style="font-size:12px; margin:6px 0;"></div>
    </aside>
    <div id="map-wrap">
      <canvas id="map"></canvas>
    </div>
    <aside id="palette">
      <div class="meta" id="paletteMeta">Palette</div>
      <input id="paletteSearch" type="text" placeholder="Search tiles..." style="width:100%; margin:8px 0;">
      <div id="paletteList"></div>
    </aside>
  </main>
<script>
const state = {
  palette: [],
  paletteById: {},
  selectedId: null,
  zone: null,
  grid: [],
  width: 0,
  height: 0,
  xoff: 0,
  yoff: 0,
  wilderness: 0,
  name: "",
  isDown: false,
  selected: null,
  areaSelection: new Set(),
  entranceCells: new Set(),
};

const zoneSelect = document.getElementById('zoneSelect');
const loadBtn = document.getElementById('loadBtn');
const saveBtn = document.getElementById('saveBtn');
const statusEl = document.getElementById('status');
const cellSizeEl = document.getElementById('cellSize');
const modePaintBtn = document.getElementById('modePaint');
const modeQueryBtn = document.getElementById('modeQuery');
const modeSelectBtn = document.getElementById('modeSelect');
const selectionApplyBtn = document.getElementById('selectionApply');
const selectionClearBtn = document.getElementById('selectionClear');
const zoomInBtn = document.getElementById('zoomIn');
const zoomOutBtn = document.getElementById('zoomOut');
const paletteList = document.getElementById('paletteList');
const paletteMeta = document.getElementById('paletteMeta');
const paletteSearch = document.getElementById('paletteSearch');
const cellTitle = document.getElementById('cellTitle');
const cellInfo = document.getElementById('cellInfo');
const cellClear = document.getElementById('cellClear');
const exitDir = document.getElementById('exitDir');
const exitTarget = document.getElementById('exitTarget');
const exitSet = document.getElementById('exitSet');
const exitDel = document.getElementById('exitDel');
const exitList = document.getElementById('exitList');
const canvas = document.getElementById('map');
const ctx = canvas.getContext('2d');

function setStatus(msg) { statusEl.textContent = msg; }
function setInfo(msg) { cellInfo.textContent = msg; }

function fetchJson(url, opts) {
  return fetch(url, opts).then(r =>
    r.json().then(data => {
      if (!r.ok) throw new Error(data.error || r.statusText);
      return data;
    })
  );
}

function renderPalette() {
  paletteList.innerHTML = '';
  const query = (paletteSearch.value || '').trim().toLowerCase();
  for (const item of state.palette) {
    if (query) {
      const hay = `${item.symbol} ${item.id} ${item.name}`.toLowerCase();
      if (!hay.includes(query)) continue;
    }
    const div = document.createElement('div');
    div.className = 'palette-item' + (item.id === state.selectedId ? ' active' : '');
    const color = colorFromIndex(item.color || 0);
    div.innerHTML = `<span style="color:${color}">${item.symbol}</span>  #${item.id}  ${item.name}`;
    div.addEventListener('click', () => {
      state.selectedId = item.id;
      renderPalette();
    });
    paletteList.appendChild(div);
  }
}

paletteSearch.addEventListener('input', () => {
  renderPalette();
});

function resizeCanvas() {
  const size = parseInt(cellSizeEl.value, 10) || 10;
  canvas.width = state.width * size;
  canvas.height = state.height * size;
  ctx.font = `${Math.max(6, Math.floor(size * 0.8))}px monospace`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
}

function drawGrid() {
  const size = parseInt(cellSizeEl.value, 10) || 10;
  ctx.fillStyle = '#0c0f12';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  for (let y = 0; y < state.height; y++) {
    for (let x = 0; x < state.width; x++) {
      const id = state.grid[y][x];
      const item = state.paletteById[id];
      const sym = item ? item.symbol : '?';
      const cx = x * size + size / 2;
      const cy = y * size + size / 2;
      if (state.selected && state.selected.x === x && state.selected.y === y) {
        ctx.fillStyle = '#1f6b3a';
        ctx.fillRect(x * size, y * size, size, size);
      } else if (state.entranceCells.has(`${x},${y}`)) {
        ctx.fillStyle = 'rgba(80, 160, 255, 0.25)';
        ctx.fillRect(x * size, y * size, size, size);
      }
      if (state.areaSelection.has(`${x},${y}`)) {
        ctx.fillStyle = 'rgba(255, 255, 0, 0.25)';
        ctx.fillRect(x * size, y * size, size, size);
      }
      const color = item ? colorFromIndex(item.color || 0) : '#e6e6e6';
      ctx.fillStyle = color;
      ctx.fillText(sym, cx, cy);
    }
  }
}

function colorFromIndex(idx) {
  const map = {
    1: '#202020',
    2: '#e74c3c',
    3: '#2ecc71',
    4: '#f1c40f',
    5: '#3498db',
    6: '#9b59b6',
    7: '#1abc9c',
    8: '#ecf0f1',
    9: '#ffffff',
    10: '#ffffff',
    11: '#e6e6e6',
    12: '#e6e6e6',
    13: '#95a5a6',
    14: '#000000',
    15: '#ff7675',
    16: '#55efc4',
    17: '#ffeaa7',
    18: '#74b9ff',
    19: '#a29bfe',
    20: '#81ecec',
    21: '#ffffff',
  };
  return map[idx] || '#e6e6e6';
}

function gridPos(evt) {
  const rect = canvas.getBoundingClientRect();
  const size = parseInt(cellSizeEl.value, 10) || 10;
  const x = Math.floor((evt.clientX - rect.left) / size);
  const y = Math.floor((evt.clientY - rect.top) / size);
  if (x < 0 || y < 0 || x >= state.width || y >= state.height) return null;
  return {x, y};
}

function formatCellInfo(pos) {
  const id = state.grid[pos.y][pos.x];
  const item = state.paletteById[id];
  const sym = item ? item.symbol : '?';
  const name = item ? item.name : 'Unknown';
  const vx = state.xoff + pos.x;
  const vy = state.yoff + pos.y;
  let vnum = '';
  if (state.wilderness === 1) {
    vnum = 1000000 + (vy * 1000) + vx;
  } else if (state.wilderness === 2) {
    vnum = (state.zone * 100) + (vy * 100) + vx;
  }
  return {
    vnum: vnum,
    text: `Pos: x=${vx} y=${vy}\nTile: ${sym} #${id} ${name}`
  };
}

function setSelectedCell(pos) {
  state.selected = pos;
  if (!pos) {
    cellTitle.textContent = 'Cell (none)';
    setInfo('No cell selected.');
    loadExitList();
    drawGrid();
    return;
  }
  const info = formatCellInfo(pos);
  cellTitle.textContent = `Cell #${info.vnum}`;
  setInfo(info.text);
  loadExitList();
  drawGrid();
}

function paintAt(evt) {
  if (state.selectedId === null) return;
  const pos = gridPos(evt);
  if (!pos) return;
  state.grid[pos.y][pos.x] = state.selectedId;
  drawGrid();
  const info = formatCellInfo(pos);
  cellTitle.textContent = `Cell #${info.vnum}`;
  setInfo(info.text);
  setSelectedCell(pos);
}

function selectAt(evt) {
  const pos = gridPos(evt);
  if (!pos) return;
  const key = `${pos.x},${pos.y}`;
  if (evt.altKey) {
    state.areaSelection.delete(key);
  } else {
    state.areaSelection.add(key);
  }
  setSelectedCell(pos);
  drawGrid();
}

canvas.addEventListener('mousedown', (evt) => {
  state.isDown = true;
  if (state.mode === 'query') {
    const pos = gridPos(evt);
    if (pos) {
      const info = formatCellInfo(pos);
      cellTitle.textContent = `Cell #${info.vnum}`;
      setInfo(info.text);
      setSelectedCell(pos);
    }
  } else if (state.mode === 'select') {
    selectAt(evt);
  } else {
    paintAt(evt);
  }
});
canvas.addEventListener('mousemove', (evt) => {
  if (state.mode === 'query') return;
  if (!state.isDown) return;
  if (state.mode === 'select') selectAt(evt);
  else paintAt(evt);
});
window.addEventListener('mouseup', () => { state.isDown = false; });

cellSizeEl.addEventListener('change', () => {
  resizeCanvas();
  drawGrid();
  if (state.selected) scrollToCell(state.selected);
});

cellClear.addEventListener('click', () => {
  setSelectedCell(null);
  setStatus('Selection cleared.');
});

function moveSelection(dx, dy) {
  if (!state.selected) {
    setSelectedCell({x: 0, y: 0});
    scrollToCell({x: 0, y: 0});
    const info = formatCellInfo({x: 0, y: 0});
    cellTitle.textContent = `Cell #${info.vnum}`;
    setInfo(info.text);
    return;
  }
  const nx = Math.max(0, Math.min(state.width - 1, state.selected.x + dx));
  const ny = Math.max(0, Math.min(state.height - 1, state.selected.y + dy));
  setSelectedCell({x: nx, y: ny});
  scrollToCell({x: nx, y: ny});
  const info = formatCellInfo({x: nx, y: ny});
  cellTitle.textContent = `Cell #${info.vnum}`;
  setInfo(info.text);
}

window.addEventListener('keydown', (evt) => {
  if (!state.zone) return;
  if (evt.target && (evt.target.tagName === 'INPUT' || evt.target.tagName === 'TEXTAREA' || evt.target.tagName === 'SELECT')) {
    return;
  }
  switch (evt.key) {
    case 'ArrowUp': moveSelection(0, -1); evt.preventDefault(); break;
    case 'ArrowDown': moveSelection(0, 1); evt.preventDefault(); break;
    case 'ArrowLeft': moveSelection(-1, 0); evt.preventDefault(); break;
    case 'ArrowRight': moveSelection(1, 0); evt.preventDefault(); break;
    default: break;
  }
});

zoomInBtn.addEventListener('click', () => {
  const val = Math.min(24, (parseInt(cellSizeEl.value, 10) || 10) + 1);
  cellSizeEl.value = val;
  resizeCanvas();
  drawGrid();
  if (state.selected) scrollToCell(state.selected);
});
zoomOutBtn.addEventListener('click', () => {
  const val = Math.max(4, (parseInt(cellSizeEl.value, 10) || 10) - 1);
  cellSizeEl.value = val;
  resizeCanvas();
  drawGrid();
  if (state.selected) scrollToCell(state.selected);
});

function setMode(mode) {
  state.mode = mode;
  if (mode === 'paint') {
    modePaintBtn.disabled = true;
    modeQueryBtn.disabled = false;
    modeSelectBtn.disabled = false;
  } else if (mode === 'select') {
    modePaintBtn.disabled = false;
    modeQueryBtn.disabled = false;
    modeSelectBtn.disabled = true;
  } else {
    modePaintBtn.disabled = false;
    modeQueryBtn.disabled = true;
    modeSelectBtn.disabled = false;
  }
}

modePaintBtn.addEventListener('click', () => setMode('paint'));
modeQueryBtn.addEventListener('click', () => setMode('query'));
modeSelectBtn.addEventListener('click', () => setMode('select'));

selectionApplyBtn.addEventListener('click', () => {
  if (state.selectedId === null || state.areaSelection.size === 0) {
    setStatus('Select tiles and choose a palette item first.');
    return;
  }
  for (const key of state.areaSelection) {
    const parts = key.split(',');
    const x = parseInt(parts[0], 10);
    const y = parseInt(parts[1], 10);
    if (!Number.isNaN(x) && !Number.isNaN(y)) {
      state.grid[y][x] = state.selectedId;
    }
  }
  state.areaSelection.clear();
  drawGrid();
  setStatus('Selection filled.');
});

selectionClearBtn.addEventListener('click', () => {
  state.areaSelection.clear();
  drawGrid();
  setStatus('Selection cleared.');
});

document.getElementById('map-wrap').addEventListener('wheel', (evt) => {
  if (!evt.ctrlKey && !evt.shiftKey) return;
  evt.preventDefault();
  const delta = evt.deltaY;
  let val = parseInt(cellSizeEl.value, 10) || 10;
  val += (delta < 0 ? 1 : -1);
  val = Math.max(4, Math.min(24, val));
  cellSizeEl.value = val;
  resizeCanvas();
  drawGrid();
  if (state.selected) scrollToCell(state.selected);
}, { passive: false });

loadBtn.addEventListener('click', async () => {
  const zone = parseInt(zoneSelect.value, 10);
  if (!zone) return;
  setStatus('Loading...');
  try {
    const data = await fetchJson(`/api/map?zone=${zone}`);
    state.zone = data.zone;
    state.grid = data.grid;
    state.width = data.width;
    state.height = data.height;
    state.xoff = data.x_offset;
    state.yoff = data.y_offset;
    state.wilderness = data.wilderness;
    state.name = data.name;
    state.selected = null;
    setSelectedCell(null);
    resizeCanvas();
    drawGrid();
    setStatus(`Loaded zone ${data.zone} ${data.name}`);
    loadExitList();
  } catch (e) {
    setStatus(`Load failed: ${e.message}`);
  }
});

saveBtn.addEventListener('click', async () => {
  if (!state.zone) return;
  setStatus('Saving...');
  try {
    const res = await fetchJson(`/api/map?zone=${state.zone}`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({grid: state.grid})
    });
    setStatus(`Saved. Backup: ${res.backup}`);
  } catch (e) {
    setStatus(`Save failed: ${e.message}`);
  }
});

function vnumToCell(vnum) {
  if (!state.zone) return null;
  let vx = 0;
  let vy = 0;
  if (state.wilderness === 1) {
    vy = Math.floor((vnum - 1000000) / 1000);
    vx = (vnum - 1000000) % 1000;
  } else {
    vy = Math.floor((vnum - (state.zone * 100)) / 100);
    vx = (vnum - (state.zone * 100)) % 100;
  }
  const x = vx - state.xoff;
  const y = vy - state.yoff;
  if (x < 0 || y < 0 || x >= state.width || y >= state.height) return null;
  return {x, y, vx, vy};
}

function scrollToCell(pos) {
  const wrap = document.getElementById('map-wrap');
  const size = parseInt(cellSizeEl.value, 10) || 10;
  const cx = pos.x * size + size / 2;
  const cy = pos.y * size + size / 2;
  wrap.scrollLeft = Math.max(0, cx - wrap.clientWidth / 2);
  wrap.scrollTop = Math.max(0, cy - wrap.clientHeight / 2);
}

function updateEntranceCells(exits) {
  state.entranceCells.clear();
  if (!exits) return;
  for (const vnum of Object.keys(exits)) {
    const pos = vnumToCell(parseInt(vnum, 10));
    if (!pos) continue;
    state.entranceCells.add(`${pos.x},${pos.y}`);
  }
}

async function loadExitList() {
  if (!state.zone) return;
  try {
    const data = await fetchJson(`/api/exits?zone=${state.zone}`);
    updateEntranceCells(data.exits || {});
    exitList.innerHTML = '';
    if (!data.exits || Object.keys(data.exits).length === 0) {
      exitList.textContent = 'No exits defined.';
      return;
    }
    const keys = Object.keys(data.exits).sort((a,b)=>parseInt(a)-parseInt(b));
    const dirNames = {0:'N',1:'E',2:'S',3:'W',4:'U',5:'D'};
    for (const vnum of keys) {
      if (state.selected) {
        const vx = state.xoff + state.selected.x;
        const vy = state.yoff + state.selected.y;
        const selVnum = (state.wilderness === 1)
          ? (1000000 + (vy * 1000) + vx)
          : ((state.zone * 100) + (vy * 100) + vx);
        if (parseInt(vnum, 10) !== selVnum) continue;
      }
      const exits = data.exits[vnum];
      const row = document.createElement('div');
      row.style.marginBottom = '6px';
      const title = document.createElement('div');
      title.textContent = `Cell ${vnum}`;
      row.appendChild(title);
      for (const ex of exits) {
        const dir = ex.dir;
        const toVnum = ex.to_vnum;
        const btn = document.createElement('button');
        btn.className = 'btn';
        btn.style.margin = '2px';
        const label = dirNames[dir] || dir;
        btn.textContent = `${label} -> ${toVnum}`;
        btn.addEventListener('click', () => {
          const pos = vnumToCell(parseInt(vnum, 10));
          if (!pos) return;
          setSelectedCell({x: pos.x, y: pos.y});
          scrollToCell({x: pos.x, y: pos.y});
        });
        row.appendChild(btn);
        const link = document.createElement('a');
        link.href = `/room?vnum=${toVnum}`;
        link.target = '_blank';
        link.textContent = 'open';
        link.style.marginLeft = '6px';
        row.appendChild(link);
        const rm = document.createElement('button');
        rm.className = 'btn';
        rm.style.marginLeft = '6px';
        rm.textContent = 'remove';
        rm.addEventListener('click', () => {
          fetchJson(`/api/exit?zone=${state.zone}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({vnum: parseInt(vnum, 10), dir: dir, match_to_vnum: toVnum})
          }).then(res => {
            setStatus(res.message || 'Exit removed.');
            loadExitList();
          }).catch(e => setStatus(`Exit remove failed: ${e.message}`));
        });
        row.appendChild(rm);
      }
      exitList.appendChild(row);
    }
    if (!exitList.innerHTML) {
      exitList.textContent = 'No exits for selected cell.';
    }
    drawGrid();
  } catch (e) {
    exitList.textContent = `Failed to load exits: ${e.message}`;
  }
}

async function setExit(remove) {
  if (!state.zone || !state.selected) return;
  const dir = parseInt(exitDir.value, 10);
  const vx = state.xoff + state.selected.x;
  const vy = state.yoff + state.selected.y;
  let vnum = '';
  if (state.wilderness === 1) vnum = 1000000 + (vy * 1000) + vx;
  else vnum = (state.zone * 100) + (vy * 100) + vx;
  const payload = { vnum: vnum, dir: dir };
  if (!remove) {
    const tgt = parseInt(exitTarget.value, 10);
    if (!tgt) { setStatus('Set a target vnum first.'); return; }
    payload.to_vnum = tgt;
  } else {
    const tgt = parseInt(exitTarget.value, 10);
    if (tgt) payload.match_to_vnum = tgt;
  }
  try {
    const res = await fetchJson(`/api/exit?zone=${state.zone}`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    setStatus(res.message || 'Exit updated.');
    loadExitList();
  } catch (e) {
    setStatus(`Exit update failed: ${e.message}`);
  }
}

exitSet.addEventListener('click', () => setExit(false));
exitDel.addEventListener('click', () => setExit(true));

async function init() {
  const palette = await fetchJson('/api/palette');
  state.palette = palette;
  state.paletteById = {};
  for (const item of palette) state.paletteById[item.id] = item;
  state.selectedId = palette[0].id;
  state.mode = 'query';
  setMode('query');
  renderPalette();
  const zones = await fetchJson('/api/zones');
  for (const z of zones) {
    const opt = document.createElement('option');
    opt.value = z.number;
    opt.textContent = `${z.number} ${z.name} (${z.wilderness === 2 ? 'miniwild' : 'wild'})`;
    zoneSelect.appendChild(opt);
  }
  paletteMeta.textContent = `Palette (${palette.length})`;

  const params = new URLSearchParams(window.location.search);
  if (params.get('vnum')) {
    const vnum = parseInt(params.get('vnum'), 10);
    // Find zone that matches vnum by asking server
    try {
      const room = await fetchJson(`/api/room?vnum=${vnum}`);
      if (room.zone) {
        zoneSelect.value = room.zone;
        loadBtn.click();
        // selection will be updated after load via query mode click;
        // we directly select here when grid is ready.
        setTimeout(() => {
          const pos = vnumToCell(vnum);
          if (pos) {
            setSelectedCell({x: pos.x, y: pos.y});
            scrollToCell({x: pos.x, y: pos.y});
          }
        }, 300);
      }
    } catch (e) {
      setStatus(`Init vnum failed: ${e.message}`);
    }
  }
  if (params.get('zone')) {
    const zone = parseInt(params.get('zone'), 10);
    if (zone) {
      zoneSelect.value = zone;
      loadBtn.click();
    }
  }
}

init().catch(e => setStatus(`Init failed: ${e.message}`));
</script>
</body>
</html>
"""

ROOM_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Zone Editor</title>
  <style>
    body { margin: 0; font-family: monospace; background: #101417; color: #e6e6e6; }
    header { padding: 10px 14px; border-bottom: 1px solid #2a2f35; display: flex; gap: 12px; align-items: center; }
    main { padding: 12px 14px; }
    .row { display: flex; gap: 10px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }
    .btn { background: #1b2230; color: #e6e6e6; border: 1px solid #2a2f35; padding: 6px 10px; cursor: pointer; }
    input, textarea, select { background: #0f141a; color: #e6e6e6; border: 1px solid #2a2f35; padding: 4px; }
    textarea { width: 100%; height: 160px; }
    .box { border: 1px solid #2a2f35; padding: 8px; margin-bottom: 12px; }
    .meta { font-size: 12px; opacity: 0.8; }
    table { width: 100%; border-collapse: collapse; }
    th, td { border: 1px solid #2a2f35; padding: 4px; font-size: 12px; }
    .search-results { border: 1px solid #2a2f35; background: #0f141a; max-height: 180px; overflow: auto; }
    .search-results button { width: 100%; text-align: left; background: transparent; color: #e6e6e6; border: none; padding: 6px 8px; cursor: pointer; }
    .search-results button:hover { background: #1b2230; }
  </style>
</head>
<body>
  <header>
    <div class="row">
      <label>Room VNUM</label>
      <input id="vnumInput" type="number" style="width:120px">
      <button id="loadBtn" class="btn">Load Room</button>
    </div>
    <div class="row">
      <label>Room Search</label>
      <input id="roomSearch" type="text" placeholder="Search room name/desc" style="width:260px">
      <button id="roomSearchBtn" class="btn">Find</button>
    </div>
    <div id="roomSearchResults" class="search-results" style="display:none;"></div>
    <div class="row">
      <label>Zone</label>
      <input id="zoneOpenInput" type="number" style="width:120px">
      <button id="zoneOpenBtn" class="btn">Open Zone</button>
    </div>
    <div class="row">
      <label>Zone Search</label>
      <input id="zoneSearch" type="text" placeholder="Search zone name/number" style="width:260px">
      <button id="zoneSearchBtn" class="btn">Find</button>
    </div>
    <div id="zoneSearchResults" class="search-results" style="display:none;"></div>
    <a class="btn" href="/help" target="_blank">Help</a>
    <div class="meta" id="status">Idle</div>
    <button id="saveBtn" class="btn">Save</button>
  </header>
  <main>
    <div class="box">
      <div class="row">
        <label>Name</label>
        <input id="nameInput" type="text" style="flex:1">
      </div>
      <div class="row">
        <label>Room Flags</label>
        <input id="flagsInput" type="number" style="width:120px">
        <label>Sector</label>
        <input id="sectorInput" type="number" style="width:120px">
        <label>Zone</label>
        <input id="zoneInput" type="number" style="width:120px" disabled>
      </div>
      <div class="row">
        <label>Description</label>
      </div>
      <textarea id="descInput"></textarea>
    </div>

    <div class="box">
      <div class="row">
        <div class="meta">Exits</div>
        <button id="addExitBtn" class="btn">Add Exit</button>
      </div>
      <table id="exitsTable">
        <thead>
          <tr><th>Dir</th><th>To VNUM</th><th>Exit Info</th><th>Key</th><th>To Room Key</th><th>Actions</th></tr>
        </thead>
        <tbody></tbody>
      </table>
    </div>

    <div class="box">
      <div class="row">
        <div class="meta">Room Spawns (M/O)</div>
        <div class="meta" id="spawnHint">Mob/Object VNUM + Max count in this room.</div>
      </div>
      <table id="spawnsTable">
        <thead>
          <tr><th>Cmd</th><th>VNUM</th><th>Max</th></tr>
        </thead>
        <tbody></tbody>
      </table>
      <div class="row">
        <label>Type</label>
        <select id="spawnCmd">
          <option value="M">Mob (M)</option>
          <option value="O">Object (O)</option>
        </select>
        <label>VNUM</label>
        <input id="spawnVnum" type="number" placeholder="Mob/Object VNUM" style="width:140px">
        <label>Max</label>
        <input id="spawnMax" type="number" placeholder="Max in room" value="1" style="width:100px">
        <button id="spawnAdd" class="btn">Add Spawn</button>
      </div>
      <div class="row">
        <label>Find</label>
        <input id="spawnSearch" type="text" placeholder="Search mob/object by name" style="width:260px">
        <button id="spawnSearchBtn" class="btn">Search</button>
      </div>
      <div id="spawnSearchResults" class="search-results" style="display:none;"></div>
      <div class="meta">Spawns are appended to the zone file. Backup is created on save.</div>
    </div>

    <div class="box">
      <div class="row">
        <div class="meta">Zone Reset Commands</div>
      </div>
      <table id="resetsTable">
        <thead>
          <tr><th>Cmd</th><th>if</th><th>arg1</th><th>arg2</th><th>arg3</th><th>raw</th></tr>
        </thead>
        <tbody></tbody>
      </table>
      <div class="row">
        <label>Cmd</label>
        <select id="resetCmd">
          <option value="M">M</option>
          <option value="O">O</option>
          <option value="E">E</option>
          <option value="G">G</option>
          <option value="P">P</option>
          <option value="D">D</option>
          <option value="R">R</option>
        </select>
        <label>If</label>
        <input id="resetIf" type="number" placeholder="If (0/1)" value="0" style="width:80px">
        <label id="resetA1Label">Arg1</label>
        <input id="resetA1" type="number" placeholder="Arg1" style="width:120px">
        <label id="resetA2Label">Arg2</label>
        <input id="resetA2" type="number" placeholder="Arg2" style="width:120px">
        <label id="resetA3Label">Arg3</label>
        <input id="resetA3" type="number" placeholder="Arg3" style="width:120px">
        <input id="resetComment" type="text" placeholder="comment" style="width:180px">
        <button id="resetAdd" class="btn">Append Reset</button>
      </div>
      <div class="meta" id="resetHint">Select a command to see argument meanings.</div>
      <div class="meta">
        For M/O/D/R, set args to target this room (M/O: arg3=room vnum; D: arg1=room vnum; R: arg2=room vnum).
      </div>
    </div>

    <div class="box">
      <div class="row">
        <div class="meta">Zone Map (non‑wild)</div>
        <label>Zoom</label>
        <input id="zoneZoom" type="number" min="10" max="60" value="20" style="width:60px">
      </div>
      <canvas id="zoneCanvas"></canvas>
      <div class="meta">Click a room to open it.</div>
    </div>
  </main>
<script>
const statusEl = document.getElementById('status');
const vnumInput = document.getElementById('vnumInput');
const loadBtn = document.getElementById('loadBtn');
const zoneCanvas = document.getElementById('zoneCanvas');
const zoneZoom = document.getElementById('zoneZoom');
const zctx = zoneCanvas.getContext('2d');
let zoneIndex = [];
const saveBtn = document.getElementById('saveBtn');
const nameInput = document.getElementById('nameInput');
const descInput = document.getElementById('descInput');
const flagsInput = document.getElementById('flagsInput');
const sectorInput = document.getElementById('sectorInput');
const zoneInput = document.getElementById('zoneInput');
const exitsTable = document.getElementById('exitsTable').querySelector('tbody');
const spawnsTable = document.getElementById('spawnsTable').querySelector('tbody');
const spawnCmd = document.getElementById('spawnCmd');
const spawnVnum = document.getElementById('spawnVnum');
const spawnMax = document.getElementById('spawnMax');
const spawnAdd = document.getElementById('spawnAdd');
const roomSearchInput = document.getElementById('roomSearch');
const roomSearchBtn = document.getElementById('roomSearchBtn');
const roomSearchResults = document.getElementById('roomSearchResults');
const zoneOpenInput = document.getElementById('zoneOpenInput');
const zoneOpenBtn = document.getElementById('zoneOpenBtn');
const zoneSearchInput = document.getElementById('zoneSearch');
const zoneSearchBtn = document.getElementById('zoneSearchBtn');
const zoneSearchResults = document.getElementById('zoneSearchResults');
const spawnSearchInput = document.getElementById('spawnSearch');
const spawnSearchBtn = document.getElementById('spawnSearchBtn');
const spawnSearchResults = document.getElementById('spawnSearchResults');
const spawnHint = document.getElementById('spawnHint');
const resetsTable = document.getElementById('resetsTable').querySelector('tbody');
const resetCmd = document.getElementById('resetCmd');
const resetIf = document.getElementById('resetIf');
const resetA1 = document.getElementById('resetA1');
const resetA2 = document.getElementById('resetA2');
const resetA3 = document.getElementById('resetA3');
const resetComment = document.getElementById('resetComment');
const resetAdd = document.getElementById('resetAdd');
const resetA1Label = document.getElementById('resetA1Label');
const resetA2Label = document.getElementById('resetA2Label');
const resetA3Label = document.getElementById('resetA3Label');
const resetHint = document.getElementById('resetHint');

let roomData = null;

function setStatus(msg) { statusEl.textContent = msg; }

function fetchJson(url, opts) {
  return fetch(url, opts).then(r =>
    r.json().then(data => {
      if (!r.ok) throw new Error(data.error || r.statusText);
      return data;
    })
  );
}

function renderExits() {
  exitsTable.innerHTML = '';
  if (!roomData) return;
  const dirNames = {0:'N',1:'E',2:'S',3:'W',4:'U',5:'D'};
  for (const ex of roomData.exits) {
    const tr = document.createElement('tr');
    const dir = document.createElement('td');
    const dirSelect = document.createElement('select');
    for (const [num, label] of Object.entries(dirNames)) {
      const opt = document.createElement('option');
      opt.value = num;
      opt.textContent = label;
      dirSelect.appendChild(opt);
    }
    dirSelect.value = String(ex.dir);
    dir.appendChild(dirSelect);
    const to = document.createElement('td');
    const toInput = document.createElement('input');
    toInput.type = 'number';
    toInput.value = ex.to_room;
    to.appendChild(toInput);
    const info = document.createElement('td');
    const infoInput = document.createElement('input');
    infoInput.type = 'number';
    infoInput.value = ex.exit_info;
    info.appendChild(infoInput);
    const key = document.createElement('td');
    const keyInput = document.createElement('input');
    keyInput.type = 'number';
    keyInput.value = ex.key;
    key.appendChild(keyInput);
    const trk = document.createElement('td');
    const trkInput = document.createElement('input');
    trkInput.type = 'number';
    trkInput.value = ex.to_room_key;
    trk.appendChild(trkInput);
    const actions = document.createElement('td');
    const delBtn = document.createElement('button');
    delBtn.className = 'btn';
    delBtn.textContent = 'Remove';
    delBtn.addEventListener('click', () => {
      roomData.exits = roomData.exits.filter(e => e !== ex);
      renderExits();
    });
    actions.appendChild(delBtn);
    tr.appendChild(dir);
    tr.appendChild(to);
    tr.appendChild(info);
    tr.appendChild(key);
    tr.appendChild(trk);
    tr.appendChild(actions);
    exitsTable.appendChild(tr);
    ex._inputs = {dirSelect, toInput, infoInput, keyInput, trkInput};
  }
}

function renderZoneMap(data, currentVnum, neighborSet) {
  const size = parseInt(zoneZoom.value, 10) || 20;
  const rooms = data.rooms || [];
  const edges = data.edges || [];
  const external = data.external || [];
  if (!rooms.length) {
    zoneCanvas.width = 0;
    zoneCanvas.height = 0;
    zoneIndex = [];
    return;
  }
  const maxX = Math.max(...rooms.map(r => r.x));
  const maxY = Math.max(...rooms.map(r => r.y));
  zoneCanvas.width = (maxX + 1) * size;
  zoneCanvas.height = (maxY + 1) * size;
  zctx.fillStyle = '#0c0f12';
  zctx.fillRect(0, 0, zoneCanvas.width, zoneCanvas.height);
  zctx.strokeStyle = '#3a4a5a';
  zctx.lineWidth = 2;
  const dirVec = {0:[0,-1],1:[1,0],2:[0,1],3:[-1,0]};
  for (const e of edges) {
    const x1 = e.x1 * size + size / 2;
    const y1 = e.y1 * size + size / 2;
    const x2 = e.x2 * size + size / 2;
    const y2 = e.y2 * size + size / 2;
    zctx.beginPath();
    zctx.moveTo(x1, y1);
    zctx.lineTo(x2, y2);
    zctx.stroke();
  }
  if (external.length) {
    zctx.strokeStyle = '#7a5a3a';
    zctx.setLineDash([6, 4]);
    for (const e of external) {
      const x1 = e.x1 * size + size / 2;
      const y1 = e.y1 * size + size / 2;
      let x2 = x1;
      let y2 = y1;
      if (dirVec[e.dir]) {
        x2 = x1 + dirVec[e.dir][0] * size * 0.7;
        y2 = y1 + dirVec[e.dir][1] * size * 0.7;
        zctx.beginPath();
        zctx.moveTo(x1, y1);
        zctx.lineTo(x2, y2);
        zctx.stroke();
        zctx.fillStyle = '#7a5a3a';
        zctx.beginPath();
        zctx.arc(x2, y2, Math.max(3, size * 0.12), 0, Math.PI * 2);
        zctx.fill();
      }
    }
    zctx.setLineDash([]);
  }
  zoneIndex = rooms;
  for (const r of rooms) {
    const x = r.x * size;
    const y = r.y * size;
    if (currentVnum && r.vnum === currentVnum) {
      zctx.fillStyle = '#1f6b3a';
    } else if (neighborSet && neighborSet.has(r.vnum)) {
      zctx.fillStyle = '#6b6a1f';
    } else {
      zctx.fillStyle = '#1f3b5a';
    }
    zctx.fillRect(x + 2, y + 2, size - 4, size - 4);
    zctx.fillStyle = '#e6e6e6';
    zctx.font = '10px monospace';
    zctx.textAlign = 'center';
    zctx.textBaseline = 'middle';
    zctx.fillText(r.vnum, x + size / 2, y + size / 2);
  }
}

function renderSpawns() {
  spawnsTable.innerHTML = '';
  if (!roomData) return;
  for (const s of roomData.spawns) {
    const tr = document.createElement('tr');
    const link = s.cmd === 'M' ? `/mob?vnum=${s.vnum}` : `/obj?vnum=${s.vnum}`;
    tr.innerHTML = `<td>${s.cmd}</td><td>${s.vnum} <a href="${link}" target="_blank">open</a></td><td>${s.max}</td>`;
    spawnsTable.appendChild(tr);
  }
}

function updateResetHints() {
  const cmd = resetCmd.value;
  const map = {
    M: {a1: 'Mob VNUM', a2: 'Max in zone', a3: 'Room VNUM', hint: 'Load a mob into a room.'},
    O: {a1: 'Object VNUM', a2: 'Max in zone', a3: 'Room VNUM', hint: 'Load an object into a room.'},
    E: {a1: 'Object VNUM', a2: 'Max in zone', a3: 'Wear position', hint: 'Equip last loaded mob.'},
    G: {a1: 'Object VNUM', a2: 'Max in zone', a3: 'unused', hint: 'Give to last loaded mob.'},
    P: {a1: 'Object VNUM', a2: 'Max in zone', a3: 'Container VNUM', hint: 'Put object into another object.'},
    D: {a1: 'Room VNUM', a2: 'Dir (0-5)', a3: 'State', hint: 'Set door state (0=open,1=closed,2=locked).'},
    R: {a1: 'Object VNUM', a2: 'Room VNUM', a3: 'unused', hint: 'Remove object from room.'},
  };
  const info = map[cmd] || {a1:'Arg1', a2:'Arg2', a3:'Arg3', hint:'Select a command to see argument meanings.'};
  resetA1Label.textContent = info.a1;
  resetA2Label.textContent = info.a2;
  resetA3Label.textContent = info.a3;
  resetHint.textContent = info.hint;
}

function renderResets() {
  resetsTable.innerHTML = '';
  if (!roomData) return;
  for (const r of roomData.resets) {
    const tr = document.createElement('tr');
    let link = '';
    if (['M', 'O', 'E', 'G', 'P'].includes(r.cmd)) {
      const target = r.cmd === 'M' ? 'mob' : 'obj';
      link = ` <a href="/${target}?vnum=${r.arg1}" target="_blank">open</a>`;
    }
    tr.innerHTML = `<td>${r.cmd}</td><td>${r.if_flag}</td><td>${r.arg1}${link}</td><td>${r.arg2}</td><td>${r.arg3 ?? ''}</td><td>${r.raw}</td>`;
    resetsTable.appendChild(tr);
  }
}

function syncExitInputs() {
  for (const ex of roomData.exits) {
    ex.dir = parseInt(ex._inputs.dirSelect.value, 10) || 0;
    ex.to_room = parseInt(ex._inputs.toInput.value, 10) || 0;
    ex.exit_info = parseInt(ex._inputs.infoInput.value, 10) || 0;
    ex.key = parseInt(ex._inputs.keyInput.value, 10) || 0;
    ex.to_room_key = parseInt(ex._inputs.trkInput.value, 10) || 0;
  }
}

async function loadRoom() {
  const vnum = parseInt(vnumInput.value, 10);
  if (!vnum) return;
  setStatus('Loading...');
  try {
    const data = await fetchJson(`/api/room?vnum=${vnum}`);
    roomData = data;
    nameInput.value = data.name;
    descInput.value = data.description;
    flagsInput.value = data.room_flags;
    sectorInput.value = data.sector_type;
    zoneInput.value = data.zone;
    renderExits();
    renderSpawns();
    renderResets();
    const ro = !!data.readonly;
    saveBtn.disabled = ro;
    nameInput.disabled = ro;
    descInput.disabled = ro;
    flagsInput.disabled = ro;
    sectorInput.disabled = ro;
    document.getElementById('addExitBtn').disabled = ro;
    spawnAdd.disabled = ro;
    if (data.zone_wilderness === 0) {
      const z = await fetchJson(`/api/zone_map?zone=${data.zone}`);
      const neighbors = new Set();
      for (const ex of data.exits || []) {
        if (ex.to_room) neighbors.add(ex.to_room);
      }
      renderZoneMap(z, data.vnum, neighbors);
    } else {
      renderZoneMap({rooms: [], edges: []});
    }
    setStatus(`Loaded ${data.vnum} (${data.zone_name || 'zone'})`);
  } catch (e) {
    setStatus(`Load failed: ${e.message}`);
  }
}

async function saveRoom() {
  if (!roomData) return;
  syncExitInputs();
  roomData.name = nameInput.value;
  roomData.description = descInput.value;
  roomData.room_flags = parseInt(flagsInput.value, 10) || 0;
  roomData.sector_type = parseInt(sectorInput.value, 10) || 0;
  setStatus('Saving...');
  try {
    const res = await fetchJson(`/api/room?vnum=${roomData.vnum}`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(roomData)
    });
    setStatus(res.message || 'Saved.');
  } catch (e) {
    setStatus(`Save failed: ${e.message}`);
  }
}

function renderSearchResults(container, results, onSelect) {
  container.innerHTML = '';
  if (!results.length) {
    container.style.display = 'none';
    return;
  }
  for (const r of results) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = `#${r.vnum} ${r.name || ''}`.trim();
    btn.addEventListener('click', () => onSelect(r));
    container.appendChild(btn);
  }
  container.style.display = 'block';
}

async function searchRooms() {
  const q = roomSearchInput.value.trim();
  if (!q) return;
  setStatus('Searching rooms...');
  try {
    const data = await fetchJson(`/api/search_room?q=${encodeURIComponent(q)}`);
    renderSearchResults(roomSearchResults, data.results || [], (r) => {
      roomSearchResults.style.display = 'none';
      vnumInput.value = r.vnum;
      loadRoom();
    });
    setStatus(`Found ${data.results.length} rooms`);
  } catch (e) {
    setStatus(`Search failed: ${e.message}`);
  }
}

async function openZoneByNumber(zoneNum) {
  if (!zoneNum) return;
  setStatus('Opening zone...');
  try {
    const info = await fetchJson(`/api/zone_info?zone=${zoneNum}`);
    if (info.wilderness && info.wilderness !== 0) {
      window.open(`/wild?zone=${zoneNum}`, '_blank');
      setStatus(`Opened wilderness zone ${zoneNum}`);
      return;
    }
    const res = await fetchJson(`/api/zone_first_room?zone=${zoneNum}`);
    vnumInput.value = res.vnum;
    loadRoom();
  } catch (e) {
    setStatus(`Open zone failed: ${e.message}`);
  }
}


async function searchZones() {
  const q = zoneSearchInput.value.trim();
  if (!q) return;
  setStatus('Searching zones...');
  try {
    const data = await fetchJson(`/api/search_zone?q=${encodeURIComponent(q)}`);
    renderSearchResults(zoneSearchResults, data.results || [], (z) => {
      zoneSearchResults.style.display = 'none';
      zoneOpenInput.value = z.number;
      openZoneByNumber(z.number);
    });
    setStatus(`Found ${data.results.length} zones`);
  } catch (e) {
    setStatus(`Search failed: ${e.message}`);
  }
}

async function searchSpawns() {
  const q = spawnSearchInput.value.trim();
  if (!q) return;
  const endpoint = spawnCmd.value === 'M' ? 'search_mob' : 'search_obj';
  setStatus('Searching...');
  try {
    const data = await fetchJson(`/api/${endpoint}?q=${encodeURIComponent(q)}`);
    renderSearchResults(spawnSearchResults, data.results || [], (r) => {
      spawnSearchResults.style.display = 'none';
      spawnVnum.value = r.vnum;
    });
    setStatus(`Found ${data.results.length} entries`);
  } catch (e) {
    setStatus(`Search failed: ${e.message}`);
  }
}

loadBtn.addEventListener('click', loadRoom);
saveBtn.addEventListener('click', saveRoom);
resetCmd.addEventListener('change', updateResetHints);
roomSearchBtn.addEventListener('click', searchRooms);
roomSearchInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') searchRooms();
});
zoneOpenBtn.addEventListener('click', () => openZoneByNumber(parseInt(zoneOpenInput.value, 10)));
zoneSearchBtn.addEventListener('click', searchZones);
zoneSearchInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') searchZones();
});
spawnSearchBtn.addEventListener('click', searchSpawns);
spawnSearchInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') searchSpawns();
});
zoneCanvas.addEventListener('click', (evt) => {
  const rect = zoneCanvas.getBoundingClientRect();
  const size = parseInt(zoneZoom.value, 10) || 20;
  const x = Math.floor((evt.clientX - rect.left) / size);
  const y = Math.floor((evt.clientY - rect.top) / size);
  const room = zoneIndex.find(r => r.x === x && r.y === y);
  if (room) {
    vnumInput.value = room.vnum;
    loadRoom();
  }
});

zoneZoom.addEventListener('change', () => {
  if (roomData && roomData.zone_wilderness === 0) {
    fetchJson(`/api/zone_map?zone=${roomData.zone}`).then(z => {
      const neighbors = new Set();
      for (const ex of roomData.exits || []) {
        if (ex.to_room) neighbors.add(ex.to_room);
      }
      renderZoneMap(z, roomData.vnum, neighbors);
    });
  }
});

zoneCanvas.addEventListener('wheel', (evt) => {
  evt.preventDefault();
  const delta = evt.deltaY < 0 ? 2 : -2;
  const current = parseInt(zoneZoom.value, 10) || 20;
  const next = Math.min(60, Math.max(10, current + delta));
  if (next !== current) {
    zoneZoom.value = next;
    zoneZoom.dispatchEvent(new Event('change'));
  }
}, { passive: false });

document.getElementById('addExitBtn').addEventListener('click', () => {
  if (!roomData) return;
  roomData.exits.push({
    dir: 0, keyword: '', description: '',
    exit_info: 0, key: 0, to_room: 0, to_room_key: 0
  });
  renderExits();
});

spawnAdd.addEventListener('click', async () => {
  if (!roomData) return;
  const cmd = spawnCmd.value;
  const vnum = parseInt(spawnVnum.value, 10);
  const max = parseInt(spawnMax.value, 10) || 1;
  if (!vnum) { setStatus('Spawn VNUM required.'); return; }
  setStatus('Adding spawn...');
  try {
    const res = await fetchJson(`/api/spawn?vnum=${roomData.vnum}`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({cmd, vnum, max})
    });
    setStatus(res.message || 'Spawn added.');
    const data = await fetchJson(`/api/room?vnum=${roomData.vnum}`);
    roomData = data;
    renderSpawns();
    renderResets();
  } catch (e) {
    setStatus(`Spawn add failed: ${e.message}`);
  }
});

updateResetHints();

resetAdd.addEventListener('click', async () => {
  if (!roomData) return;
  const cmd = resetCmd.value;
  const ifFlag = parseInt(resetIf.value, 10) || 0;
  const a1 = parseInt(resetA1.value, 10) || 0;
  const a2 = parseInt(resetA2.value, 10) || 0;
  const a3 = parseInt(resetA3.value, 10) || 0;
  const comment = resetComment.value || '';
  setStatus('Appending reset...');
  try {
    const res = await fetchJson(`/api/reset?vnum=${roomData.vnum}`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({cmd, if_flag: ifFlag, arg1: a1, arg2: a2, arg3: a3, comment})
    });
    setStatus(res.message || 'Reset appended.');
    const data = await fetchJson(`/api/room?vnum=${roomData.vnum}`);
    roomData = data;
    renderResets();
  } catch (e) {
    setStatus(`Reset append failed: ${e.message}`);
  }
});

// Init from query param
const params = new URLSearchParams(window.location.search);
if (params.get('vnum')) {
  vnumInput.value = params.get('vnum');
  loadRoom();
}
</script>
</body>
</html>
"""

MOB_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mob Editor</title>
  <style>
    body { margin: 0; font-family: monospace; background: #101417; color: #e6e6e6; }
    header { padding: 10px 14px; border-bottom: 1px solid #2a2f35; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
    main { padding: 12px 14px; }
    .btn { background: #1b2230; color: #e6e6e6; border: 1px solid #2a2f35; padding: 6px 10px; cursor: pointer; }
    input, textarea, select { background: #0f141a; color: #e6e6e6; border: 1px solid #2a2f35; padding: 4px; }
    textarea { width: 100%; min-height: 90px; }
    .box { border: 1px solid #2a2f35; padding: 10px; margin-bottom: 12px; }
    .meta { font-size: 12px; opacity: 0.8; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; }
    .field label { display: block; font-size: 12px; opacity: 0.85; margin-bottom: 4px; }
    .row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
    .list-row { display: grid; grid-template-columns: 1fr 1fr auto; gap: 8px; align-items: center; margin-bottom: 6px; }
    .list-row input { width: 100%; }
    .list-row .btn { padding: 4px 8px; }
    .section-title { font-size: 13px; text-transform: uppercase; letter-spacing: 0.08em; opacity: 0.7; margin-bottom: 8px; }
    .search-results { border: 1px solid #2a2f35; background: #0f141a; max-height: 180px; overflow: auto; width: 100%; }
    .search-results button { width: 100%; text-align: left; background: transparent; color: #e6e6e6; border: none; padding: 6px 8px; cursor: pointer; }
    .search-results button:hover { background: #1b2230; }
    .flag-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 6px; margin-top: 6px; max-height: 160px; overflow: auto; padding: 4px; }
    .flag-item { display: flex; gap: 6px; align-items: center; font-size: 12px; }
    .affect-hint { font-size: 11px; opacity: 0.75; grid-column: 1 / -1; }
    .affect-list { max-height: 220px; overflow: auto; padding: 4px; border: 1px solid #2a2f35; background: #0f141a; }
  </style>
</head>
<body>
  <header>
    <div class="row">
      <label>Mob VNUM</label>
      <input id="vnumInput" type="number" style="width:120px">
      <button id="loadBtn" class="btn">Load</button>
    </div>
    <div class="row">
      <label>Search</label>
      <input id="mobSearch" type="text" placeholder="Search mob name/desc" style="width:260px">
      <button id="mobSearchBtn" class="btn">Find</button>
    </div>
    <div id="mobSearchResults" class="search-results" style="display:none;"></div>
    <a class="btn" href="/help" target="_blank">Help</a>
    <div class="meta" id="status">Idle</div>
    <button id="saveBtn" class="btn">Save</button>
  </header>
  <main>
    <div class="box">
      <div class="section-title">Strings</div>
      <div class="grid">
        <div class="field"><label>Keywords</label><input id="keywords" type="text"></div>
        <div class="field"><label>Short description</label><input id="shortDesc" type="text"></div>
        <div class="field"><label>Long description</label><input id="longDesc" type="text"></div>
      </div>
      <div class="field" style="margin-top:8px;">
        <label>Description</label>
        <textarea id="description"></textarea>
      </div>
    </div>
    <div class="box">
      <div class="section-title">Unused Strings (Legacy)</div>
      <div class="grid">
        <div class="field"><label>Unused 1</label><textarea id="unused1"></textarea></div>
        <div class="field"><label>Unused 2</label><textarea id="unused2"></textarea></div>
        <div class="field"><label>Unused 3</label><textarea id="unused3"></textarea></div>
      </div>
    </div>
    <div class="box">
      <div class="section-title">Flags and IDs</div>
      <div class="grid">
        <div class="field"><label>Act flags (string)</label><input id="actFlags" type="text"></div>
        <div class="field"><label>Affect flags (string)</label><input id="affFlags" type="text"></div>
        <div class="field"><label>Alignment</label><input id="alignment" type="number"></div>
        <div class="field"><label>Reserved 1</label><input id="reserved1" type="number"></div>
        <div class="field"><label>Reserved 2</label><input id="reserved2" type="number"></div>
        <div class="field"><label>Reserved 3</label><input id="reserved3" type="number"></div>
        <div class="field"><label>Master ID</label><input id="masterId" type="number"></div>
        <div class="field"><label>Clan ID</label><input id="clanId" type="number"></div>
        <div class="field"><label>Mob type</label>
          <select id="mobType">
            <option value="S">Simple (S)</option>
            <option value="E">Enhanced (E)</option>
          </select>
        </div>
      </div>
    </div>
    <div class="box">
      <div class="section-title">Stats</div>
      <div class="grid">
        <div class="field"><label>Level</label><input id="level" type="number"></div>
        <div class="field"><label>THAC0</label><input id="thac0" type="number"></div>
        <div class="field"><label>Armor (AC*10)</label><input id="armor" type="number"></div>
        <div class="field"><label>HP dice #</label><input id="hpNum" type="number"></div>
        <div class="field"><label>HP dice size</label><input id="hpSize" type="number"></div>
        <div class="field"><label>HP bonus</label><input id="hpBonus" type="number"></div>
        <div class="field"><label>Damage dice #</label><input id="damNum" type="number"></div>
        <div class="field"><label>Damage dice size</label><input id="damSize" type="number"></div>
        <div class="field"><label>Damage bonus</label><input id="damBonus" type="number"></div>
        <div class="field"><label>Gold</label><input id="gold" type="number"></div>
        <div class="field"><label>Experience</label><input id="exp" type="number"></div>
        <div class="field"><label>Position</label><input id="position" type="number"></div>
        <div class="field"><label>Default position</label><input id="defaultPosition" type="number"></div>
        <div class="field"><label>Sex</label><input id="sex" type="number"></div>
      </div>
    </div>
    <div class="box" id="especSection">
      <div class="section-title">Enhanced Specs</div>
      <div class="meta">Key/value pairs like BareHandAttack: 11</div>
      <div id="especList"></div>
      <button id="addEspec" class="btn">Add Spec</button>
    </div>
    <div class="box">
      <div class="section-title">Triggers</div>
      <div id="triggerList"></div>
      <button id="addTrigger" class="btn">Add Trigger</button>
    </div>
    <div class="box">
      <div class="section-title">Other Lines (Rare)</div>
      <div class="meta">Preserved for unusual data lines after triggers.</div>
      <textarea id="unknownLines"></textarea>
    </div>
  </main>
<script>
const statusEl = document.getElementById('status');
const vnumInput = document.getElementById('vnumInput');
const loadBtn = document.getElementById('loadBtn');
const saveBtn = document.getElementById('saveBtn');
const mobType = document.getElementById('mobType');
const especSection = document.getElementById('especSection');
const especList = document.getElementById('especList');
const triggerList = document.getElementById('triggerList');
const mobSearchInput = document.getElementById('mobSearch');
const mobSearchBtn = document.getElementById('mobSearchBtn');
const mobSearchResults = document.getElementById('mobSearchResults');

const fields = {
  keywords: document.getElementById('keywords'),
  short: document.getElementById('shortDesc'),
  long: document.getElementById('longDesc'),
  description: document.getElementById('description'),
  unused1: document.getElementById('unused1'),
  unused2: document.getElementById('unused2'),
  unused3: document.getElementById('unused3'),
  actFlags: document.getElementById('actFlags'),
  affFlags: document.getElementById('affFlags'),
  alignment: document.getElementById('alignment'),
  reserved1: document.getElementById('reserved1'),
  reserved2: document.getElementById('reserved2'),
  reserved3: document.getElementById('reserved3'),
  masterId: document.getElementById('masterId'),
  clanId: document.getElementById('clanId'),
  level: document.getElementById('level'),
  thac0: document.getElementById('thac0'),
  armor: document.getElementById('armor'),
  hpNum: document.getElementById('hpNum'),
  hpSize: document.getElementById('hpSize'),
  hpBonus: document.getElementById('hpBonus'),
  damNum: document.getElementById('damNum'),
  damSize: document.getElementById('damSize'),
  damBonus: document.getElementById('damBonus'),
  gold: document.getElementById('gold'),
  exp: document.getElementById('exp'),
  position: document.getElementById('position'),
  defaultPosition: document.getElementById('defaultPosition'),
  sex: document.getElementById('sex'),
  unknownLines: document.getElementById('unknownLines'),
};

function setStatus(msg) { statusEl.textContent = msg; }
function fetchJson(url, opts) {
  return fetch(url, opts).then(r =>
    r.json().then(data => {
      if (!r.ok) throw new Error(data.error || r.statusText);
      return data;
    })
  );
}

function renderSearchResults(container, results, onSelect) {
  container.innerHTML = '';
  if (!results.length) {
    container.style.display = 'none';
    return;
  }
  for (const r of results) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = `#${r.vnum} ${r.name || ''}`.trim();
    btn.addEventListener('click', () => onSelect(r));
    container.appendChild(btn);
  }
  container.style.display = 'block';
}

async function searchMobs() {
  const q = mobSearchInput.value.trim();
  if (!q) return;
  setStatus('Searching mobs...');
  try {
    const data = await fetchJson(`/api/search_mob?q=${encodeURIComponent(q)}`);
    renderSearchResults(mobSearchResults, data.results || [], (r) => {
      mobSearchResults.style.display = 'none';
      vnumInput.value = r.vnum;
      loadMob();
    });
    setStatus(`Found ${data.results.length} mobs`);
  } catch (e) {
    setStatus(`Search failed: ${e.message}`);
  }
}

function setEspecVisibility() {
  especSection.style.display = mobType.value === 'E' ? 'block' : 'none';
}

function addEspecRow(key = '', value = '') {
  const row = document.createElement('div');
  row.className = 'list-row';
  row.innerHTML = `
    <input class="espec-key" placeholder="Key" value="">
    <input class="espec-val" placeholder="Value" value="">
    <button class="btn">Remove</button>
  `;
  row.querySelector('.espec-key').value = key;
  row.querySelector('.espec-val').value = value;
  row.querySelector('button').addEventListener('click', () => row.remove());
  especList.appendChild(row);
}

function addTriggerRow(value = '') {
  const row = document.createElement('div');
  row.className = 'list-row';
  row.innerHTML = `
    <input class="trigger-val" placeholder="Trigger VNUM" type="number" value="">
    <div></div>
    <button class="btn">Remove</button>
  `;
  row.querySelector('.trigger-val').value = value;
  row.querySelector('button').addEventListener('click', () => row.remove());
  triggerList.appendChild(row);
}

function collectEspecs() {
  return [...especList.querySelectorAll('.list-row')].map(row => ({
    key: row.querySelector('.espec-key').value,
    value: row.querySelector('.espec-val').value,
  }));
}

function collectTriggers() {
  return [...triggerList.querySelectorAll('.list-row')].map(row =>
    parseInt(row.querySelector('.trigger-val').value, 10) || 0
  ).filter(v => v);
}

async function loadMob() {
  const vnum = parseInt(vnumInput.value, 10);
  if (!vnum) return;
  setStatus('Loading...');
  try {
    const data = await fetchJson(`/api/mob?vnum=${vnum}`);
    fields.keywords.value = data.strings.keywords || '';
    fields.short.value = data.strings.short || '';
    fields.long.value = data.strings.long || '';
    fields.description.value = data.strings.description || '';
    fields.unused1.value = (data.unused_strings && data.unused_strings[0]) || '';
    fields.unused2.value = (data.unused_strings && data.unused_strings[1]) || '';
    fields.unused3.value = (data.unused_strings && data.unused_strings[2]) || '';
    fields.actFlags.value = data.flags.act_flags || '';
    fields.affFlags.value = data.flags.aff_flags || '';
    fields.alignment.value = data.flags.alignment ?? 0;
    fields.reserved1.value = data.flags.reserved1 ?? 0;
    fields.reserved2.value = data.flags.reserved2 ?? 0;
    fields.reserved3.value = data.flags.reserved3 ?? 0;
    fields.masterId.value = data.flags.master_id ?? 0;
    fields.clanId.value = data.flags.clan_id ?? 0;
    mobType.value = (data.flags.type || 'S').toUpperCase();
    fields.level.value = data.stats.level ?? 1;
    fields.thac0.value = data.stats.thac0 ?? 20;
    fields.armor.value = data.stats.armor ?? 0;
    fields.hpNum.value = data.stats.hp_num ?? 1;
    fields.hpSize.value = data.stats.hp_size ?? 1;
    fields.hpBonus.value = data.stats.hp_bonus ?? 0;
    fields.damNum.value = data.stats.dam_num ?? 1;
    fields.damSize.value = data.stats.dam_size ?? 1;
    fields.damBonus.value = data.stats.dam_bonus ?? 0;
    fields.gold.value = data.stats.gold ?? 0;
    fields.exp.value = data.stats.exp ?? 0;
    fields.position.value = data.stats.position ?? 0;
    fields.defaultPosition.value = data.stats.default_position ?? 0;
    fields.sex.value = data.stats.sex ?? 0;
    especList.innerHTML = '';
    for (const e of data.especs || []) addEspecRow(e.key, e.value);
    triggerList.innerHTML = '';
    for (const t of data.triggers || []) addTriggerRow(t);
    fields.unknownLines.value = (data.unknown_lines || []).join('\\n');
    setEspecVisibility();
    setStatus(`Loaded mob ${data.vnum}`);
  } catch (e) {
    setStatus(`Load failed: ${e.message}`);
  }
}

async function saveMob() {
  const vnum = parseInt(vnumInput.value, 10);
  if (!vnum) return;
  setStatus('Saving...');
  try {
    const payload = {
      strings: {
        keywords: fields.keywords.value,
        short: fields.short.value,
        long: fields.long.value,
        description: fields.description.value,
      },
      unused_strings: [fields.unused1.value, fields.unused2.value, fields.unused3.value],
      flags: {
        act_flags: fields.actFlags.value,
        aff_flags: fields.affFlags.value,
        alignment: parseInt(fields.alignment.value, 10) || 0,
        reserved1: parseInt(fields.reserved1.value, 10) || 0,
        reserved2: parseInt(fields.reserved2.value, 10) || 0,
        reserved3: parseInt(fields.reserved3.value, 10) || 0,
        master_id: parseInt(fields.masterId.value, 10) || 0,
        clan_id: parseInt(fields.clanId.value, 10) || 0,
        type: mobType.value,
      },
      stats: {
        level: parseInt(fields.level.value, 10) || 1,
        thac0: parseInt(fields.thac0.value, 10) || 20,
        armor: parseInt(fields.armor.value, 10) || 0,
        hp_num: parseInt(fields.hpNum.value, 10) || 1,
        hp_size: parseInt(fields.hpSize.value, 10) || 1,
        hp_bonus: parseInt(fields.hpBonus.value, 10) || 0,
        dam_num: parseInt(fields.damNum.value, 10) || 1,
        dam_size: parseInt(fields.damSize.value, 10) || 1,
        dam_bonus: parseInt(fields.damBonus.value, 10) || 0,
        gold: parseInt(fields.gold.value, 10) || 0,
        exp: parseInt(fields.exp.value, 10) || 0,
        position: parseInt(fields.position.value, 10) || 0,
        default_position: parseInt(fields.defaultPosition.value, 10) || 0,
        sex: parseInt(fields.sex.value, 10) || 0,
      },
      especs: collectEspecs(),
      triggers: collectTriggers(),
      unknown_lines: fields.unknownLines.value.split('\\n').map(l => l.trimEnd()).filter(l => l),
    };
    const res = await fetchJson(`/api/mob?vnum=${vnum}`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    setStatus(res.message || 'Saved.');
  } catch (e) {
    setStatus(`Save failed: ${e.message}`);
  }
}

loadBtn.addEventListener('click', loadMob);
saveBtn.addEventListener('click', saveMob);
mobType.addEventListener('change', setEspecVisibility);
document.getElementById('addEspec').addEventListener('click', () => addEspecRow());
document.getElementById('addTrigger').addEventListener('click', () => addTriggerRow());
mobSearchBtn.addEventListener('click', searchMobs);
mobSearchInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') searchMobs();
});

const params = new URLSearchParams(location.search);
if (params.get('vnum')) {
  vnumInput.value = params.get('vnum');
  loadMob();
}
</script>
</body>
</html>
"""

OBJ_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Object Editor</title>
  <style>
    body { margin: 0; font-family: monospace; background: #101417; color: #e6e6e6; }
    header { padding: 10px 14px; border-bottom: 1px solid #2a2f35; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
    main { padding: 12px 14px; }
    .btn { background: #1b2230; color: #e6e6e6; border: 1px solid #2a2f35; padding: 6px 10px; cursor: pointer; }
    input, textarea, select { background: #0f141a; color: #e6e6e6; border: 1px solid #2a2f35; padding: 4px; }
    textarea { width: 100%; min-height: 90px; }
    .box { border: 1px solid #2a2f35; padding: 10px; margin-bottom: 12px; }
    .meta { font-size: 12px; opacity: 0.8; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; }
    .field label { display: block; font-size: 12px; opacity: 0.85; margin-bottom: 4px; }
    .row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
    .list-row { display: grid; grid-template-columns: 1fr 1fr auto; gap: 8px; align-items: center; margin-bottom: 6px; }
    .list-row input, .list-row textarea { width: 100%; }
    .list-row .btn { padding: 4px 8px; }
    .section-title { font-size: 13px; text-transform: uppercase; letter-spacing: 0.08em; opacity: 0.7; margin-bottom: 8px; }
    .search-results { border: 1px solid #2a2f35; background: #0f141a; max-height: 180px; overflow: auto; width: 100%; }
    .search-results button { width: 100%; text-align: left; background: transparent; color: #e6e6e6; border: none; padding: 6px 8px; cursor: pointer; }
    .search-results button:hover { background: #1b2230; }
  </style>
</head>
<body>
  <header>
    <div class="row">
      <label>Object VNUM</label>
      <input id="vnumInput" type="number" style="width:120px">
      <button id="loadBtn" class="btn">Load</button>
    </div>
    <div class="row">
      <label>Search</label>
      <input id="objSearch" type="text" placeholder="Search object name/desc" style="width:260px">
      <button id="objSearchBtn" class="btn">Find</button>
    </div>
    <div id="objSearchResults" class="search-results" style="display:none;"></div>
    <a class="btn" href="/help" target="_blank">Help</a>
    <div class="meta" id="status">Idle</div>
    <button id="saveBtn" class="btn">Save</button>
  </header>
  <main>
    <div class="box">
      <div class="section-title">Strings</div>
      <div class="grid">
        <div class="field"><label>Keywords</label><input id="keywords" type="text"></div>
        <div class="field"><label>Short description</label><input id="shortDesc" type="text"></div>
        <div class="field"><label>Long description</label><input id="longDesc" type="text"></div>
      </div>
      <div class="field" style="margin-top:8px;">
        <label>Action description</label>
        <textarea id="actionDesc"></textarea>
      </div>
    </div>
    <div class="box">
      <div class="section-title">Type and Flags</div>
      <div class="grid">
        <div class="field">
          <label>Type</label>
          <select id="objType"></select>
        </div>
        <div class="field">
          <label>Extra flags (string)</label>
          <input id="extraFlags" type="text">
          <div class="meta">Flags use letters (e.g., "ab"). Numeric values are converted to letters on blur.</div>
          <div id="extraFlagsList" class="flag-list"></div>
        </div>
        <div class="field">
          <label>Wear flags (string)</label>
          <input id="wearFlags" type="text">
          <div class="meta">Flags use letters (e.g., "ac"). Numeric values are converted to letters on blur.</div>
          <div id="wearFlagsList" class="flag-list"></div>
        </div>
      </div>
    </div>
    <div class="box">
      <div class="section-title">Values</div>
      <div class="grid">
        <div class="field"><label>Value 0</label><input id="value0" type="number"></div>
        <div class="field"><label>Value 1</label><input id="value1" type="number"></div>
        <div class="field"><label>Value 2</label><input id="value2" type="number"></div>
        <div class="field"><label>Value 3</label><input id="value3" type="number"></div>
        <div class="field">
          <label><input id="hasSlots" type="checkbox"> Include slots</label>
          <div class="row" style="margin-top:6px;">
            <input id="currSlots" type="number" placeholder="Current">
            <input id="totalSlots" type="number" placeholder="Total">
          </div>
        </div>
      </div>
    </div>
    <div class="box">
      <div class="section-title">Costs and Weight</div>
      <div class="grid">
        <div class="field"><label>Weight</label><input id="weight" type="number"></div>
        <div class="field"><label>Cost</label><input id="cost" type="number"></div>
        <div class="field"><label>Cost per day</label><input id="costPerDay" type="number"></div>
        <div class="field">
          <label><input id="hasMinLevel" type="checkbox"> Include min level</label>
          <input id="minLevel" type="number">
        </div>
        <div class="field">
          <label><input id="hasMaterial" type="checkbox"> Include material</label>
          <div class="row" style="margin-top:6px;">
            <select id="materialType"></select>
            <input id="materialNum" type="number" placeholder="Number">
          </div>
        </div>
      </div>
    </div>
    <div class="box">
      <div class="section-title">Extra Descriptions</div>
      <div id="extraList"></div>
      <button id="addExtra" class="btn">Add Extra</button>
    </div>
    <div class="box">
      <div class="section-title">Affects</div>
      <div class="meta">Location uses APPLY_* values from the game.</div>
      <div id="affectList" class="affect-list"></div>
      <button id="addAffect" class="btn">Add Affect</button>
    </div>
    <div class="box">
      <div class="section-title">Custom Bitvector</div>
      <label class="meta"><input id="hasBitvector" type="checkbox"> Include bitvector (4 fields)</label>
      <div class="grid" style="margin-top:6px;">
        <div class="field"><label>Bitvector 0</label><input id="bit0" type="number"></div>
        <div class="field"><label>Bitvector 1</label><input id="bit1" type="number"></div>
        <div class="field"><label>Bitvector 2</label><input id="bit2" type="number"></div>
        <div class="field"><label>Bitvector 3</label><input id="bit3" type="number"></div>
      </div>
    </div>
    <div class="box">
      <div class="section-title">Triggers</div>
      <div id="triggerList"></div>
      <button id="addTrigger" class="btn">Add Trigger</button>
    </div>
    <div class="box">
      <div class="section-title">Other Lines (Rare)</div>
      <div class="meta">Preserved for unusual data lines after triggers.</div>
      <textarea id="unknownLines"></textarea>
    </div>
  </main>
<script>
const statusEl = document.getElementById('status');
const vnumInput = document.getElementById('vnumInput');
const loadBtn = document.getElementById('loadBtn');
const saveBtn = document.getElementById('saveBtn');
const extraList = document.getElementById('extraList');
const affectList = document.getElementById('affectList');
const triggerList = document.getElementById('triggerList');
const objSearchInput = document.getElementById('objSearch');
const objSearchBtn = document.getElementById('objSearchBtn');
const objSearchResults = document.getElementById('objSearchResults');
const extraFlagsList = document.getElementById('extraFlagsList');
const wearFlagsList = document.getElementById('wearFlagsList');

const ITEM_TYPES = [
  "UNDEFINED", "LIGHT", "SCROLL", "WAND", "STAFF", "WEAPON", "FIRE WEAPON",
  "MISSILE", "TREASURE", "ARMOR", "POTION", "WORN", "OTHER", "TRASH", "TRAP",
  "CONTAINER", "NOTE", "LIQ CONTAINER", "KEY", "FOOD", "MONEY", "PEN", "BOAT",
  "FOUNTAIN", "FLY", "PORTAL", "THROW", "GRENADE", "BOW", "SLING", "CROSSBOW",
  "BOLT", "ARROW", "ROCK", "RICEVUTA_STALLA", "CHIAVE RENTABILE",
  "CIBO PER CAVALLI", "MARTELLO", "SEGA", "PICCA", "SCUOIATORE", "FALCE",
  "ASCIA", "MARTELLETTO", "PIETRA", "ALBERO", "MINERALE", "NATURALE",
  "METALLO GREZZO (R)", "TRONCO (R)", "PIETRA GREZZA (R)", "PELLE GREZZA (R)",
  "PRODOTTO NATURALE (R)", "LINGOTTO (R)", "TRAVE LEGNO (R)",
  "PIETRA PULITA (R)", "PELLE PULITA (R)", "CIBO CUOCERE (R)",
  "TRAVE COSTRUZIONE (R)", "ROCCIA SQUADRATA (R)",
  "MARTELLO COSTRUZIONE", "ASSE LEGNO (R)", "ROCCIA", "ROCCIA GREZZA (R)",
  "GEMMA (R)", "TALISMANO DRAGO", "ERBA", "MANETTE", "MANGANELLO", "BENDA",
  "PICCOZZA", "ERBA GREZZA (R)", "ERBA PULITA (R)", "BOCCETTA ALCH.",
  "TRITAERBE", "BAVAGLIO", "CANNA DA PESCA", "STRUM. CUCINA", "MATTARELLO",
  "STRUM. RIPULITURA", "PASTELLA (R)", "PELLE (R)", "ARMA DA CACCIA",
  "STR. CONCERIA", "ATTO NOTARILE", "PORTA", "CONTRATTO VEND.",
  "TRAPPOLA", "VESTE", "RELIQUIA", "LIBRO MAGICO WAND",
  "LIBRO MAGICO STAFF", "WEAPON 2 HANDS", "TISANA CALDA",
  "TISANA RAFFREDDATA", "BENDE UNTE", "POLVERE"
];

const WEAR_BITS = [
  "TAKE", "FINGER", "NECK", "BODY", "HEAD", "LEGS", "FEET", "HANDS", "ARMS",
  "SHIELD", "ABOUT", "WAIST", "WRIST", "WIELD", "HOLD", "LOBSX", "SPALLE",
  "POLSI", "OCCHI", "BOCCA", "ALTRO", "HANG", "VESTE", "RELIQUIA"
];

const EXTRA_BITS = [
  "GLOW", "HUM", "NORENT", "NODONATE", "NOINVIS", "INVISIBLE", "MAGIC",
  "NODROP", "BLESS", "NOGOOD", "NOEVIL", "NONEUTRAL", "NOPANDION",
  "NOCYRINIC", "NOALCIONE", "NOGENIDIAN", "NOSELL", "NOPELOI",
  "LIVE_GRENADE", "NOLOCATE", "NO_5_LIV", "NO_10_LIV", "NO_20_LIV",
  "NO_25_LIV", "NO_30_LIV", "NO_40_LIV", "RESTRING (R)", "CORPSE (R)",
  "FORGIATO", "AFFILATO", "RINOM_ALIAS", "RINOM_NAME", "RINOM_DESCR",
  "NO_IDENT", "QUEST"
];

const MATERIAL_TYPES = [
  "Non Specificato",
  "Metallo",
  "Legno",
  "Gemma",
  "Roccia",
  "Pelle e affini",
  "Naturale",
  "Erbe medicinali"
];

const APPLY_TYPES = [
  'NONE', 'STR', 'DEX', 'INT', 'WIS', 'CON', 'CHA', 'CLASS', 'LEVEL', 'AGE',
  'CHAR_WEIGHT', 'CHAR_HEIGHT', 'MAXMANA', 'MAXHIT', 'MAXMOVE', 'GOLD', 'EXP',
  'ARMOR', 'HITROLL', 'DAMROLL', 'SAVING_PARA', 'SAVING_ROD', 'SAVING_PETRI',
  'SAVING_BREATH', 'SAVING_SPELL', 'HIT_REGEN', 'MANA_REGEN', 'RES_FUOCO',
  'RES_GHIACCIO', 'RES_ELETTRICITA', 'RES_ACIDO', 'RES_OSCURITA', 'RES_CAOS',
  'RES_ORDINE', 'RES_LUCE', 'RES_FISICO'
];

const FLAG_CHARS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ';

function flagIndex(ch) {
  return FLAG_CHARS.indexOf(ch);
}

function indexesToFlags(idxs) {
  return idxs.map(i => FLAG_CHARS[i]).filter(Boolean).join('');
}

function flagsToIndexes(flags) {
  const out = [];
  for (const ch of flags) {
    const idx = flagIndex(ch);
    if (idx >= 0) out.push(idx);
  }
  return out;
}

function flagIntToLetters(value) {
  let num;
  try {
    num = BigInt(value);
  } catch {
    return '';
  }
  let out = '';
  for (let i = 0; i < FLAG_CHARS.length; i++) {
    if (num & (1n << BigInt(i))) out += FLAG_CHARS[i];
  }
  return out;
}

function normalizeFlagInput(inputEl, listContainer) {
  const raw = inputEl.value.trim();
  if (/^[0-9]+$/.test(raw)) {
    inputEl.value = flagIntToLetters(raw);
  }
  syncFlagsToChecks(listContainer, inputEl);
}

function buildSelectOptions(selectEl, labels) {
  selectEl.innerHTML = '';
  labels.forEach((label, idx) => {
    const opt = document.createElement('option');
    opt.value = idx;
    opt.textContent = `${idx} ${label}`;
    selectEl.appendChild(opt);
  });
}

function selectWithFallback(selectEl, value, labels) {
  const idx = parseInt(value, 10);
  if (!Number.isFinite(idx)) return;
  if (idx >= 0 && idx < labels.length) {
    selectEl.value = String(idx);
    return;
  }
  const opt = document.createElement('option');
  opt.value = String(idx);
  opt.textContent = `${idx} (custom)`;
  selectEl.appendChild(opt);
  selectEl.value = String(idx);
}

function buildFlagList(container, labels, inputEl) {
  container.innerHTML = '';
  labels.forEach((label, idx) => {
    const wrap = document.createElement('label');
    wrap.className = 'flag-item';
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.dataset.idx = idx;
    const text = document.createElement('span');
    const flagLabel = FLAG_CHARS[idx] || idx;
    text.textContent = `${flagLabel} ${label}`;
    cb.addEventListener('change', () => {
      const selected = [...container.querySelectorAll('input[type="checkbox"]')]
        .filter(x => x.checked)
        .map(x => parseInt(x.dataset.idx, 10));
      inputEl.value = indexesToFlags(selected);
    });
    wrap.appendChild(cb);
    wrap.appendChild(text);
    container.appendChild(wrap);
  });
}

function syncFlagsToChecks(container, inputEl) {
  const idxs = new Set(flagsToIndexes(inputEl.value));
  for (const cb of container.querySelectorAll('input[type="checkbox"]')) {
    const idx = parseInt(cb.dataset.idx, 10);
    cb.checked = idxs.has(idx);
  }
}

const fields = {
  keywords: document.getElementById('keywords'),
  short: document.getElementById('shortDesc'),
  long: document.getElementById('longDesc'),
  action: document.getElementById('actionDesc'),
  objType: document.getElementById('objType'),
  extraFlags: document.getElementById('extraFlags'),
  wearFlags: document.getElementById('wearFlags'),
  value0: document.getElementById('value0'),
  value1: document.getElementById('value1'),
  value2: document.getElementById('value2'),
  value3: document.getElementById('value3'),
  hasSlots: document.getElementById('hasSlots'),
  currSlots: document.getElementById('currSlots'),
  totalSlots: document.getElementById('totalSlots'),
  weight: document.getElementById('weight'),
  cost: document.getElementById('cost'),
  costPerDay: document.getElementById('costPerDay'),
  hasMinLevel: document.getElementById('hasMinLevel'),
  minLevel: document.getElementById('minLevel'),
  hasMaterial: document.getElementById('hasMaterial'),
  materialType: document.getElementById('materialType'),
  materialNum: document.getElementById('materialNum'),
  hasBitvector: document.getElementById('hasBitvector'),
  bit0: document.getElementById('bit0'),
  bit1: document.getElementById('bit1'),
  bit2: document.getElementById('bit2'),
  bit3: document.getElementById('bit3'),
  unknownLines: document.getElementById('unknownLines'),
};

function setStatus(msg) { statusEl.textContent = msg; }
function fetchJson(url, opts) {
  return fetch(url, opts).then(r =>
    r.json().then(data => {
      if (!r.ok) throw new Error(data.error || r.statusText);
      return data;
    })
  );
}

function renderSearchResults(container, results, onSelect) {
  container.innerHTML = '';
  if (!results.length) {
    container.style.display = 'none';
    return;
  }
  for (const r of results) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = `#${r.vnum} ${r.name || ''}`.trim();
    btn.addEventListener('click', () => onSelect(r));
    container.appendChild(btn);
  }
  container.style.display = 'block';
}

async function searchObjects() {
  const q = objSearchInput.value.trim();
  if (!q) return;
  setStatus('Searching objects...');
  try {
    const data = await fetchJson(`/api/search_obj?q=${encodeURIComponent(q)}`);
    renderSearchResults(objSearchResults, data.results || [], (r) => {
      objSearchResults.style.display = 'none';
      vnumInput.value = r.vnum;
      loadObj();
    });
    setStatus(`Found ${data.results.length} objects`);
  } catch (e) {
    setStatus(`Search failed: ${e.message}`);
  }
}

function toggleSlots() {
  const enabled = fields.hasSlots.checked;
  fields.currSlots.disabled = !enabled;
  fields.totalSlots.disabled = !enabled;
}

function toggleMinLevel() {
  const enabled = fields.hasMinLevel.checked;
  fields.minLevel.disabled = !enabled;
  if (!enabled) {
    fields.hasMaterial.checked = false;
    toggleMaterial();
  }
}

function toggleMaterial() {
  const enabled = fields.hasMaterial.checked;
  if (enabled && !fields.hasMinLevel.checked) {
    fields.hasMinLevel.checked = true;
    fields.minLevel.disabled = false;
  }
  fields.materialType.disabled = !enabled;
  fields.materialNum.disabled = !enabled;
}

function toggleBitvector() {
  const enabled = fields.hasBitvector.checked;
  fields.bit0.disabled = !enabled;
  fields.bit1.disabled = !enabled;
  fields.bit2.disabled = !enabled;
  fields.bit3.disabled = !enabled;
}

function addExtraRow(keyword = '', description = '') {
  const row = document.createElement('div');
  row.className = 'list-row';
  row.innerHTML = `
    <input class="extra-key" placeholder="Keyword" value="">
    <textarea class="extra-desc" placeholder="Description"></textarea>
    <button class="btn">Remove</button>
  `;
  row.querySelector('.extra-key').value = keyword;
  row.querySelector('.extra-desc').value = description;
  row.querySelector('button').addEventListener('click', () => row.remove());
  extraList.appendChild(row);
}

function addAffectRow(location = '', modifier = '') {
  const row = document.createElement('div');
  row.className = 'list-row';
  const locSelect = document.createElement('select');
  locSelect.className = 'affect-loc';
  for (let i = 0; i < APPLY_TYPES.length; i++) {
    const opt = document.createElement('option');
    opt.value = i;
    opt.textContent = `${i} ${APPLY_TYPES[i]}`;
    locSelect.appendChild(opt);
  }
  locSelect.value = location !== '' ? location : 0;
  const modInput = document.createElement('input');
  modInput.className = 'affect-mod';
  modInput.type = 'number';
  modInput.placeholder = 'Modifier';
  modInput.value = modifier;
  const hint = document.createElement('div');
  hint.className = 'affect-hint';
  const removeBtn = document.createElement('button');
  removeBtn.className = 'btn';
  removeBtn.textContent = 'Remove';
  removeBtn.addEventListener('click', () => row.remove());
  row.appendChild(locSelect);
  row.appendChild(modInput);
  row.appendChild(hint);
  row.appendChild(removeBtn);
  affectList.appendChild(row);

  const updateHint = () => {
    const loc = parseInt(locSelect.value, 10) || 0;
    const mod = parseInt(modInput.value, 10) || 0;
    let text = '';
    if (mod === 0) {
      text = 'Modifier is 0 (no effect).';
    } else if (loc === 17 || (loc >= 20 && loc <= 24)) {
      text = mod < 0 ? 'Bonus (lower is better).' : 'Penalty (higher is worse).';
    } else {
      text = mod > 0 ? 'Bonus (higher is better).' : 'Penalty (lower is worse).';
    }
    hint.textContent = text;
  };
  locSelect.addEventListener('change', updateHint);
  modInput.addEventListener('input', updateHint);
  updateHint();
}

function addTriggerRow(value = '') {
  const row = document.createElement('div');
  row.className = 'list-row';
  row.innerHTML = `
    <input class="trigger-val" placeholder="Trigger VNUM" type="number" value="">
    <div></div>
    <button class="btn">Remove</button>
  `;
  row.querySelector('.trigger-val').value = value;
  row.querySelector('button').addEventListener('click', () => row.remove());
  triggerList.appendChild(row);
}

function collectExtras() {
  return [...extraList.querySelectorAll('.list-row')].map(row => ({
    keyword: row.querySelector('.extra-key').value,
    description: row.querySelector('.extra-desc').value,
  }));
}

function collectAffects() {
  return [...affectList.querySelectorAll('.list-row')].map(row => ({
    location: parseInt(row.querySelector('.affect-loc').value, 10) || 0,
    modifier: parseInt(row.querySelector('.affect-mod').value, 10) || 0,
  }));
}

function collectTriggers() {
  return [...triggerList.querySelectorAll('.list-row')].map(row =>
    parseInt(row.querySelector('.trigger-val').value, 10) || 0
  ).filter(v => v);
}

buildSelectOptions(fields.objType, ITEM_TYPES);
buildSelectOptions(fields.materialType, MATERIAL_TYPES);
buildFlagList(extraFlagsList, EXTRA_BITS, fields.extraFlags);
buildFlagList(wearFlagsList, WEAR_BITS, fields.wearFlags);
fields.extraFlags.addEventListener('input', () => syncFlagsToChecks(extraFlagsList, fields.extraFlags));
fields.wearFlags.addEventListener('input', () => syncFlagsToChecks(wearFlagsList, fields.wearFlags));
fields.extraFlags.addEventListener('blur', () => normalizeFlagInput(fields.extraFlags, extraFlagsList));
fields.wearFlags.addEventListener('blur', () => normalizeFlagInput(fields.wearFlags, wearFlagsList));

async function loadObj() {
  const vnum = parseInt(vnumInput.value, 10);
  if (!vnum) return;
  setStatus('Loading...');
  try {
    const data = await fetchJson(`/api/obj?vnum=${vnum}`);
    fields.keywords.value = data.strings.keywords || '';
    fields.short.value = data.strings.short || '';
    fields.long.value = data.strings.description || '';
    fields.action.value = data.strings.action || '';
    selectWithFallback(fields.objType, data.flags.type ?? 0, ITEM_TYPES);
    fields.extraFlags.value = data.flags.extra_flags || '';
    fields.wearFlags.value = data.flags.wear_flags || '';
    normalizeFlagInput(fields.extraFlags, extraFlagsList);
    normalizeFlagInput(fields.wearFlags, wearFlagsList);
    fields.value0.value = data.values.value0 ?? 0;
    fields.value1.value = data.values.value1 ?? 0;
    fields.value2.value = data.values.value2 ?? 0;
    fields.value3.value = data.values.value3 ?? 0;
    fields.hasSlots.checked = !!data.values.has_slots;
    fields.currSlots.value = data.values.curr_slots ?? 0;
    fields.totalSlots.value = data.values.total_slots ?? 0;
    fields.weight.value = data.costs.weight ?? 0;
    fields.cost.value = data.costs.cost ?? 0;
    fields.costPerDay.value = data.costs.cost_per_day ?? 0;
    fields.hasMinLevel.checked = !!data.costs.has_min_level;
    fields.minLevel.value = data.costs.min_level ?? -1;
    fields.hasMaterial.checked = !!data.costs.has_material;
    selectWithFallback(fields.materialType, data.costs.material_type ?? 0, MATERIAL_TYPES);
    fields.materialNum.value = data.costs.material_num ?? 0;
    fields.hasBitvector.checked = !!data.bitvector;
    fields.bit0.value = data.bitvector ? data.bitvector[0] : 0;
    fields.bit1.value = data.bitvector ? data.bitvector[1] : 0;
    fields.bit2.value = data.bitvector ? data.bitvector[2] : 0;
    fields.bit3.value = data.bitvector ? data.bitvector[3] : 0;
    extraList.innerHTML = '';
    for (const e of data.extras || []) addExtraRow(e.keyword, e.description);
    affectList.innerHTML = '';
    for (const a of data.affects || []) addAffectRow(a.location, a.modifier);
    triggerList.innerHTML = '';
    for (const t of data.triggers || []) addTriggerRow(t);
    fields.unknownLines.value = (data.unknown_lines || []).join('\\n');
    toggleSlots();
    toggleMinLevel();
    toggleMaterial();
    toggleBitvector();
    setStatus(`Loaded object ${data.vnum}`);
  } catch (e) {
    setStatus(`Load failed: ${e.message}`);
  }
}

async function saveObj() {
  const vnum = parseInt(vnumInput.value, 10);
  if (!vnum) return;
  setStatus('Saving...');
  try {
    const payload = {
      strings: {
        keywords: fields.keywords.value,
        short: fields.short.value,
        description: fields.long.value,
        action: fields.action.value,
      },
      flags: {
        type: parseInt(fields.objType.value, 10) || 0,
        extra_flags: fields.extraFlags.value,
        wear_flags: fields.wearFlags.value,
      },
      values: {
        value0: parseInt(fields.value0.value, 10) || 0,
        value1: parseInt(fields.value1.value, 10) || 0,
        value2: parseInt(fields.value2.value, 10) || 0,
        value3: parseInt(fields.value3.value, 10) || 0,
        curr_slots: parseInt(fields.currSlots.value, 10) || 0,
        total_slots: parseInt(fields.totalSlots.value, 10) || 0,
        has_slots: fields.hasSlots.checked,
      },
      costs: {
        weight: parseInt(fields.weight.value, 10) || 0,
        cost: parseInt(fields.cost.value, 10) || 0,
        cost_per_day: parseInt(fields.costPerDay.value, 10) || 0,
        min_level: parseInt(fields.minLevel.value, 10) || -1,
        material_type: parseInt(fields.materialType.value, 10) || 0,
        material_num: parseInt(fields.materialNum.value, 10) || 0,
        has_min_level: fields.hasMinLevel.checked,
        has_material: fields.hasMaterial.checked,
      },
      extras: collectExtras(),
      affects: collectAffects(),
      bitvector: fields.hasBitvector.checked ? [
        parseInt(fields.bit0.value, 10) || 0,
        parseInt(fields.bit1.value, 10) || 0,
        parseInt(fields.bit2.value, 10) || 0,
        parseInt(fields.bit3.value, 10) || 0,
      ] : null,
      triggers: collectTriggers(),
      unknown_lines: fields.unknownLines.value.split('\\n').map(l => l.trimEnd()).filter(l => l),
    };
    const res = await fetchJson(`/api/obj?vnum=${vnum}`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    setStatus(res.message || 'Saved.');
  } catch (e) {
    setStatus(`Save failed: ${e.message}`);
  }
}

loadBtn.addEventListener('click', loadObj);
saveBtn.addEventListener('click', saveObj);
fields.hasSlots.addEventListener('change', toggleSlots);
fields.hasMinLevel.addEventListener('change', toggleMinLevel);
fields.hasMaterial.addEventListener('change', toggleMaterial);
fields.hasBitvector.addEventListener('change', toggleBitvector);
document.getElementById('addExtra').addEventListener('click', () => addExtraRow());
document.getElementById('addAffect').addEventListener('click', () => addAffectRow());
document.getElementById('addTrigger').addEventListener('click', () => addTriggerRow());
objSearchBtn.addEventListener('click', searchObjects);
objSearchInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') searchObjects();
});

const params = new URLSearchParams(location.search);
if (params.get('vnum')) {
  vnumInput.value = params.get('vnum');
  loadObj();
}
</script>
</body>
</html>
"""

ZONE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Zone Map</title>
  <style>
    body { margin: 0; font-family: monospace; background: #101417; color: #e6e6e6; }
    header { padding: 10px 14px; border-bottom: 1px solid #2a2f35; display: flex; gap: 12px; align-items: center; }
    main { height: calc(100vh - 48px); overflow: auto; }
    .btn { background: #1b2230; color: #e6e6e6; border: 1px solid #2a2f35; padding: 6px 10px; cursor: pointer; }
    input { background: #0f141a; color: #e6e6e6; border: 1px solid #2a2f35; padding: 4px; }
    canvas { image-rendering: pixelated; background: #0c0f12; }
    .meta { font-size: 12px; opacity: 0.8; }
  </style>
</head>
<body>
  <header>
    <label>Zone</label>
    <input id="zoneInput" type="number" style="width:120px">
    <button id="loadBtn" class="btn">Load</button>
    <label>Zoom</label>
    <input id="cellSize" type="number" min="8" max="60" value="20" style="width:60px">
    <a class="btn" href="/help" target="_blank">Help</a>
    <div class="meta" id="status">Idle</div>
  </header>
  <main>
    <canvas id="zoneCanvas"></canvas>
  </main>
<script>
const zoneInput = document.getElementById('zoneInput');
const loadBtn = document.getElementById('loadBtn');
const cellSize = document.getElementById('cellSize');
const statusEl = document.getElementById('status');
const canvas = document.getElementById('zoneCanvas');
const ctx = canvas.getContext('2d');
let roomIndex = [];

function setStatus(msg) { statusEl.textContent = msg; }

function fetchJson(url, opts) {
  return fetch(url, opts).then(r =>
    r.json().then(data => {
      if (!r.ok) throw new Error(data.error || r.statusText);
      return data;
    })
  );
}

function drawGrid(data) {
  const size = parseInt(cellSize.value, 10) || 20;
  const rooms = data.rooms || [];
  const edges = data.edges || [];
  const external = data.external || [];
  if (!rooms.length) {
    setStatus('No rooms found.');
    return;
  }
  const maxX = Math.max(...rooms.map(r => r.x));
  const maxY = Math.max(...rooms.map(r => r.y));
  canvas.width = (maxX + 1) * size;
  canvas.height = (maxY + 1) * size;
  ctx.fillStyle = '#0c0f12';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  roomIndex = rooms;
  ctx.strokeStyle = '#3a4a5a';
  ctx.lineWidth = 2;
  const dirVec = {0:[0,-1],1:[1,0],2:[0,1],3:[-1,0]};
  for (const e of edges) {
    const x1 = e.x1 * size + size / 2;
    const y1 = e.y1 * size + size / 2;
    const x2 = e.x2 * size + size / 2;
    const y2 = e.y2 * size + size / 2;
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
  }
  if (external.length) {
    ctx.strokeStyle = '#7a5a3a';
    ctx.setLineDash([6, 4]);
    for (const e of external) {
      const x1 = e.x1 * size + size / 2;
      const y1 = e.y1 * size + size / 2;
      let x2 = x1;
      let y2 = y1;
      if (dirVec[e.dir]) {
        x2 = x1 + dirVec[e.dir][0] * size * 0.7;
        y2 = y1 + dirVec[e.dir][1] * size * 0.7;
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
        ctx.fillStyle = '#7a5a3a';
        ctx.beginPath();
        ctx.arc(x2, y2, Math.max(3, size * 0.12), 0, Math.PI * 2);
        ctx.fill();
      }
    }
    ctx.setLineDash([]);
  }
  for (const r of rooms) {
    const x = r.x * size;
    const y = r.y * size;
    ctx.fillStyle = '#1f3b5a';
    ctx.fillRect(x, y, size - 1, size - 1);
    ctx.fillStyle = '#e6e6e6';
    ctx.font = `${Math.max(8, size * 0.4)}px monospace`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(r.vnum, x + size / 2, y + size / 2);
  }
}

loadBtn.addEventListener('click', async () => {
  const zone = parseInt(zoneInput.value, 10);
  if (!zone) return;
  setStatus('Loading...');
  try {
    const data = await fetchJson(`/api/zone_map?zone=${zone}`);
    drawGrid(data);
    setStatus(`Loaded zone ${zone}`);
  } catch (e) {
    setStatus(`Load failed: ${e.message}`);
  }
});

cellSize.addEventListener('change', () => {
  loadBtn.click();
});

canvas.addEventListener('wheel', (evt) => {
  evt.preventDefault();
  const delta = evt.deltaY < 0 ? 2 : -2;
  const current = parseInt(cellSize.value, 10) || 20;
  const next = Math.min(60, Math.max(10, current + delta));
  if (next !== current) {
    cellSize.value = next;
    loadBtn.click();
  }
}, { passive: false });

canvas.addEventListener('click', (evt) => {
  const rect = canvas.getBoundingClientRect();
  const size = parseInt(cellSize.value, 10) || 20;
  const x = Math.floor((evt.clientX - rect.left) / size);
  const y = Math.floor((evt.clientY - rect.top) / size);
  const room = roomIndex.find(r => r.x === x && r.y === y);
  if (room) {
    window.open(`/room?vnum=${room.vnum}`, '_blank');
  }
});

const params = new URLSearchParams(window.location.search);
if (params.get('zone')) {
  zoneInput.value = params.get('zone');
  loadBtn.click();
}
</script>
</body>
</html>
"""

def load_help_html():
    path = os.path.join(ROOT, "doc", "wildweb.md")
    text = read_text(path)
    def esc(s):
        return (s.replace("&", "&amp;")
                 .replace("<", "&lt;")
                 .replace(">", "&gt;"))
    body = []
    in_list = False
    in_code = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("```"):
            if not in_code:
                body.append("<pre>")
                in_code = True
            else:
                body.append("</pre>")
                in_code = False
            continue
        if in_code:
            body.append(esc(line))
            continue
        if line.startswith("## "):
            if in_list:
                body.append("</ul>")
                in_list = False
            body.append(f"<h2>{esc(line[3:])}</h2>")
            continue
        if line.startswith("# "):
            if in_list:
                body.append("</ul>")
                in_list = False
            body.append(f"<h1>{esc(line[2:])}</h1>")
            continue
        if line.startswith("- "):
            if not in_list:
                body.append("<ul>")
                in_list = True
            body.append(f"<li>{esc(line[2:])}</li>")
            continue
        if not line.strip():
            if in_list:
                body.append("</ul>")
                in_list = False
            body.append("<br>")
            continue
        if in_list:
            body.append("</ul>")
            in_list = False
        body.append(f"<p>{esc(line)}</p>")
    if in_list:
        body.append("</ul>")
    if in_code:
        body.append("</pre>")
    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>World Editor Help</title>
  <style>
    body { margin: 0; font-family: monospace; background: #101417; color: #e6e6e6; }
    main { max-width: 900px; margin: 40px auto; padding: 20px; }
    h1, h2 { color: #e6e6e6; }
    code { background: #0f141a; padding: 2px 4px; border: 1px solid #2a2f35; }
    pre { background: #0f141a; padding: 12px; border: 1px solid #2a2f35; overflow: auto; }
    a { color: #7cc7ff; }
    ul { line-height: 1.5; }
  </style>
</head>
<body>
  <main>
""" + "\n".join(body) + """
  </main>
</body>
</html>
"""
    return html


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, content_type="text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8")

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send(200, HOME_HTML.encode("utf-8"))
            return
        if parsed.path == "/help":
            html = load_help_html()
            self._send(200, html.encode("utf-8"))
            return
        if parsed.path == "/wild":
            self._send(200, HTML.encode("utf-8"))
            return
        if parsed.path == "/mob":
            self._send(200, MOB_HTML.encode("utf-8"))
            return
        if parsed.path == "/obj":
            self._send(200, OBJ_HTML.encode("utf-8"))
            return
        if parsed.path == "/room":
            self._send(200, ROOM_HTML.encode("utf-8"))
            return
        if parsed.path == "/zone":
            self._send(200, ZONE_HTML.encode("utf-8"))
            return
        if parsed.path == "/api/palette":
            self._send_json(200, parse_wild_table())
            return
        if parsed.path == "/api/zones":
            zones = []
            for name in os.listdir(ZON_DIR):
                if not name.endswith(".zon"):
                    continue
                info = parse_zone_file(os.path.join(ZON_DIR, name))
                if not info:
                    continue
                if info["wilderness"] in (1, 2):
                    zones.append(info)
            zones.sort(key=lambda z: z["number"])
            self._send_json(200, zones)
            return
        if parsed.path == "/api/map":
            qs = parse_qs(parsed.query)
            zone = int(qs.get("zone", [0])[0])
            try:
                info, width, height, xoff, yoff, grid = read_map_ids(zone)
            except Exception as e:
                self._send_json(400, {"error": str(e)})
                return
            self._send_json(200, {
                "zone": zone,
                "name": info["name"],
                "wilderness": info["wilderness"],
                "width": width,
                "height": height,
                "x_offset": xoff,
                "y_offset": yoff,
                "grid": grid,
            })
            return
        if parsed.path == "/api/room":
            qs = parse_qs(parsed.query)
            vnum = int(qs.get("vnum", [0])[0])
            try:
                room = load_room_by_vnum(vnum)
                if not room:
                    # fallback: check if this is wild/miniwild and compute from map
                    zone = find_zone_for_vnum(vnum)
                    if not zone or zone["wilderness"] not in (1, 2):
                        raise ValueError("Room not found.")
                    info, width, height, xoff, yoff, grid = read_map_ids(zone["number"])
                    if zone["wilderness"] == 1:
                        vy = (vnum - 1000000) // 1000
                        vx = (vnum - 1000000) % 1000
                    else:
                        vy = (vnum - (zone["number"] * 100)) // 100
                        vx = (vnum - (zone["number"] * 100)) % 100
                    gx = vx - xoff
                    gy = vy - yoff
                    if not (0 <= gx < width and 0 <= gy < height):
                        raise ValueError("Room not found.")
                    wild_id = grid[gy][gx]
                    wild_table = parse_wild_table_full()
                    meta = wild_table.get(wild_id, {})
                    room = {
                        "vnum": vnum,
                        "name": meta.get("name", "Unknown"),
                        "description": meta.get("description", ""),
                        "room_flags": meta.get("room_flags", 0),
                        "sector_type": meta.get("sector_type", 0),
                        "zone": zone["number"],
                        "zone_name": zone["name"],
                        "zone_wilderness": zone["wilderness"],
                        "exits": [],
                        "extras": [],
                        "spawns": list_room_spawns(vnum),
                        "resets": list_room_resets(vnum),
                        "readonly": True,
                    }
                else:
                    zone = find_zone_for_vnum(vnum)
                    room["zone_name"] = zone["name"] if zone else ""
                    room["zone_wilderness"] = zone["wilderness"] if zone else 0
                    room["spawns"] = list_room_spawns(vnum)
                    room["resets"] = list_room_resets(vnum)
                self._send_json(200, room)
            except Exception as e:
                self._send_json(400, {"error": str(e)})
            return
        if parsed.path == "/api/mob":
            qs = parse_qs(parsed.query)
            vnum = int(qs.get("vnum", [0])[0])
            try:
                mob = load_mob_by_vnum(vnum)
                if not mob:
                    raise ValueError("Mob not found.")
                self._send_json(200, mob)
            except Exception as e:
                self._send_json(400, {"error": str(e)})
            return
        if parsed.path == "/api/obj":
            qs = parse_qs(parsed.query)
            vnum = int(qs.get("vnum", [0])[0])
            try:
                obj = load_obj_by_vnum(vnum)
                if not obj:
                    raise ValueError("Object not found.")
                self._send_json(200, obj)
            except Exception as e:
                self._send_json(400, {"error": str(e)})
            return
        if parsed.path == "/api/search_mob":
            qs = parse_qs(parsed.query)
            q = qs.get("q", [""])[0]
            limit = int(qs.get("limit", [50])[0])
            try:
                results = search_mobs(q, limit=limit)
                self._send_json(200, {"results": results})
            except Exception as e:
                self._send_json(400, {"error": str(e)})
            return
        if parsed.path == "/api/search_obj":
            qs = parse_qs(parsed.query)
            q = qs.get("q", [""])[0]
            limit = int(qs.get("limit", [50])[0])
            try:
                results = search_objects(q, limit=limit)
                self._send_json(200, {"results": results})
            except Exception as e:
                self._send_json(400, {"error": str(e)})
            return
        if parsed.path == "/api/search_room":
            qs = parse_qs(parsed.query)
            q = qs.get("q", [""])[0]
            limit = int(qs.get("limit", [50])[0])
            try:
                results = search_rooms(q, limit=limit)
                self._send_json(200, {"results": results})
            except Exception as e:
                self._send_json(400, {"error": str(e)})
            return
        if parsed.path == "/api/search_zone":
            qs = parse_qs(parsed.query)
            q = qs.get("q", [""])[0]
            limit = int(qs.get("limit", [50])[0])
            try:
                results = search_zones(q, limit=limit)
                self._send_json(200, {"results": results})
            except Exception as e:
                self._send_json(400, {"error": str(e)})
            return
        if parsed.path == "/api/zone_info":
            qs = parse_qs(parsed.query)
            zone = int(qs.get("zone", [0])[0])
            try:
                info = parse_zone_file(os.path.join(ZON_DIR, f"{zone}.zon"))
                if not info:
                    raise ValueError("Zone not found.")
                self._send_json(200, info)
            except Exception as e:
                self._send_json(400, {"error": str(e)})
            return
        if parsed.path == "/api/zone_first_room":
            qs = parse_qs(parsed.query)
            zone = int(qs.get("zone", [0])[0])
            try:
                vnum, err = zone_first_room(zone)
                if err:
                    raise ValueError(err)
                self._send_json(200, {"vnum": vnum})
            except Exception as e:
                self._send_json(400, {"error": str(e)})
            return
        if parsed.path == "/api/exits":
            qs = parse_qs(parsed.query)
            zone = int(qs.get("zone", [0])[0])
            try:
                exits = load_zone_exits(zone)
            except Exception as e:
                self._send_json(400, {"error": str(e)})
                return
            self._send_json(200, {"zone": zone, "exits": exits})
            return
        if parsed.path == "/api/zone_map":
            qs = parse_qs(parsed.query)
            zone = int(qs.get("zone", [0])[0])
            try:
                info = parse_zone_file(os.path.join(ZON_DIR, f"{zone}.zon"))
                if not info:
                    raise ValueError("Zone not found.")
                if info["wilderness"] != 0:
                    raise ValueError("Zone map view is for non-wild zones only.")
                grid = build_zone_grid(zone)
            except Exception as e:
                self._send_json(400, {"error": str(e)})
                return
            self._send_json(200, grid)
            return
        self._send(404, b"not found", "text/plain; charset=utf-8")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/map":
            if parsed.path == "/api/exit":
                qs = parse_qs(parsed.query)
                zone = int(qs.get("zone", [0])[0])
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except Exception as e:
                    self._send_json(400, {"error": f"Invalid JSON: {e}"})
                    return
                try:
                    vnum = int(payload.get("vnum", 0))
                    dir_num = int(payload.get("dir", -1))
                    to_vnum = payload.get("to_vnum", None)
                    if to_vnum is not None:
                        to_vnum = int(to_vnum)
                    match_to = payload.get("match_to_vnum", None)
                    if match_to is not None:
                        match_to = int(match_to)
                except Exception:
                    self._send_json(400, {"error": "Invalid vnum/dir/to_vnum"})
                    return
                if dir_num < 0 or dir_num > 5:
                    self._send_json(400, {"error": "dir must be 0..5"})
                    return
                try:
                    backup = update_wld_exit(zone, vnum, dir_num, to_vnum, match_to_vnum=match_to)
                except Exception as e:
                    self._send_json(400, {"error": str(e)})
                    return
                msg = "Exit removed." if to_vnum is None else "Exit set."
                if backup:
                    msg += f" Backup: {os.path.basename(backup)}"
                self._send_json(200, {"ok": True, "message": msg})
                return
            if parsed.path == "/api/room":
                qs = parse_qs(parsed.query)
                vnum = int(qs.get("vnum", [0])[0])
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except Exception as e:
                    self._send_json(400, {"error": f"Invalid JSON: {e}"})
                    return
                try:
                    room = load_room_by_vnum(vnum)
                    if not room:
                        raise ValueError("Room not found in editable .wld files.")
                    room["name"] = payload.get("name", room["name"])
                    room["description"] = payload.get("description", room["description"])
                    room["room_flags"] = int(payload.get("room_flags", room["room_flags"]))
                    room["sector_type"] = int(payload.get("sector_type", room["sector_type"]))
                    exits = payload.get("exits", [])
                    new_exits = []
                    for ex in exits:
                        new_exits.append({
                            "dir": int(ex.get("dir", 0)),
                            "keyword": ex.get("keyword", ""),
                            "description": ex.get("description", ""),
                            "exit_info": int(ex.get("exit_info", 0)),
                            "key": int(ex.get("key", 0)),
                            "to_room": int(ex.get("to_room", 0)),
                            "to_room_key": int(ex.get("to_room_key", 0)),
                        })
                    room["exits"] = new_exits
                    backup = save_room_by_vnum(vnum, room)
                except Exception as e:
                    self._send_json(400, {"error": str(e)})
                    return
                self._send_json(200, {"ok": True, "message": f"Room saved. Backup: {os.path.basename(backup)}"})
                return
            if parsed.path == "/api/spawn":
                qs = parse_qs(parsed.query)
                vnum = int(qs.get("vnum", [0])[0])
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except Exception as e:
                    self._send_json(400, {"error": f"Invalid JSON: {e}"})
                    return
                cmd = payload.get("cmd", "")
                obj_vnum = int(payload.get("vnum", 0))
                max_count = int(payload.get("max", 1))
                try:
                    backup = add_room_spawn(vnum, cmd, obj_vnum, max_count)
                except Exception as e:
                    self._send_json(400, {"error": str(e)})
                    return
                self._send_json(200, {"ok": True, "message": f"Spawn added. Backup: {os.path.basename(backup)}"})
                return
            if parsed.path == "/api/mob":
                qs = parse_qs(parsed.query)
                vnum = int(qs.get("vnum", [0])[0])
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except Exception as e:
                    self._send_json(400, {"error": f"Invalid JSON: {e}"})
                    return
                try:
                    backup = save_mob_by_vnum(vnum, payload)
                except Exception as e:
                    self._send_json(400, {"error": str(e)})
                    return
                self._send_json(200, {"ok": True, "message": f"Mob saved. Backup: {os.path.basename(backup)}"})
                return
            if parsed.path == "/api/obj":
                qs = parse_qs(parsed.query)
                vnum = int(qs.get("vnum", [0])[0])
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except Exception as e:
                    self._send_json(400, {"error": f"Invalid JSON: {e}"})
                    return
                try:
                    backup = save_obj_by_vnum(vnum, payload)
                except Exception as e:
                    self._send_json(400, {"error": str(e)})
                    return
                self._send_json(200, {"ok": True, "message": f"Object saved. Backup: {os.path.basename(backup)}"})
                return
            if parsed.path == "/api/reset":
                qs = parse_qs(parsed.query)
                vnum = int(qs.get("vnum", [0])[0])
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except Exception as e:
                    self._send_json(400, {"error": f"Invalid JSON: {e}"})
                    return
                cmd = payload.get("cmd", "")
                if_flag = int(payload.get("if_flag", 0))
                arg1 = int(payload.get("arg1", 0))
                arg2 = int(payload.get("arg2", 0))
                arg3 = int(payload.get("arg3", 0))
                comment = payload.get("comment", "")
                try:
                    backup = append_zone_reset(vnum, cmd, if_flag, arg1, arg2, arg3, comment)
                except Exception as e:
                    self._send_json(400, {"error": str(e)})
                    return
                self._send_json(200, {"ok": True, "message": f"Reset appended. Backup: {os.path.basename(backup)}"})
                return
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        qs = parse_qs(parsed.query)
        zone = int(qs.get("zone", [0])[0])
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as e:
            self._send_json(400, {"error": f"Invalid JSON: {e}"})
            return
        grid = payload.get("grid")
        if not isinstance(grid, list):
            self._send_json(400, {"error": "grid must be a 2D array"})
            return
        try:
            info, width, height, _xoff, _yoff, _old = read_map_ids(zone)
        except Exception as e:
            self._send_json(400, {"error": str(e)})
            return
        if len(grid) != height or any(len(r) != width for r in grid):
            self._send_json(400, {"error": f"wrong grid size, expected {width}x{height}"})
            return
        try:
            new_grid = [[int(v) for v in row] for row in grid]
        except Exception:
            self._send_json(400, {"error": "grid values must be integers"})
            return
        backup = write_map_ids(zone, new_grid)
        self._send_json(200, {"ok": True, "backup": os.path.basename(backup)})


def main():
    parser = argparse.ArgumentParser(description="Wild/Miniwild web editor.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default=8080, type=int)
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), Handler)
    print(f"Serving on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
