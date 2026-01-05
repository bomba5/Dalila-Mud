# Wild/Miniwild Web Editor

Run a local web UI to edit wilderness/miniwild maps and regular room files,
plus entrances/exits and basic spawns.

## Start the server

```
python tools/wildweb.py --host 0.0.0.0 --port 8080
```

## Build (non‑Nix)

```
make build
```

Optional overrides:

```
make build BUILD_CC=clang BUILD_FLAGS="-Wall -std=gnu89 -Wno-implicit-int"
```

Open in a browser:

```
http://<your-host>:8080
```

You’ll see a selector page:
- **Edit Wild/Miniwild** → `/wild`
- **Edit Zone/Rooms** → `/room`
- **Edit Mob** → `/mob`
- **Edit Object** → `/obj`
- **Help** button opens `/help`

## Layout (Map Editor)

- Left panel: entrances/exits editor + selected cell info
- Center: map grid (paint/query)
- Right panel: tile palette + search

## Features

- Visual grid for wild/miniwild
- Palette of symbols (id + name) from `lib/world/wild/wild_table`
- Click/drag paint
- Zoom controls and query mode (click a cell to read id/name/vnum)
- Tile symbols are colored using the in‑game wilderness color index
- Auto backup on save: `lib/world/wild/<zone>.map.bak-YYYYmmdd-HHMMSS`
- Entrances/exits editor for wilderness/miniwild special rooms
- Room editor for regular `.wld` areas (form‑based)
- Basic spawns (M/O) for rooms via zone resets
- Selection mode for irregular multi‑cell painting

## Basic usage

1) Start the server and open the UI in a browser.
2) Select a zone and click **Load**.
3) Pick a tile in the palette, then paint on the map.
4) Click **Save** to write the `.map` file.
5) Restart the game server to load new maps.

## Query mode

- The editor starts in **Query** mode.
- Click a cell to show its symbol, id, name, and computed VNUM.
- Use this to confirm coordinates or pick an entrance location.
- Use **Clear Selection** to unselect a cell and show all exits again.

## Selection mode

- Switch to **Select** mode to brush an irregular selection.
- Hold **Alt** while selecting to remove from the selection.
- **Fill Selection** paints the selection with the current palette tile.
- **Clear Selection** removes the selection overlay.

## Notes

- The editor reads zone type from `lib/world/zon/<zone>.zon`.
- Only wilderness/miniwild zones are listed.
- Restart the server after saving to load new maps.
- Mouse wheel zoom: hold **Ctrl** or **Shift** to zoom, centered on the selected cell.

## Entrances/Exits

Use the left panel:

1) Click a cell (query or paint mode).
2) Choose direction and target VNUM.
3) Use **Set Exit** or **Remove Exit**.

Exit list behavior:
- No cell selected: shows all exits in the zone.
- Cell selected: shows only exits for that cell.
- Click an exit in the list to jump/select that cell in the grid.
- Click **open** to open the target room in the Room Editor.

## Zone Editor (regular areas)

Open in a new tab:

```
http://<your-host>:8080/room?vnum=<VNUM>
```

Features:
- Edit room name/description, flags, sector, and exits.
- Adds backups to the source `.wld` file.
- If the room is a wilderness/miniwild map cell without a special room block,
  the editor opens it as **read‑only**.
- If the room does not exist yet, the editor creates a minimal special room
  block based on the current terrain cell.
- Embedded **Zone Map** for non‑wild zones with connecting lines and direction labels.
- Spawn list includes **open** links to Mob/Object editors.
- Search rooms by name/description from the header.
- Open zones by number and search zones by name/number.

## Zone Map (non‑wild zones)

The Room Editor shows a zone map when the room belongs to a non‑wild zone.

- Grid layout is built from N/E/S/W exits.
- Lines show connections and direction labels.
- Dashed links show exits to other zones or wilderness (with target vnum).
- Click a room to load it in the same tab.
- Zoom using the input next to the Zone Map header.

## Spawns (M/O) and Resets (M/O/E/G/P/D/R)

The room editor lets you add basic spawns:
- `M` = mob in room
- `O` = object in room

These are appended to the zone file for the room and backed up.
Use the **Find** input to search mobs/objects by name and fill the VNUM.

Reset commands:
- The room editor shows room‑related resets (M/O/D/R).
- You can append any reset command (M/O/E/G/P/D/R) with raw args.
- These are appended to the zone file and backed up.

## Mob/Object Editors

Open in a new tab:

```
http://<your-host>:8080/mob?vnum=<VNUM>
http://<your-host>:8080/obj?vnum=<VNUM>
```

- Core name fields are form‑based.
- Full numeric fields, flags, extras, affects, and triggers are editable.
- Search mobs/objects by name/description from the header.
- Object editor shows labeled type/flag/material selectors and APPLY_* affects.
- Backups are created on save.

Backups:
- Mobs: `lib/world/mob/<file>.mob.bak-YYYYmmdd-HHMMSS`
- Objects: `lib/world/obj/<file>.obj.bak-YYYYmmdd-HHMMSS`
