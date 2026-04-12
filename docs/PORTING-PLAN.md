# Dalila-MUD Porting Plan: C to Python 3

Total estimate: **72-108 hours** of agent work.
With Bart's agents doing 90%: Jhonata reviews ~10-15h.

---

## Phase 0: Foundation (4-6h)

Goal: Python project skeleton, all data structures, all world file parsers.
This phase produces zero game logic but 100% data loading capability.

### P0-1: Project skeleton (30min)
- Create `pyproject.toml` with project metadata, Python 3.12+ requirement, pytest dependency
- Create the full `dalila/` package tree (all `__init__.py` files per CLAUDE.md structure)
- Create `tests/conftest.py` with path fixtures pointing to `lib/world/`
- Verify: `python -m dalila` imports cleanly, `pytest` discovers test dir

### P0-2: Constants and enums (1-2h)
- Port all `#define` groups from `structs.h` to `dalila/models/constants.py`
- Use `enum.IntEnum` for discrete sets (directions, positions, sectors, classes)
- Use `enum.IntFlag` for bitfields (room_flags, extra_flags, affected_by, wear_flags)
- Include ALL Italian-named constants: `DANNO_FUOCO/GHIACCIO/ELETTRICITA/ACIDO`,
  `RELIGIONE_SHAARR/XHYPYS/SILUE/THERION`, `LOCATION_TESTA/BRACCIO_D/etc.`,
  `LAST_BASH/STEAL/BREATH/etc.`
- Port constants from `constants.c` (1,462 lines): spell names, class names,
  direction names, wear positions, sector types, liquid types
- Port constants from `spells.h` (491 lines): all spell/skill numbers
- Verify: all enums importable, spot-check values match C defines

### P0-3: Data structure models (2-3h)
- Port `structs.h` (1,768 lines) to dataclasses in `dalila/models/`:
  - `characters.py`: `CharData`, `CharFileRecord` (binary layout), `CharPlayerData`,
    `CharAbilityData`, `CharPointData`, `CharSpecialData`, `CharSpecialDataSaved`,
    `PlayerSpecialDataSaved` (with skills[201], proficienze[101], abilita[101]),
    `MemoryRec`, `TimeInfoData`, `TimeData`, `PlayerFee`
  - `objects.py`: `ObjData`, `ObjFlagData` (with value[10], bitvector[4]),
    `ObjAffectedType`, `ObjFileElem`, `RentInfo`, `ExtraDescrData`
  - `rooms.py`: `RoomData` (with wild_modif, wild_rnum Dalila extensions),
    `RoomDirectionData`, `ExtraDescr`
  - `world.py`: `ZoneData`, `ResetCommand`, `ShopData`, `IndexData`,
    `TrigData`, `TrigProtoList`, `ScriptData`
- Preserve C field names where they are Italian game terms
- Include `struct` module format strings for binary playerfile fields
- Verify: import all models, field counts match C structs

### P0-4: World file parsers (2-3h)
- Port world loading from `db.c` (4,101 lines, specifically the `boot_db()`,
  `parse_room()`, `parse_mobile()`, `parse_object()`, `load_zones()` functions)
- Create parsers in `dalila/parsers/`:
  - `world.py`: Parse .wld files (207 files in `lib/world/wld/`), handle
    Dalila extensions (room resources, wilderness modifiers, extra bitvectors)
  - `mobs.py`: Parse .mob files (162 files in `lib/world/mob/`)
  - `objects.py`: Parse .obj files (190 files, note NUM_OBJ_VAL_POSITIONS=10
    and Dalila-specific fields: tipo_materiale, num_materiale, curr_slots, total_slots)
  - `zones.py`: Parse .zon files (220 files), zone reset commands
  - `shops.py`: Parse .shp files (87 files) -- reference `shop.c` (2,258 lines)
  - `triggers.py`: Parse .trg files (92 files) -- reference `dg_db_scripts.c` (424 lines)
  - `wilderness.py`: Parse .map files and `wild_table` from `lib/world/wild/`
- Each parser reads from `index.*` files to discover which zone files to load
- Verify against C boot output:
  - Exact room count, mob prototype count, obj prototype count
  - Zone count, shop count, trigger count
  - No parse errors on any file

---

## Phase 1: Core Engine (8-12h)

Goal: A player can telnet in, see the login screen, create a character or log in,
and see the MOTD. No game world interaction yet.

