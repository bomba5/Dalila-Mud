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

ROOM_INDEX = None
ZONE_INDEX = None


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
        return {"rooms": [], "edges": [], "min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0}
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
    for vnum, (x, y) in coords.items():
        for ex in rooms[vnum]["exits"]:
            if ex["dir"] not in dir_vec:
                continue
            to_room = ex["to_room"]
            if to_room not in coords:
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
    return {"rooms": out, "edges": edges, "min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y}


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
      <a class="btn" href="/room">Edit Room</a>
    </div>
    <div class="meta">Use the room editor for non‑wild zones and zone maps.</div>
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
    </div>
    <div class="row">
      <label>Zoom</label>
      <button id="zoomOut" class="btn">-</button>
      <input id="cellSize" type="number" min="4" max="24" value="10" style="width:60px">
      <button id="zoomIn" class="btn">+</button>
    </div>
    <div class="spacer"></div>
    <div class="status" id="status">Idle</div>
    <button id="saveBtn" class="btn">Save</button>
  </header>
  <main>
    <aside id="exits">
      <div class="meta">Entrances/Exits</div>
      <div class="meta" id="cellMeta">No cell selected.</div>
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
};

const zoneSelect = document.getElementById('zoneSelect');
const loadBtn = document.getElementById('loadBtn');
const saveBtn = document.getElementById('saveBtn');
const statusEl = document.getElementById('status');
const cellSizeEl = document.getElementById('cellSize');
const modePaintBtn = document.getElementById('modePaint');
const modeQueryBtn = document.getElementById('modeQuery');
const zoomInBtn = document.getElementById('zoomIn');
const zoomOutBtn = document.getElementById('zoomOut');
const paletteList = document.getElementById('paletteList');
const paletteMeta = document.getElementById('paletteMeta');
const paletteSearch = document.getElementById('paletteSearch');
const cellMeta = document.getElementById('cellMeta');
const cellClear = document.getElementById('cellClear');
const exitDir = document.getElementById('exitDir');
const exitTarget = document.getElementById('exitTarget');
const exitSet = document.getElementById('exitSet');
const exitDel = document.getElementById('exitDel');
const exitList = document.getElementById('exitList');
const canvas = document.getElementById('map');
const ctx = canvas.getContext('2d');

function setStatus(msg) { statusEl.textContent = msg; }

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
  return `zone ${state.zone} ${state.name} | x=${vx} y=${vy} vnum=${vnum} | ${sym} #${id} ${name}`;
}

function setSelectedCell(pos) {
  state.selected = pos;
  if (!pos) {
    cellMeta.textContent = 'No cell selected.';
    loadExitList();
    drawGrid();
    return;
  }
  cellMeta.textContent = formatCellInfo(pos);
  loadExitList();
  drawGrid();
}

function paintAt(evt) {
  if (state.selectedId === null) return;
  const pos = gridPos(evt);
  if (!pos) return;
  state.grid[pos.y][pos.x] = state.selectedId;
  drawGrid();
  setStatus(formatCellInfo(pos));
  setSelectedCell(pos);
}

canvas.addEventListener('mousedown', (evt) => {
  state.isDown = true;
  if (state.mode === 'query') {
    const pos = gridPos(evt);
    if (pos) {
      setStatus(formatCellInfo(pos));
      setSelectedCell(pos);
    }
  } else {
    paintAt(evt);
  }
});
canvas.addEventListener('mousemove', (evt) => {
  if (state.mode === 'query') return;
  if (state.isDown) paintAt(evt);
});
window.addEventListener('mouseup', () => { state.isDown = false; });

cellSizeEl.addEventListener('change', () => {
  resizeCanvas();
  drawGrid();
});

cellClear.addEventListener('click', () => {
  setSelectedCell(null);
  setStatus('Selection cleared.');
});

function moveSelection(dx, dy) {
  if (!state.selected) {
    setSelectedCell({x: 0, y: 0});
    scrollToCell({x: 0, y: 0});
    return;
  }
  const nx = Math.max(0, Math.min(state.width - 1, state.selected.x + dx));
  const ny = Math.max(0, Math.min(state.height - 1, state.selected.y + dy));
  setSelectedCell({x: nx, y: ny});
  scrollToCell({x: nx, y: ny});
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
});
zoomOutBtn.addEventListener('click', () => {
  const val = Math.max(4, (parseInt(cellSizeEl.value, 10) || 10) - 1);
  cellSizeEl.value = val;
  resizeCanvas();
  drawGrid();
});

function setMode(mode) {
  state.mode = mode;
  if (mode === 'paint') {
    modePaintBtn.disabled = true;
    modeQueryBtn.disabled = false;
  } else {
    modePaintBtn.disabled = false;
    modeQueryBtn.disabled = true;
  }
}

modePaintBtn.addEventListener('click', () => setMode('paint'));
modeQueryBtn.addEventListener('click', () => setMode('query'));

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

