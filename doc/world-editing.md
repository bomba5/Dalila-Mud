# Editing Wilderness, Miniwilds, Zones, and Rooms

This project is CircleMUD-based. World data lives under `lib/world/`. There are
two layers:

- **Normal areas** are defined by `.wld` (rooms) and `.zon` (zone resets).
- **Wilderness/miniwilds** are generated from a terrain table + map grid, then
  optionally overridden by special wilderness room files.

This document explains the files and how to edit them safely.

## 1) Wilderness and Miniwilds (terrain maps)

### 1.1 Terrain types: `lib/world/wild/wild_table`
Each wilderness cell references a terrain **type id** from this file.

Format per entry:

```
#<id>
<name>~
<description>~
<symbol> <color> <owner>
<move_cost> <altitude> <can_enter>
<sector_type> <room_flags>
```

Notes:
- Keep ids stable. Map files store the id number; changing/removing an id breaks
  maps that reference it.
- `symbol` and `color` are used for ASCII maps and display.
- `sector_type` and `room_flags` map to CircleMUD constants.

### 1.2 Map grids: `lib/world/wild/*.map` + `lib/world/wild/index.map`
Each `.map` file is a **grid of integers**, one row per line:
- **Wilderness** maps are **200x200**.
- **Miniwild** maps are **25x17**.

Each integer is a terrain type id from `wild_table`.

The list of map files is in `lib/world/wild/index.map`. Add your new map file
there if you create one.

Example (fragment of a map line):
```
301 301 301 300 300 200 119 27 2 2 2 2 ...
```

### 1.3 Wilderness special rooms: `lib/world/wild/*.wld` + `index.wld`
Wilderness/miniwild rooms are auto-generated from the map. To add **exits,
extra descriptions, room flags, or special behavior** to specific cells, use a
“special room” definition in a wilderness `.wld` file.

These files use the **same room format** as normal `.wld` files. They override
the auto-generated room for a specific VNUM.

The list of special-room files is in `lib/world/wild/index.wld`.

### 1.4 How to compute wilderness VNUMs from map coordinates
The coordinate system is defined in `src/wilderness.h`.

**Wilderness (zone wilderness=1):**
- Map size: **200x200**
- Map origin offset in the grid: `RXOR=400`, `RYOR=400`
- VNUM formula: `WILD_VNUM(x, y) = 1,000,000 + (1000 * y) + x`

To map a cell:
- `x = RXOR + column_index`
- `y = RYOR + row_index`
- `column_index` is the position in the line starting from 0
- `row_index` is the line number minus 1 (top line is 0)

**Miniwild (zone wilderness=2):**
- Map size: **25x17**
- Map origin offset in the grid: `RXOR=40`, `RYOR=40`
- VNUM formula: `MINIWILD_VNUM = (zone_number * 100) + (100 * y) + x`

To map a miniwild cell:
- `x = 40 + column_index`
- `y = 40 + row_index`
- `zone_number` is the zone id from the `.zon` file header (e.g., `20100`)

### 1.5 Miniwild exits (linking to the normal world)
Miniwild zones must declare exit VNUMs in the zone file. The order is:

```
<north> <east> <south> <west>
```

These are used when you walk off the miniwild map edge in that direction.

## 2) Zones (`.zon` files)

Zones define reset commands (mobs/objects/doors/etc) and zone metadata.

Files live in:
- `lib/world/zon/*.zon`
- indexed by `lib/world/zon/index` (and `index.mini` for the mini set)

Zone header format (line 3):
- **3 fields:** `<top> <lifespan> <reset_mode>`
- **4 fields:** `<top> <lifespan> <reset_mode> <wilderness>`
- **5 fields:** `<bottom> <top> <lifespan> <reset_mode> <wilderness>`

`wilderness` values (from `src/wilderness.h`):
- `0` = normal area
- `1` = wilderness
- `2` = miniwild

If `wilderness = 2` (miniwild), the next line must be:
```
<north> <east> <south> <west>
```

Zone commands follow until `S` or `$`. Common commands:
- `M` = load mob
- `O` = load object in room
- `G` = give object to last mob
- `E` = equip object on last mob
- `D` = set door state
- `R` = remove object from room
- `P` = put object in object

## 3) Rooms (`.wld` files)

Room files live in:
- `lib/world/wld/*.wld`
- indexed by `lib/world/wld/index` (and `index.mini` for the mini set)

Basic room format:

```
#<vnum>
<name>~
<description>~
<zone> <room_flags> <sector_type>
D<dir>
<door_name>~
<exit_description>~
<exit_info> <key_vnum> <to_room_vnum> <to_room_key>
E
<keyword>~
<description>~
S
```

Notes:
- `D<dir>` uses 0=N, 1=E, 2=S, 3=W, 4=U, 5=D.
- Multiple `D` and `E` blocks can appear.
- `S` ends a room. After `S`, triggers may appear.

## 4) Practical workflow

1) Identify the target zone or wilderness map file.
2) If editing wilderness/miniwild terrain:
   - Update `lib/world/wild/wild_table` if you need a new terrain type.
   - Edit the `.map` grid values to use the desired terrain ids.
3) If you need special behavior/exits on a wilderness cell:
   - Compute the VNUM for that cell.
   - Add a room entry to the correct `lib/world/wild/*.wld` file.
4) If you add a new `.wld`, `.zon`, or wilderness map file:
   - Add it to the appropriate `index` file.
5) Restart the server to reload world data.

## 5) Files to keep handy

- `lib/world/wild/wild_table` (terrain types)
- `lib/world/wild/index.map`, `lib/world/wild/*.map`
- `lib/world/wild/index.wld`, `lib/world/wild/*.wld` (special rooms)
- `lib/world/wld/index`, `lib/world/wld/*.wld`
- `lib/world/zon/index`, `lib/world/zon/*.zon`
- `src/wilderness.h` (coordinate sizes/offsets)
- `src/wilderness.c` and `src/db.c` (parsing/format rules)