### P1-1: Network layer (3-4h)
- Port `comm.c` (2,798 lines) networking to asyncio:
  - `dalila/net/server.py`: `asyncio.start_server()` on port 4000
  - `dalila/net/descriptor.py`: `Descriptor` class replacing `struct descriptor_data`
    -- tracks connection state, output buffer, input queue, snoop chain
  - `dalila/net/telnet.py`: Telnet IAC handling (echo on/off for passwords,
    NAWS for terminal size), from `telnet.h` (319 lines)
- Handle: new connections, input buffering, output flushing, connection close,
  max descriptor limit, site banning (from `ban.c`, 447 lines)
- Verify: telnet localhost 4000 connects and receives greeting text

### P1-2: Game loop and heartbeat (2-3h)
- Port the game loop from `comm.c` `game_loop()`:
  - `dalila/engine/game_loop.py`: asyncio event loop with pulse counters
  - `OPT_USEC = 100000` (10 passes/sec)
  - Pulse timers: PULSE_ZONE (10s), PULSE_MOBILE (10s), PULSE_VIOLENCE (3s)
  - Call zone resets, mob activity, combat rounds, regen ticks at correct intervals
- Port `limits.c` (1,244 lines): `point_update()`, `check_idling()`,
  gain functions for hp/mana/move
- Port `regen.c` (312 lines): regeneration calculations
- Port `events.c` (125 lines) and `queue.c` (175 lines): event queue system
- Verify: game loop runs, pulse counters increment correctly, no CPU spin

### P1-3: Login state machine (2-3h)
- Port `nanny()` from `interpreter.c` (line 2219, ~400 lines):
  - `dalila/engine/interpreter.py`: state machine for connection states
  - States: CON_GET_NAME, CON_NAME_CNFRM, CON_PASSWORD, CON_NEWPASSWD,
    CON_CNFPASSWD, CON_QSEX, CON_QCLASS, CON_RMOTD, CON_MENU, CON_PLAYING,
    plus OLC states, plus Dalila-specific: mestieri choice, abilita choice,
    iniziazione (religion), hometown selection, stat rolling
  - Reference menus: `menu_iniziazione()`, `menu_mestieri()`,
    `menu_scelta_abilita()`
- Port character loading: `load_char()` from `db.c`, `init_char()`, `do_start()`
- Load text files: `lib/text/greetings`, `lib/text/motd`, `lib/text/menu`,
  `lib/text/background`, `lib/text/news`, `lib/text/credits`
- Verify: full login flow works -- new character creation and existing character login

### P1-4: Command interpreter (1-2h)
- Port command table from `interpreter.c` (line 373, ~600 entries):
  - `dalila/engine/interpreter.py`: `CommandInfo` dataclass, dispatch dict
  - All Italian+English dual aliases (nord/north, guarda/look, etc.)
  - Position restrictions, level restrictions, subcmd values
  - `command_interpreter()` function: input parsing, abbreviation matching,
    special proc checking, command dispatch
- Stub all ACMD functions to print "Not yet implemented"
- Verify: type commands, see dispatch working, abbreviations resolve correctly

---

## Phase 2: World Interaction (10-15h)

Goal: Walk around the world, look at rooms/mobs/objects, pick up and drop items,
talk to other players. The MUD feels alive but has no combat.

### P2-1: Room and movement (3-4h)
- Port `act.movement.c` (2,456 lines):
  - `dalila/commands/movement.py`: do_move, do_enter, do_leave, do_stand,
    do_sit, do_rest, do_sleep, do_wake, do_follow, do_ride (cavalcare),
    do_knock, do_open, do_close, do_lock, do_unlock
  - Door handling, key checking, movement cost (sector-based)
  - Riding system (cavalcatura -- transported/transported_by)
  - Wilderness movement (wild_modif, map display)
- Port room display from `act.informative.c`: look_at_room(), list exits
- Port `graph.c` (388 lines): BFS pathfinding (used by track, hunt, go-patrol)
- Verify: walk between rooms, see descriptions, use doors, ride mounts

### P2-2: Look and examine (3-4h)
- Port `act.informative.c` (3,891 lines):
  - `dalila/commands/informative.py`: do_look, do_examine, do_stat,
    do_score (punteggio), do_who (chi), do_where (dove), do_weather (meteo),
    do_time (tempo), do_inventory (inventario), do_equipment (equipaggiamento),
    do_consider (considera), do_diagnose (diagnosi), do_toggle, do_affects
  - Disguise display logic (camuffamento fields from char_player_data)
  - Wilderness map rendering for look
  - List people/objects in room with proper Italian formatting
