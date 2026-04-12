# Dalila-MUD: C to Python 3 Port

## Project overview

Dalila-MUD is a custom Italian MUD based on CircleMUD 3.1, heavily extended with
unique game systems. The goal of this project is a full port from C to Python 3
that produces **exact behavioral compatibility** with the original server.

- **Source**: 71 C files, 32 headers, ~110K LOC in `src/`
- **World data**: 476K lines across .wld/.mob/.obj/.zon/.shp/.trg in `lib/world/`
- **Port target**: Python 3.12+, asyncio networking, dataclasses for game objects
- **Output directory**: `dalila/` (Python package root)

Players must not notice the difference. Same port (4000), same world files, same
commands, same text output byte-for-byte where it matters.

## Read order for context

1. This file (CLAUDE.md)
2. `docs/PORTING-PLAN.md` -- phased breakdown with estimates
3. `docs/AGENT-TASKS.md` -- pre-written task prompts for each phase
4. `src/structs.h` -- all data structures (1,768 lines), the single most
   important file for understanding the data model
5. `src/interpreter.c` -- command table (line 373+) and nanny() login state
   machine (line 2219+)
6. `src/comm.c` -- network layer, select() loop, game_loop()
7. `src/db.c` -- world file loaders, boot sequence (4,101 lines)

## Hard rules

1. **Never modify world files.** The files in `lib/` are sacred game content.
   The Python port reads them exactly as the C version does. No format changes,
   no "improved" formats, no migrations. The parser adapts to the data, not the
   other way around.

2. **Preserve Italian text exactly.** All player-facing strings, room
   descriptions, item names, mob descriptions, error messages, menus, and
   prompts must be reproduced character-for-character. Do not translate, do not
   "fix" grammar, do not normalize whitespace. When porting a C function that
   contains `send_to_char("Non puoi farlo!\r\n", ch)`, the Python equivalent
   must send the identical string.

3. **Test against existing data.** Every module must be validated against the
   real world files in `lib/world/`. Parser tests must load actual .wld, .mob,
   .obj, .zon, .shp, .trg files and verify entity counts, field values, and
   cross-references match the C version's boot output.

4. **Commands must have both Italian and English aliases.** The command table in
   `interpreter.c` (line 373) defines dual aliases -- e.g., "north"/"nord",
   "look"/"guarda", "quit"/"abbandonare". The Python dispatch table must
   replicate this exactly.

5. **No premature optimization.** Port the logic faithfully first. Optimize
   only when profiling shows a bottleneck. The C code uses global arrays and
   pointer chains; the Python port uses proper data structures, but the game
   logic and formulas must be identical.

6. **Binary playerfile support.** The C version stores players in a binary
   format defined by `struct char_file_u` in `structs.h` (line ~1279+). The
   Python port must be able to READ these files for migration. New player
   storage will use JSON or SQLite, but the migration tool must handle the
   exact binary layout.

## Custom Dalila systems (not in stock CircleMUD)

These are the systems that make Dalila unique. Each must be ported faithfully:

| System | Italian name | C files | LOC | Description |
|--------|-------------|---------|-----|-------------|
| Crafting | Mestieri | mestieri.c, mestieri.h | 5,901 | Full crafting system with materials, recipes, skill progression |
| Kingdoms | Regni/Clan | clan.c, clan.h, clan2.c, clan2.h | 6,863 (4,009 + 2,854) | Kingdom management, ranks, diplomacy, fees (stipendio) |
| Abilities | Abilita | abilita.c, abilita.h | 1,425 | Custom ability system separate from skills/spells |
| Wilderness | Wilderness | wilderness.c, wilderness.h, wedit.c | 2,449 (1,829 + 620) | Open-world wilderness with maps (.map files in lib/world/wild/) |
| DG Scripts | Trigger | dg_scripts.c + 9 dg_*.c files | 7,867 | Death Gate scripting engine for mob/obj/room triggers |
| Armies | Eserciti | eserciti.c, eserciti.h | 534 | Military unit management tied to kingdoms |
| Critical hits | Colpi critici | fight.c (LOCATION_* defines) | Part of 3,768 | Locational damage: testa, braccio_d/s, torso, gamba_d/s |
| Religions | Religioni | structs.h defines + spell effects | Distributed | 4 religions: Shaarr, Xhypys, Silue, Therion |
| Arena | Arena | arena.c, arena.h | 744 | PvP arena system |
| Auction | Asta | auction.c, auction.h | 422 | Item auction house |
| Quests | Quest | quest.c | 894 | Quest tracking system |
| Mob patrol | Go-patrol | go-patrol.c | 1,001 | Mob pathfinding and patrol routes |
| Spec procs | Procedure speciali | spec_procs.c, spec_assign.c | 5,747 (5,237 + 510) | Special procedures for unique mob/room behavior |
| InterMUD | InterMUD | act.intermud.c | 791 | Cross-MUD communication |
| Disguise | Camuffamento | structs.h char_player_data | Distributed | Full identity disguise system (name, class, level, sex, clan) |
| Fishing | Pesca | Events in char_special_data | Distributed | Fishing event system |