async function loadExitList() {
  if (!state.zone) return;
  try {
    const data = await fetchJson(`/api/exits?zone=${state.zone}`);
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
  <title>Room Editor</title>
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
  </style>
</head>
<body>
  <header>
    <div class="row">
      <label>Room VNUM</label>
      <input id="vnumInput" type="number" style="width:120px">
      <button id="loadBtn" class="btn">Load</button>
      <button id="openMapBtn" class="btn">Open Map</button>
    </div>
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
      </div>
      <table id="spawnsTable">
        <thead>
          <tr><th>Cmd</th><th>VNUM</th><th>Max</th></tr>
        </thead>
        <tbody></tbody>
      </table>
      <div class="row">
        <select id="spawnCmd">
          <option value="M">Mob (M)</option>
          <option value="O">Object (O)</option>
        </select>
        <input id="spawnVnum" type="number" placeholder="VNUM" style="width:120px">
        <input id="spawnMax" type="number" placeholder="Max" value="1" style="width:80px">
        <button id="spawnAdd" class="btn">Add Spawn</button>
      </div>
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
        <select id="resetCmd">
          <option value="M">M</option>
          <option value="O">O</option>
          <option value="E">E</option>
          <option value="G">G</option>
          <option value="P">P</option>
          <option value="D">D</option>
          <option value="R">R</option>
        </select>
        <input id="resetIf" type="number" placeholder="if" value="0" style="width:60px">
        <input id="resetA1" type="number" placeholder="arg1" style="width:90px">
        <input id="resetA2" type="number" placeholder="arg2" style="width:90px">
        <input id="resetA3" type="number" placeholder="arg3" style="width:90px">
        <input id="resetComment" type="text" placeholder="comment" style="width:180px">
        <button id="resetAdd" class="btn">Append Reset</button>
      </div>
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
const openMapBtn = document.getElementById('openMapBtn');
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
const resetsTable = document.getElementById('resetsTable').querySelector('tbody');
const resetCmd = document.getElementById('resetCmd');
const resetIf = document.getElementById('resetIf');
const resetA1 = document.getElementById('resetA1');
const resetA2 = document.getElementById('resetA2');
const resetA3 = document.getElementById('resetA3');
const resetComment = document.getElementById('resetComment');
const resetAdd = document.getElementById('resetAdd');

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
    dir.textContent = dirNames[ex.dir] ?? ex.dir;
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
    ex._inputs = {toInput, infoInput, keyInput, trkInput};
  }
}

function renderZoneMap(data, currentVnum, neighborSet) {
  const size = parseInt(zoneZoom.value, 10) || 20;
  const rooms = data.rooms || [];
  const edges = data.edges || [];
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
  const dirNames = {0:'N',1:'E',2:'S',3:'W'};
  for (const e of edges) {
    const x1 = e.x1 * size + size / 2;
    const y1 = e.y1 * size + size / 2;
    const x2 = e.x2 * size + size / 2;
    const y2 = e.y2 * size + size / 2;
    zctx.beginPath();
    zctx.moveTo(x1, y1);
    zctx.lineTo(x2, y2);
    zctx.stroke();
    const lx = (x1 + x2) / 2;
    const ly = (y1 + y2) / 2;
    zctx.fillStyle = '#e6e6e6';
    zctx.font = '10px monospace';
    zctx.textAlign = 'center';
    zctx.textBaseline = 'middle';
    zctx.fillText(dirNames[e.dir] || e.dir, lx, ly - 6);
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
    tr.innerHTML = `<td>${s.cmd}</td><td>${s.vnum}</td><td>${s.max}</td>`;
    spawnsTable.appendChild(tr);
  }
}

function renderResets() {
  resetsTable.innerHTML = '';
  if (!roomData) return;
  for (const r of roomData.resets) {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${r.cmd}</td><td>${r.if_flag}</td><td>${r.arg1}</td><td>${r.arg2}</td><td>${r.arg3 ?? ''}</td><td>${r.raw}</td>`;
    resetsTable.appendChild(tr);
  }
}

function syncExitInputs() {
  for (const ex of roomData.exits) {
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
    openMapBtn.disabled = !(data.zone_wilderness === 1 || data.zone_wilderness === 2);
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

loadBtn.addEventListener('click', loadRoom);
saveBtn.addEventListener('click', saveRoom);
openMapBtn.addEventListener('click', () => {
  if (!roomData) return;
  window.open(`/wild?vnum=${roomData.vnum}`, '_blank');
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
  const dirNames = {0:'N',1:'E',2:'S',3:'W'};
  for (const e of edges) {
    const x1 = e.x1 * size + size / 2;
    const y1 = e.y1 * size + size / 2;
    const x2 = e.x2 * size + size / 2;
    const y2 = e.y2 * size + size / 2;
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
    const lx = (x1 + x2) / 2;
    const ly = (y1 + y2) / 2;
    ctx.fillStyle = '#e6e6e6';
    ctx.font = `${Math.max(8, size * 0.4)}px monospace`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(dirNames[e.dir] || e.dir, lx, ly - 6);
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
        if parsed.path == "/wild":
            self._send(200, HTML.encode("utf-8"))
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
