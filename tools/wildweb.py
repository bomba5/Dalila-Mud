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
        symbol = sym_line.split()[0]
        if len(symbol) != 1:
            symbol = symbol[0]
        entries.append({
            "id": wild_id,
            "symbol": symbol,
            "name": " ".join(name_lines).strip(),
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
        wilderness = 0
    elif len(parts) == 4:
        wilderness = int(parts[3])
    else:
        wilderness = int(parts[4])
    return {"number": number, "name": name, "wilderness": wilderness}


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


def parse_exit_map(lines):
    exits = {}
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
                        exits[dir_num] = to_vnum
                    except ValueError:
                        pass
            i += 4
            continue
        i += 1
    return exits


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
        exits = parse_exit_map(block_lines)
        if exits:
            exit_map[vnum] = {str(k): v for k, v in exits.items()}
    return exit_map


def update_wld_exit(zone, vnum, dir_num, to_vnum):
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
                    if to_vnum is None:
                        # remove 4-line block
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
  return fetch(url, opts).then(r => {
    if (!r.ok) throw new Error(r.statusText);
    return r.json();
  });
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
    div.textContent = `${item.symbol}  #${item.id}  ${item.name}`;
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
      ctx.fillStyle = '#e6e6e6';
      ctx.fillText(sym, cx, cy);
    }
  }
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
      const dirs = Object.keys(exits).sort((a,b)=>parseInt(a)-parseInt(b));
      for (const dir of dirs) {
        const toVnum = exits[dir];
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
}

init().catch(e => setStatus(`Init failed: ${e.message}`));
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
            self._send(200, HTML.encode("utf-8"))
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
                except Exception:
                    self._send_json(400, {"error": "Invalid vnum/dir/to_vnum"})
                    return
                if dir_num < 0 or dir_num > 5:
                    self._send_json(400, {"error": "dir must be 0..5"})
                    return
                try:
                    backup = update_wld_exit(zone, vnum, dir_num, to_vnum)
                except Exception as e:
                    self._send_json(400, {"error": str(e)})
                    return
                msg = "Exit removed." if to_vnum is None else "Exit set."
                if backup:
                    msg += f" Backup: {os.path.basename(backup)}"
                self._send_json(200, {"ok": True, "message": msg})
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