## Coding conventions

### Python style
- Python 3.12+ minimum (use modern syntax: `type` statements, `match/case`)
- `asyncio` for all networking -- no threads, no select()
- `dataclasses` with full type hints for all game objects
- Use `enum.IntEnum` or `enum.IntFlag` for all C `#define` constant groups
- Docstrings on all public functions, referencing the original C function name
- No external dependencies beyond the standard library (match the C version's
  libc-only approach). Exception: `pytest` for testing.
- Line length: 100 chars max
- Imports: stdlib, then project, then typing (isort compatible)

### Package structure
```
dalila/
    __init__.py
    models/              # Data structures (from structs.h)
        __init__.py
        characters.py    # char_data, char_file_u, char_player_data, etc.
        objects.py       # obj_data, obj_flag_data, obj_file_elem
        rooms.py         # room_data, room_direction_data
        world.py         # zone_data, shop_data, trigger types
        constants.py     # All #define constants as enums
    parsers/             # World file loaders (from db.c)
        __init__.py
        world.py         # .wld parser
        mobs.py          # .mob parser
        objects.py       # .obj parser
        zones.py         # .zon parser
        shops.py         # .shp parser
        triggers.py      # .trg parser
        wilderness.py    # .map + wild_table parser
    net/                 # Network layer (from comm.c)
        __init__.py
        server.py        # asyncio server, connection handling
        descriptor.py    # descriptor_data equivalent
        telnet.py        # Telnet protocol handling
    engine/              # Core game loop
        __init__.py
        game_loop.py     # Heartbeat, pulse timers
        handler.py       # find_char, find_obj, affect handling (handler.c)
        interpreter.py   # Command dispatch, nanny() state machine
        limits.py        # Regen, hunger/thirst, idle (limits.c)
    commands/            # Player commands (act.*.c files)
        __init__.py
        movement.py      # act.movement.c (2,456 lines)
        informative.py   # act.informative.c (3,891 lines)
        item.py          # act.item.c (3,083 lines)
        communication.py # act.comm.c (1,034 lines)
        offensive.py     # act.offensive.c (1,791 lines)
        social.py        # act.social.c (282 lines)
        wizard.py        # act.wizard.c (4,686 lines)
        other.py         # act.other.c (2,109 lines)
        create.py        # act.create.c (736 lines)
    combat/              # Combat engine
        __init__.py
        fight.py         # fight.c (3,768 lines)
        magic.py         # magic.c (2,275 lines)
        spells.py        # spells.c (2,318 lines)
        spell_parser.py  # spell_parser.c (1,971 lines)
    systems/             # Custom Dalila systems
        __init__.py
        mestieri.py      # Crafting (mestieri.c, 5,901 lines)
        clan.py          # Kingdoms (clan.c, 4,009 lines)
        clan2.py         # Kingdom extensions (clan2.c, 2,854 lines)
        wilderness.py    # Wilderness (wilderness.c, 1,829 lines)
        abilita.py       # Abilities (abilita.c, 1,425 lines)
        eserciti.py      # Armies (eserciti.c, 534 lines)
        arena.py         # Arena (arena.c, 744 lines)
        auction.py       # Auction (auction.c, 422 lines)
        quest.py         # Quests (quest.c, 894 lines)
        religion.py      # Religion effects (distributed across files)
    scripting/           # DG Scripts engine
        __init__.py
        engine.py        # dg_scripts.c (2,592 lines)
        triggers.py      # dg_triggers.c (898 lines)
        mob_cmds.py      # dg_mobcmd.c (1,084 lines)
        obj_cmds.py      # dg_objcmd.c (748 lines)
        wld_cmds.py      # dg_wldcmd.c (656 lines)
        db_scripts.py    # dg_db_scripts.c (424 lines)
        comm.py          # dg_comm.c (193 lines)
        misc.py          # dg_misc.c (293 lines)
        handler.py       # dg_handler.c (69 lines)
        events.py        # dg_event.c (106 lines)
    olc/                 # Online Creation
        __init__.py
        olc.py           # olc.c (715 lines)
        redit.py         # redit.c (1,229 lines)
        oedit.py         # oedit.c (1,826 lines)
        medit.py         # medit.c (1,562 lines)
        sedit.py         # sedit.c (1,498 lines)
        zedit.py         # zedit.c (1,631 lines)
        wedit.py         # wedit.c (620 lines)
        dg_olc.py        # dg_olc.c (804 lines)
    save/                # Player persistence
        __init__.py
        objsave.py       # objsave.c (2,012 lines)
        house.py         # house.c (1,030 lines)
        migration.py     # Binary playerfile → JSON/SQLite converter
    util/                # Utilities
        __init__.py
        utils.py         # utils.c (797 lines)
        config.py        # config.c (382 lines)
        constants.py     # constants.c (1,462 lines)
        weather.py       # weather.c (210 lines)
    ai/                  # Mob behavior
        __init__.py
        mobact.py        # mobact.c (599 lines)
        go_patrol.py     # go-patrol.c (1,001 lines)
        spec_procs.py    # spec_procs.c (5,237 lines)
        spec_assign.py   # spec_assign.c (510 lines)
    misc/                # Everything else
        __init__.py
        mail.py          # mail.c (564 lines)
        boards.py        # boards.c (819 lines)
        alias.py         # alias.c (133 lines)
        ban.py           # ban.c (447 lines)
        intermud.py      # act.intermud.c (791 lines)
tests/
    conftest.py          # Shared fixtures, world data paths
    test_parsers/        # World file parser tests
    test_models/         # Data structure tests
    test_commands/       # Command integration tests
    test_combat/         # Combat formula tests
    test_systems/        # Custom system tests
    test_scripting/      # DG Script tests
pyproject.toml
```