- Verify: look at rooms, examine objects, check score, see who's online

### P2-3: Item manipulation (2-3h)
- Port `act.item.c` (3,083 lines):
  - `dalila/commands/item.py`: do_get (prendi), do_drop (lascia),
    do_put (metti), do_give (dai), do_wear (indossa), do_remove (rimuovi),
    do_wield (impugna), do_grab (afferra), do_drink (bevi), do_eat (mangia),
    do_pour (versa), do_hang (aggancia)
  - Container logic (open/close/lock containers)
  - Object weight/slot system (curr_slots/total_slots)
  - Material system (tipo_materiale, num_materiale)
- Port `objsave.c` (2,012 lines): crash-save, rent system, object persistence
- Verify: pick up items, wear equipment, use containers, drop items

### P2-4: Communication (1-2h)
- Port `act.comm.c` (1,034 lines):
  - `dalila/commands/communication.py`: do_say (dici/'), do_tell (parla),
    do_whisper (sussurra), do_ask (chiedi), do_shout (urla), do_gossip,
    do_holler, do_gsay (group say), do_emote (:)
  - Channel system with soundproof room checks
  - Tell history (TELLS_STORED = 10)
- Port `act.social.c` (282 lines): social commands (abbraccia, accarezza, etc.)
- Verify: say/tell/shout between two telnet sessions

### P2-5: Handler functions (2-3h)
- Port `handler.c` (1,685 lines):
  - `dalila/engine/handler.py`: Core lookup and manipulation functions:
    `get_char_room()`, `get_char_vis()`, `get_obj_in_list_vis()`,
    `find_char()`, `find_obj()`, `affect_modify()`, `affect_to_char()`,
    `affect_remove()`, `equip_char()`, `unequip_char()`, `obj_to_room()`,
    `obj_from_room()`, `obj_to_char()`, `obj_from_char()`, `extract_char()`,
    `extract_obj()`
  - Name matching with abbreviation support
  - Keyword matching (Italian object/mob names)
- Port `utils.c` (797 lines): utility functions, dice rolling, string handling
- Verify: all name lookups work, affect system functional

---

## Phase 3: Combat and Magic (15-20h)

Goal: Full combat system with spells, abilities, critical hits, and death.

### P3-1: Combat engine (5-7h)
- Port `fight.c` (3,768 lines):
  - `dalila/combat/fight.py`: `hit()`, `damage()`, `perform_violence()`,
    `set_fighting()`, `stop_fighting()`, `die()`, `group_gain()`,
    `raw_kill()`, `death_cry()`
  - Critical hit system with locational damage:
    LOCATION_TESTA, LOCATION_BRACCIO_D/S, LOCATION_TORSO, LOCATION_GAMBA_D/S
  - Damage types: DANNO_FUOCO, DANNO_GHIACCIO, DANNO_ELETTRICITA, DANNO_ACIDO,
    DANNO_SHAARR, DANNO_XHYPHYS, DANNO_THERION, DANNO_SILUE, DANNO_FISICO
  - Notorieta/fama system (reputation from kills)
- Port `act.offensive.c` (1,791 lines):
  - `dalila/commands/offensive.py`: do_kill (uccidi), do_flee (fuggi),
    do_kick (calcia), do_bash (spingi), do_backstab (pugnala),
    do_agguato (ambush), do_steal (ruba), do_rescue (salva), do_disarm
- Verify: engage mobs in combat, see hit/damage messages, die and respawn

### P3-2: Spell system (5-7h)
- Port `spell_parser.c` (1,971 lines):
  - `dalila/combat/spell_parser.py`: `cast_spell()`, `mag_areas()`,
    `mag_damage()`, `mag_affects()`, `mag_unaffects()`, `mag_points()`,
    `mag_alter_objs()`, `mag_groups()`, `mag_masses()`, `mag_summons()`,
    `mag_creations()`
  - Spell argument parsing (target resolution)
  - Mana cost, level requirements, component checking
- Port `spells.c` (2,318 lines):
  - `dalila/combat/spells.py`: Individual spell effect implementations
  - All spell constants from `spells.h` (491 lines)
- Port `magic.c` (2,275 lines):
  - `dalila/combat/magic.py`: `mag_savingthrow()`, `mag_resistance()`,
    magic damage formulas, area effect logic
  - Religion-specific damage bonuses (DANNO_SHAARR, etc.)
- Port `class.c` (1,996 lines): class definitions, level thresholds,
  THAC0 tables, skill/spell assignment per class, stat limits
- Verify: cast spells, see damage, check saving throws, class abilities

### P3-3: Abilities (2-3h)
- Port `abilita.c` (1,425 lines):
  - `dalila/systems/abilita.py`: ability system separate from skills
  - Ability checks, learning, teaching (maestri erranti from mob_abil[5])
  - `abil_info_type` struct and abil_info[] table
  - Integration with char_data.abilita[MAX_ABILITA+1]
- Port proficiency system: proficienze[MAX_PROFICIENZE+1] from player_special_data
- Verify: use abilities, check success rates, learn from masters

### P3-4: Mob behavior (3-4h)
- Port `mobact.c` (599 lines):
  - `dalila/ai/mobact.py`: `mobile_activity()` -- mob AI per pulse
  - Aggressive mobs, scavenger mobs, memory mobs, sentinel mobs
- Port `go-patrol.c` (1,001 lines):
  - `dalila/ai/go_patrol.py`: patrol routes, pathfinding behavior
- Port `spec_procs.c` (5,237 lines) + `spec_assign.c` (510 lines):
  - `dalila/ai/spec_procs.py` + `dalila/ai/spec_assign.py`
  - All special procedures: guild masters, shopkeepers, guards, castle NPCs
- Port `castle.c` (837 lines): King's Castle special procedures
- Verify: mobs move, attack players, execute special behaviors

---

## Phase 4: Advanced Systems (20-30h)

Goal: All Dalila-specific systems operational -- scripting, crafting, kingdoms.

### P4-1: DG Scripting engine (8-12h)
- Port all dg_*.c files (7,867 lines total):
  - `dalila/scripting/engine.py` from `dg_scripts.c` (2,592 lines):
    Script execution engine, variable handling, control flow (if/else/while/switch),
    wait states, %actor% / %self% / %random% variable expansion
  - `dalila/scripting/triggers.py` from `dg_triggers.c` (898 lines):
    Trigger types (greet, command, speech, receive, death, enter, drop, etc.),
    trigger evaluation and firing
  - `dalila/scripting/mob_cmds.py` from `dg_mobcmd.c` (1,084 lines):
    Mob script commands (mecho, msend, mforce, mkill, mload, etc.)
  - `dalila/scripting/obj_cmds.py` from `dg_objcmd.c` (748 lines):
    Object script commands (oecho, osend, oforce, oload, etc.)
  - `dalila/scripting/wld_cmds.py` from `dg_wldcmd.c` (656 lines):
    Room script commands (wecho, wsend, wforce, wload, etc.)
  - `dalila/scripting/db_scripts.py` from `dg_db_scripts.c` (424 lines):
    Script loading/saving from .trg files
  - `dalila/scripting/comm.py` from `dg_comm.c` (193 lines): Script output
  - `dalila/scripting/misc.py` from `dg_misc.c` (293 lines): Utility functions
  - `dalila/scripting/handler.py` from `dg_handler.c` (69 lines)
  - `dalila/scripting/events.py` from `dg_event.c` (106 lines): Script events
- Global variable system: MAX_GBL_VAR_SAVED=128, MAX_NAME_VAR_LENGTH=20,
  MAX_VAR_LENGTH=150
- Verify: load all 92 trigger files, fire greet/command/speech triggers,
  variable substitution works, control flow executes correctly

### P4-2: Crafting system -- Mestieri (4-6h)
- Port `mestieri.c` (5,901 lines) + `mestieri.h`:
  - `dalila/systems/mestieri.py`: Complete crafting system
  - Crafting recipes, material requirements, skill checks
  - Crafting progression and mastery
  - Integration with object creation (tipo_materiale, num_materiale)
  - Reference `act.create.c` (736 lines) for creation commands
- Verify: craft items, check recipes, skill progression works

### P4-3: Kingdom system -- Regni/Clan (4-6h)
- Port `clan.c` (4,009 lines) + `clan.h` (311 lines):
  - `dalila/systems/clan.py`: Core kingdom/clan management
  - Clan creation, membership, ranks (clan_rank), diplomacy
  - Fee system (PlayerFee/stipendio struct)
  - Data files in `lib/etc/clans/` and `lib/etc/new_clans/`
- Port `clan2.c` (2,854 lines) + `clan2.h`:
  - `dalila/systems/clan2.py`: Extended kingdom features
  - Inter-clan relationships, wars, alliances
  - Territory control
- Port `eserciti.c` (534 lines) + `eserciti.h`:
  - `dalila/systems/eserciti.py`: Army management
  - Data files in `lib/etc/eserciti/`
- Religion assignment: `assign_to_regno()` function
- Verify: create clans, manage ranks, declare wars, manage armies

### P4-4: Wilderness (2-3h)
- Port `wilderness.c` (1,829 lines) + `wilderness.h` (95 lines):
  - `dalila/systems/wilderness.py`: Open-world wilderness system
  - Map rendering from .map files (wild/ directory has paired .map/.wld files)
  - `wild_table` parsing (lib/world/wild/wild_table)
  - `wild_modif` and `wild_rnum` room fields
  - Wilderness hunting (wildhunt from char_special_data)
  - Client-specific map output (client field in char_special_data)
- Port `wedit.c` (620 lines): Wilderness OLC editor
- Verify: enter wilderness, see map display, navigate, hunt works

### P4-5: Arena, auction, quests, religion (2-3h)
- Port `arena.c` (744 lines) + `arena.h`:
  - `dalila/systems/arena.py`: PvP arena, matchmaking, scoring
- Port `auction.c` (422 lines) + `auction.h`:
  - `dalila/systems/auction.py`: Item auction system
- Port `quest.c` (894 lines):
  - `dalila/systems/quest.py`: Quest tracking and completion
- Port religion system from distributed code:
  - `dalila/systems/religion.py`: 4 religions (Shaarr, Xhypys, Silue, Therion),
    membership, prayers (lib/text/pray), bonuses
  - Catarsi mechanic (catarsi field in char_special_data)
- Verify: join arena, auction items, track quests, pray to gods

---

## Phase 5: Everything Else (10-15h)

Goal: All remaining systems ported. Full game session comparable to C version.

### P5-1: OLC -- Online Creation (4-6h)
- Port all OLC editors (9,885 lines total across 8 files):
  - `dalila/olc/olc.py` from `olc.c` (715 lines): OLC framework, cleanup
  - `dalila/olc/redit.py` from `redit.c` (1,229 lines): Room editor
  - `dalila/olc/oedit.py` from `oedit.c` (1,826 lines): Object editor
  - `dalila/olc/medit.py` from `medit.c` (1,562 lines): Mobile editor
  - `dalila/olc/sedit.py` from `sedit.c` (1,498 lines): Shop editor
  - `dalila/olc/zedit.py` from `zedit.c` (1,631 lines): Zone editor
  - `dalila/olc/wedit.py` from `wedit.c` (620 lines): Wilderness editor
  - `dalila/olc/dg_olc.py` from `dg_olc.c` (804 lines): Trigger editor
- OLC parse functions are called from nanny() for in-OLC connection states
- Verify: enter OLC mode, edit a room, save changes

### P5-2: Player persistence (2-3h)
- Port binary playerfile reading from `db.c` (`load_char()`):
  - `dalila/save/migration.py`: Read `struct char_file_u` binary records
  - Exact field layout: passwd[11], name[20], title[80], description[240],
    skills[201], proficienze[101], abilita[101], affects[32], etc.
- Implement new JSON/SQLite player storage:
  - `dalila/save/player_store.py`: Modern persistence layer
  - Save/load player data, object inventory, aliases
- Port `objsave.c` (2,012 lines): rent files, crash-save, object loading
- Port `house.c` (1,030 lines): house system
- Verify: migrate a C playerfile, login with migrated character, save/load cycle

### P5-3: Utility systems (2-3h)
- Port `mail.c` (564 lines): `dalila/misc/mail.py` -- MUD mail
  (data in `lib/etc/plrmail/`)
- Port `boards.c` (819 lines): `dalila/misc/boards.py` -- bulletin boards
- Port `modify.c` (1,233 lines): string editor, text formatting
- Port `alias.c` (133 lines): `dalila/misc/alias.py` -- command aliases
- Port `ban.c` (447 lines): `dalila/misc/ban.py` -- site bans
  (data in `lib/etc/badsites`)
- Port `act.intermud.c` (791 lines): `dalila/misc/intermud.py` -- InterMUD
- Port `weather.c` (210 lines): `dalila/util/weather.py` -- weather system
- Port `config.c` (382 lines): `dalila/util/config.py` -- game configuration
- Verify: send/receive mail, post to boards, set aliases, ban sites

### P5-4: Wizard commands and admin (2-3h)
- Port `act.wizard.c` (4,686 lines):
  - `dalila/commands/wizard.py`: All immortal commands: goto, transfer, set,
    stat, purge, load, syslog, wiznet, godnet, shutdown, reboot, snoop,
    switch, force, vnum, zreset, etc.
  - Level-gated: LVL_IMMORT(71) through LVL_IMPL(91)
- Port `act.other.c` (2,109 lines):
  - `dalila/commands/other.py`: Mixed commands: camp (accampati), hide,
    sneak, steal, visible, practice, group, quit, save, title, etc.
- Verify: god commands work, teleport, load mobs/objects, stat players

---

## Phase 6: Hardening (5-10h)

Goal: Production-ready. Migrate real players, stress test, deploy.

### P6-1: Player data migration (2-3h)
- Build migration tool: `tools/migrate_players.py`
  - Read every `struct char_file_u` from the C playerfile
  - Convert to Python format (JSON or SQLite)
  - Validate: stats, inventory, skills, proficienze, abilita, clan data
  - Handle: password hashes (crypt() → modern hashing with backward compat)
  - Migrate object rent files from binary to new format
- Verify: migrate all existing players, login with each, spot-check stats

### P6-2: Performance testing (1-2h)
- Write load test: 100+ concurrent telnet connections
- Profile game loop under load (asyncio performance)
- Benchmark: world file loading time, command processing latency
- Memory usage comparison vs C version
- Verify: no connection drops, no command lag, memory stable

### P6-3: Integration testing (1-2h)
- Side-by-side testing: C on port 4001, Python on port 4002
- Automated comparison of command outputs
- Walk-through test: login, explore, fight, craft, die, re-login
- Trigger test: verify DG scripts fire identically
- Verify: outputs match between C and Python versions

### P6-4: Documentation and deployment (1-2h)
- Write operator documentation: how to run, how to configure, how to migrate
- Update `shell.nix` or add `flake.nix` for Python 3.12 environment
- Deploy to target server, test with real players on a staging port
- Cutover plan: stop C server, migrate playerfiles, start Python server

---

## Risk register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Binary playerfile format has undocumented padding/alignment | Data corruption on migration | Compare byte-for-byte with C sizeof(), use `struct.calcsize()` |
| DG Scripts have edge cases not obvious from code | Triggers behave differently | Test every .trg file, compare output with C version |
| Italian text encoding (Latin-1 vs UTF-8) | Garbled characters | Detect encoding per-file, convert consistently, test accented chars |
| Floating point combat formulas differ | Damage numbers off | Use identical integer math, never convert C int math to float |
| OLC save format must be readable by both versions | Cannot rollback | Keep original save format, add Python format alongside |
| Global mutable state (C globals) | Hard to port cleanly | Create a `GameState` singleton, explicit dependency injection |

## File size reference (largest C files)

| File | Lines | Primary purpose |
|------|-------|----------------|
| mestieri.c | 5,901 | Crafting system |
| spec_procs.c | 5,237 | Special mob/room procedures |
| act.wizard.c | 4,686 | Immortal commands |
| db.c | 4,101 | World loading, boot sequence |
| clan.c | 4,009 | Kingdom management |
| act.informative.c | 3,891 | Look, score, who, where |
| fight.c | 3,768 | Combat engine |
| act.item.c | 3,083 | Item manipulation |
| interpreter.c | 3,047 | Command table, login flow |
| clan2.c | 2,854 | Extended kingdom features |
| comm.c | 2,798 | Network, game loop |
| dg_scripts.c | 2,592 | DG script engine |
| act.movement.c | 2,456 | Movement, doors, riding |
| spells.c | 2,318 | Spell effects |
| magic.c | 2,275 | Magic framework |
| shop.c | 2,258 | Shop system |
| act.other.c | 2,109 | Mixed commands |
| objsave.c | 2,012 | Object persistence |
| class.c | 1,996 | Class definitions |
| spell_parser.c | 1,971 | Spell parsing |
