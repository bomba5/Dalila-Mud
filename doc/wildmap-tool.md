# Wild/Miniwild Symbol Editor

This tool lets you edit wilderness/miniwild maps using the in‑game symbols
from `lib/world/wild/wild_table`, then write back to the `.map` files.

## Quick start

Export a map to an ASCII symbol grid:

```
python tools/wildmap.py export 21200 --out /tmp/21200.asc
```

Edit `/tmp/21200.asc` in any editor (25x17 for miniwilds, 200x200 for wild).

Import back into the game files:

```
python tools/wildmap.py import 21200 --in /tmp/21200.asc
```

## How symbol mapping works

The `.map` files store **numeric terrain ids**. The tool converts ids to
symbols using `lib/world/wild/wild_table`.

Many ids share the **same symbol** (e.g., multiple plains). When importing,
the tool picks the **most common id in the current map** for each symbol.

If you introduce a symbol that never existed in the current map and that
symbol is ambiguous, the tool will stop and ask for a symbol override file.

## Symbol override file (optional)

Create a small file like:

```
# symbol id
p 105
c 200
O 19
```

Then import using:

```
python tools/wildmap.py import 21200 --in /tmp/21200.asc --symbol-map /tmp/symbols.map
```

## Notes

- Zone size is derived from `lib/world/zon/<zone>.zon`.
- Miniwilds are 25x17, wilderness is 200x200.
- Always restart the server to load updated maps.