### Naming conventions
- Python module names: snake_case matching the C file where possible
- Classes: PascalCase (`CharData`, `RoomData`, `ObjData`)
- Constants/enums: UPPER_SNAKE matching C defines (`ROOM_DARK`, `LVL_IMPL`)
- Functions: snake_case matching C names where practical (`send_to_char`,
  `find_char_in_room`)
- Preserve Italian names for Dalila-specific concepts: `mestieri`, `abilita`,
  `eserciti`, `regni`, `religioni`, `notorieta`, `fama`, `camuffamento`

## How to run tests

```bash
# From project root
python -m pytest tests/ -v

# Run just parser tests (fastest feedback loop)
python -m pytest tests/test_parsers/ -v

# Run with world file validation
python -m pytest tests/test_parsers/ -v --world-dir=lib/world

# Run a specific test
python -m pytest tests/test_parsers/test_world.py -v -k "test_room_count"
```

## How to validate against the C version

1. Compile and boot the C version: `cd src && make && cd .. && bin/circle -q 4001`
2. Capture boot output (zone counts, entity counts, room counts)
3. Boot the Python version: `python -m dalila --port 4002 --check-only`
4. Compare: room count, mob count, obj count, zone count, shop count, trigger count
5. Telnet to both on side-by-side ports and run the same commands -- output must match

## Key C structures to Python mappings

| C struct (structs.h) | Python class | Module |
|---|---|---|
| `struct char_data` | `CharData` | `dalila/models/characters.py` |
| `struct char_file_u` | `CharFileRecord` | `dalila/models/characters.py` |
| `struct char_player_data` | `CharPlayerData` | `dalila/models/characters.py` |
| `struct char_ability_data` | `CharAbilityData` | `dalila/models/characters.py` |
| `struct char_point_data` | `CharPointData` | `dalila/models/characters.py` |
| `struct char_special_data` | `CharSpecialData` | `dalila/models/characters.py` |
| `struct player_special_data_saved` | `PlayerSpecialSaved` | `dalila/models/characters.py` |
| `struct obj_data` | `ObjData` | `dalila/models/objects.py` |
| `struct obj_flag_data` | `ObjFlagData` | `dalila/models/objects.py` |
| `struct obj_file_elem` | `ObjFileElem` | `dalila/models/objects.py` |
| `struct room_data` | `RoomData` | `dalila/models/rooms.py` |
| `struct room_direction_data` | `RoomDirection` | `dalila/models/rooms.py` |
| `struct extra_descr_data` | `ExtraDescr` | `dalila/models/rooms.py` |
| `struct descriptor_data` | `Descriptor` | `dalila/net/descriptor.py` |
| `struct command_info` | `CommandInfo` | `dalila/engine/interpreter.py` |
| `struct zone_data` | `ZoneData` | `dalila/models/world.py` |
| `struct shop_data` | `ShopData` | `dalila/models/world.py` |
| `struct trig_data` | `TrigData` | `dalila/models/world.py` |
| `struct rent_info` | `RentInfo` | `dalila/models/objects.py` |

## Important constants (from structs.h)

- `OPT_USEC = 100000` -- 10 game loop passes per second
- `PULSE_ZONE = 10 RL_SEC` -- zone reset every 100 passes
- `PULSE_MOBILE = 10 RL_SEC` -- mob actions every 100 passes
- `PULSE_VIOLENCE = 3 RL_SEC` -- combat rounds every 30 passes
- `MAX_SKILLS = 200`, `MAX_PROFICIENZE = 100`, `MAX_ABILITA = 100`
- `MAX_AFFECT = 32`, `MAX_OBJ_AFFECT = 6`
- `NUM_OBJ_VAL_POSITIONS = 10` (extended from CircleMUD's 4)
- `NUM_RELIGIONI = 5` (Nessuna, Shaarr, Xhypys, Silue, Therion)
- `NUM_EVENTS = 11` (custom player event timers)
- Level cap: `LVL_IMPL = 91`, mortal range 1-70, immortal 71+
- Body locations: 7 (testa, braccio_d, braccio_s, torso, gamba_d, gamba_s, random)
