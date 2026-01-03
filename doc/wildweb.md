# Wild/Miniwild Web Editor

Run a local web UI to edit wilderness and miniwild maps using in‑game symbols,
plus entrances/exits.

## Start the server

```
python tools/wildweb.py --host 0.0.0.0 --port 8080
```

Open in a browser:

```
http://<your-host>:8080
```

## Layout

- Left panel: entrances/exits editor + selected cell info
- Center: map grid (paint/query)
- Right panel: tile palette + search

## Features

- Visual grid for wild/miniwild
- Palette of symbols (id + name) from `lib/world/wild/wild_table`
- Click/drag paint
- Zoom controls and query mode (click a cell to read id/name/vnum)
- Auto backup on save: `lib/world/wild/<zone>.map.bak-YYYYmmdd-HHMMSS`
- Entrances/exits editor for wilderness/miniwild special rooms

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

## Notes

- The editor reads zone type from `lib/world/zon/<zone>.zon`.
- Only wilderness/miniwild zones are listed.
- Restart the server after saving to load new maps.

## Entrances/Exits

Use the left panel:

1) Click a cell (query or paint mode).
2) Choose direction and target VNUM.
3) Use **Set Exit** or **Remove Exit**.

Exit list behavior:
- No cell selected: shows all exits in the zone.
- Cell selected: shows only exits for that cell.
- Click an exit in the list to jump/select that cell in the grid.

This edits `lib/world/wild/<zone>.wld` and creates a backup:
`lib/world/wild/<zone>.wld.bak-YYYYmmdd-HHMMSS`.

If the room does not exist yet, the editor creates a minimal special room based
on the current terrain cell.
