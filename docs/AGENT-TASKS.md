# Dalila-MUD Agent Tasks

Pre-written prompts for spawning agents on each phase of the port.
Each task is self-contained -- an agent can work on it without additional context.

Before starting any task, read `CLAUDE.md` in the project root for hard rules,
coding conventions, and package structure.

---

## Phase 0: Foundation

### Task P0-1: Project Skeleton
```
Prompt:
Create the Python project skeleton for the Dalila-MUD port.

Read CLAUDE.md for the full package structure, then:
1. Create pyproject.toml with:
   - name: dalila-mud
   - requires-python: ">=3.12"
   - dependencies: [] (no external deps)
   - optional-dependencies: {dev: ["pytest>=8.0"]}
   - scripts: {dalila: "dalila.__main__:main"}
2. Create dalila/__init__.py with __version__ = "0.1.0"
3. Create dalila/__main__.py with a stub main() that prints "Dalila-MUD Python port"
4. Create ALL __init__.py files for every subpackage listed in CLAUDE.md:
   models, parsers, net, engine, commands, combat, systems, scripting,
   olc, save, util, ai, misc
5. Create tests/conftest.py with a fixture that returns the path to lib/world/
6. Create tests/__init__.py and tests/test_parsers/__init__.py

Do NOT create any game logic -- only the skeleton.

Test: `python -m dalila` prints the banner. `python -m pytest tests/ -v` runs
with 0 tests collected and 0 errors.
```
Estimated: 30min
Dependencies: None
Output: pyproject.toml, dalila/**/__init__.py, tests/conftest.py

---

### Task P0-2: Constants and Enums
```
Prompt:
Port all C preprocessor constants from the Dalila-MUD codebase to Python enums.

Read CLAUDE.md first for conventions.

Source files to read:
- src/structs.h (1,768 lines) -- all #define groups
- src/spells.h (491 lines) -- spell/skill numbers
- src/constants.c (1,462 lines) -- string arrays for names/descriptions

Create dalila/models/constants.py with:
1. enum.IntEnum classes for discrete sets:
   - Direction (NORTH=0 through DOWN=5)
   - Position (POS_DEAD through POS_STANDING)
   - Sex, Class (character classes), SectorType
   - WearPosition (WEAR_LIGHT through all positions)
   - ItemType (ITEM_LIGHT, ITEM_SCROLL, etc.)
   - LiquidType (LIQ_WATER through LIQ_CAFFELIMONE=16)
   - DamageType (DANNO_FUOCO=0 through DANNO_FISICO=8)
   - Religion (RELIGIONE_NESSUNA=0 through RELIGIONE_THERION=4)
   - BodyLocation (LOCATION_TESTA=1 through LOCATION_RANDOM=7)
   - RentCode (RENT_UNDEF=0 through RENT_CAMP=6)
   - SunState, SkyCondition
   - PlayerEvent (LAST_BASH=0 through LAST_AFK=10, NUM_EVENTS=11)
   - ConnState (CON_PLAYING, CON_GET_NAME, etc.)
   - Level (LVL_IMPL=91, LVL_IMPLEMENTOR=90, LVL_BUILDER=85, etc.)

2. enum.IntFlag classes for bitfields:
   - RoomFlag (ROOM_DARK through all flags including ROOM_DAMAGE, ROOM_ARENA,
     ROOM_LANDMARK, ROOM_NO_DRAW)
   - ItemExtraFlag (ITEM_GLOW, ITEM_HUM, etc.)
   - WearFlag (ITEM_WEAR_TAKE, etc.)
   - AffectedBy (AFF_BLIND, etc.)
   - PlayerFlag, MobFlag
   - ContainerFlag (CONT_CLOSEABLE through CONT_LOCKED)

3. Spell/skill number constants from spells.h as an IntEnum Spell class

4. Game timing constants:
   OPT_USEC = 100000
   PASSES_PER_SEC = 10
   PULSE_ZONE = 100, PULSE_MOBILE = 100, PULSE_VIOLENCE = 30

5. Size/limit constants:
   MAX_SKILLS=200, MAX_PROFICIENZE=100, MAX_ABILITA=100, MAX_AFFECT=32,
   MAX_OBJ_AFFECT=6, NUM_OBJ_VAL_POSITIONS=10, etc.

6. String arrays from constants.c: class_names, direction_names,
   sector_types, wear_where, liquid_names, spell_names, etc.

Preserve ALL Italian constant names exactly (DANNO_FUOCO, RELIGIONE_SHAARR,
LOCATION_TESTA, etc.). Add English docstrings where helpful.

Test: `from dalila.models.constants import *` works. Spot-check:
Direction.NORTH == 0, RoomFlag.ROOM_DARK == 1, Religion.RELIGIONE_SHAARR == 1,
DamageType.DANNO_FUOCO == 0, Level.LVL_IMPL == 91.
```
Estimated: 1-2h
Dependencies: P0-1
Output: dalila/models/constants.py
Test: Import and value checks

---

### Task P0-3: Data Structure Models
```
Prompt:
Port the C data structures from structs.h to Python dataclasses.

Read CLAUDE.md first, then read src/structs.h (1,768 lines) completely.

Create the following files:

1. dalila/models/characters.py:
   - CharAbilityData: str, str_add, intel, wis, dex, con, cha
   - CharPointData: mana, max_mana, hit, max_hit, move, max_move, armor,
     gold, bank_gold, exp, fama, notorieta, hitroll, damroll
   - TimeData: birth, logon, played
   - TimeInfoData: hours, day, month, year
   - PlayerFee: has_fee, clan_fee, idclan, char_fee, idchar
   - CharSpecialDataSaved: alignment, idnum, act, affected_by (list of 4 ints),
     apply_saving_throw (list of 5 ints)
   - PlayerSpecialSaved: skills[201], proficienze[101], abilita[101],
     prof_choice[2], abil_choice[3], talks[3], wimp_level, freeze_level,
     invis_level, load_room, pref, bad_pws, conditions[3], stipendio (PlayerFee),
     clan_rank, wild_max_x/y_range, and all spare fields
   - CharPlayerData: passwd, name, short_descr, long_descr, description,
     title, poofin, poofout, sex, class_, level, hometown, time, weight, height,
     plus all camuffamento/disguise fields
   - CharData: full character with all sub-structures, linked list pointers
     replaced with Optional references or ID lookups
   - CharFileRecord: binary file format with struct format string for
     pack/unpack (used by migration tool)

2. dalila/models/objects.py:
   - ObjAffectedType: location, modifier
   - ObjFlagData: value[10], type_flag, wear_flags, extra_flags, weight,
     cost, cost_per_day, timer, bitvector[4], curr_slots, total_slots,
     min_level, tipo_materiale, num_materiale
   - ObjData: item_number, in_room, obj_flags, affected[6], name, description,
     short_description, action_description, extra descriptions, containment refs
   - ObjFileElem: binary element for rent files
   - RentInfo: time, rentcode, net_cost_per_diem, gold, account, nitems, spares
   - ExtraDescrData: keyword, description

3. dalila/models/rooms.py:
   - RoomDirectionData: general_description, keyword, exit_info, key, to_room
   - RoomData: number, zone, sector_type, name, description, ex_description,
     dir_option[6], room_flags, wild_modif, wild_rnum, light, contents, people,
     proto_script, script

4. dalila/models/world.py:
   - ZoneData: name, lifespan, age, top, reset_mode, reset commands
   - ResetCommand: command char, args, line number
   - ShopData: from shop.h
   - IndexData: vnum, number, func reference
   - TrigData, TrigProtoList, ScriptData from dg_scripts.h

Use @dataclass with appropriate defaults. Use Optional[] for nullable fields.
Import constants from dalila.models.constants. Add __slots__ where performance
matters (CharData, ObjData, RoomData will have thousands of instances).

Test: Import all models. Verify CharAbilityData has 7 fields, ObjFlagData.value
is a list of 10 ints, PlayerSpecialSaved.skills is length 201,
RoomData.dir_option is length 6.
```
Estimated: 2-3h
Dependencies: P0-2
Output: dalila/models/characters.py, objects.py, rooms.py, world.py
Test: Import validation, field count checks

---

### Task P0-4: World File Parsers
```
Prompt:
Port the world file parsers from db.c to Python.

Read CLAUDE.md first. Then read:
- src/db.c (4,101 lines) -- focus on: boot_db(), parse_room(), parse_mobile(),
  parse_object(), load_zones(), parse_shop() (or see shop.c, 2,258 lines),
  parse_trigger() (or see dg_db_scripts.c, 424 lines)
- One sample file from each type in lib/world/ to understand the format
- lib/world/wld/index.wld, lib/world/mob/index.mob, etc. (index files)

Create parsers in dalila/parsers/:

1. dalila/parsers/world.py -- parse .wld files
   - Read index.wld to get file list
   - Parse CircleMUD room format: vnum, name, description, zone, flags,
     sector, exits (direction, description, keyword, door flags, key, to_room),
     extra descriptions
   - Handle Dalila extensions (extra bitvectors, wild_modif, etc.)
   - Return list of RoomData objects

2. dalila/parsers/mobs.py -- parse .mob files
   - Read index.mob
   - Parse mob format: vnum, aliases, short_desc, long_desc, detail_desc,
     action flags, affected flags, alignment, type (S/E/C for simple/enhanced/complex),
     level, THAC0, AC, hp dice, damage dice, gold, exp, position, sex
   - Return list of mob prototypes

3. dalila/parsers/objects.py -- parse .obj files
   - Read index.obj
   - Handle NUM_OBJ_VAL_POSITIONS=10 (Dalila extension from standard 4)
   - Parse: vnum, aliases, short_desc, long_desc, action_desc, type, extra_flags,
     wear_flags, values[10], weight, cost, rent, affects, extra descriptions
   - Handle tipo_materiale, num_materiale, curr_slots, total_slots

4. dalila/parsers/zones.py -- parse .zon files
   - Read index.zon (220 zone files)
   - Parse zone header and reset commands (M/O/G/P/E/D/R/T commands)

5. dalila/parsers/shops.py -- parse .shp files
   - 87 shop files, format from shop.c boot_the_shops()

6. dalila/parsers/triggers.py -- parse .trg files
   - 92 trigger files, format from dg_db_scripts.c

7. dalila/parsers/wilderness.py -- parse .map + wild_table files
   - Wilderness maps in lib/world/wild/*.map
   - wild_table defines wilderness terrain types

Write tests in tests/test_parsers/ that load the REAL world files from lib/world/
and verify:
- Number of rooms parsed matches expected count
- Number of mob prototypes matches
- Number of object prototypes matches
- Number of zones matches (220 .zon files)
- Number of shops matches (87 .shp files)
- Number of triggers matches (92 .trg files)
- No parse errors on any file
- Spot-check: room vnum 0 exists, first zone has correct name

All parsers must handle the ~ delimiter, the $ end-of-file marker, and
multi-line string fields that are standard CircleMUD format.

Test: python -m pytest tests/test_parsers/ -v --world-dir=lib/world
All parsers load all files without errors. Counts match C boot output.
```
Estimated: 2-3h
Dependencies: P0-3
Output: dalila/parsers/*.py, tests/test_parsers/*.py
Test: Load all 958 world files, verify counts

---

## Phase 1: Core Engine

### Task P1-1: Asyncio Network Server
```
Prompt:
Port the networking layer from comm.c to Python asyncio.

Read CLAUDE.md first. Then read:
- src/comm.c (2,798 lines) -- focus on: init_game(), game_loop(),
  new_descriptor(), close_socket(), process_input(), process_output(),
  write_to_output(), send_to_char(), send_to_room(), send_to_all()
- src/comm.h -- descriptor_data struct, output buffering
- src/telnet.h (319 lines) -- telnet protocol constants
- src/ban.c (447 lines) -- site ban checking

Create:

1. dalila/net/server.py:
   - AsyncioServer class wrapping asyncio.start_server()
   - Bind to configurable port (default 4000)
   - Accept connections, create Descriptor per client
   - Handle disconnections gracefully
   - Max connections limit
   - Ban checking against lib/etc/badsites

2. dalila/net/descriptor.py:
   - Descriptor class (equivalent to struct descriptor_data):
     - Connection state (ConnState enum)
     - Input buffer with MAX_RAW_INPUT_LENGTH (512) limit
     - Output buffer with SMALL_BUFSIZE (1024) and LARGE_BUFSIZE (12288)
     - History (last 5 commands)
     - Associated character reference
     - Host/IP tracking (HOST_LENGTH=30)
     - Snoop chain
   - Input processing: line buffering, backspace handling
   - Output processing: page_string for long text

3. dalila/net/telnet.py:
   - IAC sequence handling
   - Echo on/off (for password input)
   - NAWS (terminal size negotiation)
   - Strip telnet sequences from input

Key functions to port:
- send_to_char(msg, ch) -- send text to one character
- send_to_room(msg, room, ...) -- send to everyone in a room
- send_to_all(msg) -- broadcast
- write_to_output(txt, descriptor) -- low-level output
- process_input(descriptor) -- read from socket, buffer lines
- process_output(descriptor) -- flush output buffer to socket

Load lib/text/greetings as the connection greeting banner.

Test: Start server on port 4000. Telnet in. See greeting text. Type something,
see it echoed or "command not found". Disconnect cleanly. Connect two clients
simultaneously.
```
Estimated: 3-4h
Dependencies: P0-1, P0-2
Output: dalila/net/server.py, descriptor.py, telnet.py
Test: Telnet connect/disconnect, multi-client

---

### Task P1-2: Command Interpreter and Login
```
Prompt:
Port the command interpreter and login state machine from interpreter.c.

Read CLAUDE.md first. Then read:
- src/interpreter.c (3,047 lines) -- command table at line 373 (~600 entries),
  nanny() state machine at line 2219, command_interpreter() function
- src/interpreter.h -- command_info struct, ACMD macro, connection states

Create dalila/engine/interpreter.py with:

1. CommandInfo dataclass:
   - command: str (the keyword)
   - minimum_position: Position enum
   - command_func: Callable
   - minimum_level: int
   - subcmd: int

2. COMMAND_TABLE: list of CommandInfo entries
   - Port ALL ~600 entries from cmd_info[] (line 373+)
   - Include every Italian alias: nord, sud, est, ovest, alto, basso,
     guarda, prendi, lascia, dici, parla, uccidi, fuggi, pugnala,
     indossa, rimuovi, impugna, bevi, mangia, etc.
   - Include every English alias alongside Italian ones
   - All stub to a "not_yet_implemented" function initially

3. command_interpreter(ch, argument):
   - Strip leading spaces
   - Extract first word (command)
   - Search COMMAND_TABLE with abbreviation matching (prefix match)
   - Check position requirement
   - Check level requirement
   - Call special proc first (return if handled)
   - Dispatch to command function

4. nanny(descriptor, argument):
   - Full login state machine with states:
     CON_GET_NAME, CON_NAME_CNFRM, CON_PASSWORD, CON_NEWPASSWD,
     CON_CNFPASSWD, CON_QSEX, CON_QCLASS, CON_RMOTD, CON_MENU,
     CON_PLAYING, CON_CHPWD_GETOLD, CON_CHPWD_GETNEW, CON_CHPWD_VRFY,
     CON_DELCNF1, CON_DELCNF2
   - Dalila-specific states: hometown choice, stat rolling, mestieri
     selection, abilita selection, iniziazione (religion choice)
   - Load menus from lib/text/ (menu, menu-b, menu-c variants)
   - Password handling with crypt()

Test: Full login flow -- connect, enter name, create new character (pick sex,
class, hometown, stats, mestiere, abilita, religion), see MOTD, enter game.
Also test: existing character login, bad password rejection, menu navigation.
```
Estimated: 3-4h
Dependencies: P1-1, P0-3
Output: dalila/engine/interpreter.py
Test: Complete login flow, command dispatch with stubs

---

### Task P1-3: Game Loop and Timers
```
Prompt:
Port the game loop, heartbeat system, and regeneration from comm.c and limits.c.

Read CLAUDE.md first. Then read:
- src/comm.c -- game_loop() function, heartbeat() calls
- src/limits.c (1,244 lines) -- point_update(), check_idling(), gain functions
- src/regen.c (312 lines) -- regeneration calculations
- src/events.c (125 lines) -- event queue
- src/queue.c (175 lines) -- priority queue for events
- src/weather.c (210 lines) -- weather updates

Create:

1. dalila/engine/game_loop.py:
   - GameLoop class running on asyncio event loop
   - Pulse counter incrementing every OPT_USEC (100ms)
   - Scheduled callbacks at correct intervals:
     - Every PULSE_VIOLENCE (3s): perform_violence() on all fighting chars
     - Every PULSE_MOBILE (10s): mobile_activity()
     - Every PULSE_ZONE (10s): zone_update() for resets
     - Every 75 passes (7.5s): point_update() for regen
     - Every minute: weather_change(), check_idling()
     - Stubs for all callbacks initially
   - Proper shutdown handling (SIGTERM, SIGINT)

2. dalila/engine/limits.py from limits.c:
   - hit_gain(ch), mana_gain(ch), move_gain(ch) -- HP/mana/move regen rates
   - point_update() -- iterate all characters, apply regen
   - check_idling() -- disconnect idle players
   - Hunger/thirst/drunk decay (conditions[DRUNK/FULL/THIRST])

3. dalila/engine/events.py from events.c + queue.c:
   - EventQueue with priority ordering
   - Event scheduling and firing
   - Used by combat, DG scripts, and custom systems

4. dalila/util/weather.py from weather.c:
   - Weather state machine (SUN_DARK/RISE/LIGHT/SET, SKY_CLOUDLESS through LIGHTNING)
   - weather_change() called once per minute

Test: Start game loop, verify pulse counters increment at correct rate.
Verify point_update fires every 7.5s. Run for 60s, check weather ticks.
No CPU spin (should idle between pulses).
```
Estimated: 2-3h
Dependencies: P1-1, P0-2
Output: dalila/engine/game_loop.py, limits.py, events.py; dalila/util/weather.py
Test: Pulse timing verification, no CPU spin

---

## Phase 2: World Interaction

### Task P2-1: Movement and Room Display
```
Prompt:
Port room display and movement commands from act.movement.c and act.informative.c.

Read CLAUDE.md first. Then read:
- src/act.movement.c (2,456 lines) -- all movement functions
- src/act.informative.c (3,891 lines) -- focus on look_at_room(),
  list_char_to_char(), list_obj_to_char(), do_look(), do_exits()
- src/graph.c (388 lines) -- BFS pathfinding
- src/wilderness.c -- wilderness map display sections

Create:

1. dalila/commands/movement.py:
   - do_move(ch, direction): Move character between rooms
     - Check: not fighting, position standing, exit exists, door not closed,
       enough movement points (sector-based cost), not riding check
     - Send departure/arrival messages to rooms
   - do_open/do_close/do_lock/do_unlock: Door manipulation with key checking
   - do_enter/do_leave: Special enter/leave for portals
   - do_stand/do_sit/do_rest/do_sleep/do_wake: Position changes
   - do_ride (cavalcare): Mount/dismount riding animals
   - do_follow/do_group: Follow and group system

2. dalila/commands/informative.py (partial -- look/exits only):
   - look_at_room(ch): Display room name, description, exits, people, objects
   - do_look(ch, arg): Look at room, person, object, direction, extra desc
   - do_exits(ch): List visible exits with Italian direction names
   - list_char_to_char(list, ch): List visible people in room
   - list_obj_to_char(list, ch): List visible objects in room

3. dalila/engine/handler.py (partial -- movement-related):
   - char_from_room(ch): Remove character from room
   - char_to_room(ch, room): Place character in room
   - Linked list management for room.people

Test: Login, look at start room (verify Italian description appears).
Move north/sud/est/ovest. See new room descriptions. Try locked door.
Check movement point deduction. Verify exit list shows Italian direction names.
```
Estimated: 3-4h
Dependencies: P1-2, P0-4
Output: dalila/commands/movement.py, informative.py (partial), engine/handler.py (partial)
Test: Walk around world, see rooms, use doors

---

### Task P2-2: Item Manipulation and Communication
```
Prompt:
Port item commands from act.item.c and communication from act.comm.c.

Read CLAUDE.md first. Then read:
- src/act.item.c (3,083 lines) -- all item manipulation
- src/act.comm.c (1,034 lines) -- communication commands
- src/act.social.c (282 lines) -- social commands
- src/handler.c (1,685 lines) -- object/character lookup functions

Create:

1. dalila/commands/item.py from act.item.c:
   - do_get/prendi: Pick up objects (from room, from container)
   - do_drop/lascia: Drop objects
   - do_put/metti: Put objects in containers
   - do_give/dai: Give objects to characters
   - do_wear/indossa: Wear equipment (check wear positions, slots)
   - do_remove/rimuovi: Remove equipment
   - do_wield/impugna: Wield weapons
   - do_grab/afferra: Hold items
   - do_drink/bevi, do_eat/mangia, do_pour/versa: Consumables
   - do_hang/aggancia: Hang items (Dalila-specific)
   - Container logic: open/close/lock/unlock containers

2. dalila/commands/communication.py from act.comm.c:
   - do_say/dici/': Say to room
   - do_tell/parla: Tell to specific player (with TELLS_STORED=10 history)
   - do_whisper/sussurra: Whisper to adjacent character
   - do_shout/urla: Shout across zone
   - do_gossip: Global channel
   - do_gsay: Group say
   - do_emote/:: Emote action
   - Soundproof room checking (ROOM_SOUNDPROOF blocks shout/gossip)

3. dalila/commands/social.py from act.social.c:
   - Social command framework (abbraccia, accarezza, accigliati, etc.)
   - Messages for: no target, self target, char target, mob target

4. dalila/engine/handler.py (complete) from handler.c:
   - get_char_room(name, room): Find character in room by name
   - get_char_vis(ch, name): Find visible character anywhere
   - get_obj_in_list_vis(ch, name, list): Find object in list
   - get_obj_vis(ch, name): Find visible object anywhere
   - affect_to_char(ch, affect): Apply affect
   - affect_remove(ch, affect): Remove affect
   - equip_char(ch, obj, pos): Equip item
   - unequip_char(ch, pos): Unequip item
   - obj_to_room/obj_from_room/obj_to_char/obj_from_char: Object movement
   - Name matching with abbreviation support

Test: Pick up items, drop them, wear equipment, check inventory.
Say something (verify two clients see it). Tell between two players.
Test container operations. Test soundproof room blocks.
```
Estimated: 4-5h
Dependencies: P2-1
Output: dalila/commands/item.py, communication.py, social.py; dalila/engine/handler.py
Test: Item manipulation, two-client communication

---

## Phase 3: Combat and Magic

### Task P3-1: Combat Engine
```
Prompt:
Port the combat engine from fight.c and offensive commands from act.offensive.c.

Read CLAUDE.md first. Then read:
- src/fight.c (3,768 lines) -- complete combat system
- src/act.offensive.c (1,791 lines) -- combat commands
- src/structs.h -- LOCATION_* body part defines, DANNO_* damage types,
  notorieta/fama fields in char_point_data

Create:

1. dalila/combat/fight.py from fight.c:
   - set_fighting(ch, victim): Enter combat
   - stop_fighting(ch): Leave combat
   - hit(ch, victim, type): Single attack roll
     - THAC0 calculation, AC comparison, hit/miss
     - Damage calculation with weapon dice
   - damage(ch, victim, dam, attacktype): Apply damage
     - Critical hit system: roll for LOCATION_TESTA, LOCATION_BRACCIO_D/S,
       LOCATION_TORSO, LOCATION_GAMBA_D/S, LOCATION_RANDOM
     - Damage type handling: DANNO_FUOCO, DANNO_GHIACCIO, DANNO_ELETTRICITA,
       DANNO_ACIDO, DANNO_SHAARR, DANNO_XHYPHYS, DANNO_THERION, DANNO_SILUE,
       DANNO_FISICO
     - Resistances and vulnerabilities
   - perform_violence(): Called every PULSE_VIOLENCE (3s), iterate all fighters
   - die(ch): Character death, corpse creation, exp loss
   - raw_kill(ch, killer): Kill without combat (used by scripts)
   - group_gain(killer, victim): Experience distribution to group
   - Notorieta/fama updates (KILL, TKILL, WKILL, THIEF, WANTED, etc.)
   - death_cry(): Death message to room and adjacent rooms

2. dalila/commands/offensive.py from act.offensive.c:
   - do_kill/uccidi: Initiate combat
   - do_flee/fuggi: Attempt to flee combat
   - do_kick/calcia: Kick attack
   - do_bash/spingi: Bash/shield bash
   - do_backstab/pugnala: Backstab
   - do_agguato: Ambush (Dalila-specific, with last_agguato timer)
   - do_steal/ruba: Steal from character
   - do_rescue/salva: Rescue ally from combat
   - do_disarm: Disarm opponent

All damage formulas must use INTEGER ARITHMETIC identical to the C version.
Do not convert to float at any point.

Test: Engage a mob in combat. Verify hit/miss messages appear.
Verify damage numbers match C version formulas. Die, see death message,
respawn at mortal start room. Check critical hit location messages.
Verify notorieta changes on kill.
```
Estimated: 5-7h
Dependencies: P2-1, P1-3
Output: dalila/combat/fight.py, dalila/commands/offensive.py
Test: Combat engagement, damage, death, respawn

---

### Task P3-2: Spell System
```
Prompt:
Port the magic system from magic.c, spells.c, spell_parser.c, and class.c.

Read CLAUDE.md first. Then read:
- src/spell_parser.c (1,971 lines) -- spell casting framework
- src/spells.c (2,318 lines) -- individual spell implementations
- src/magic.c (2,275 lines) -- magic damage, saving throws, effect framework
- src/class.c (1,996 lines) -- class definitions, spell assignment, THAC0 tables
- src/spells.h (491 lines) -- spell number constants, all skill/spell defines

Create:

1. dalila/combat/spell_parser.py from spell_parser.c:
   - do_cast(ch, argument): Parse spell name, find target, check mana, cast
   - call_magic(): Dispatch to appropriate mag_* function based on spell type
   - Spell types: MAG_DAMAGE, MAG_AFFECTS, MAG_UNAFFECTS, MAG_POINTS,
     MAG_ALTER_OBJS, MAG_GROUPS, MAG_MASSES, MAG_SUMMONS, MAG_CREATIONS,
     MAG_AREAS
   - Spell info table: mana cost, min level per class, targets, routines

2. dalila/combat/spells.py from spells.c:
   - Individual spell effect functions
   - Spell constants from spells.h (all SPELL_* and SKILL_* defines)
   - spell_info[] table with all spell definitions

3. dalila/combat/magic.py from magic.c:
   - mag_damage(level, ch, victim, spellnum): Direct damage spells
   - mag_affects(level, ch, victim, spellnum): Buff/debuff spells
   - mag_unaffects(level, ch, victim, spellnum): Remove effects
   - mag_points(level, ch, victim, spellnum): Heal/restore spells
   - mag_alter_objs(): Change object properties
   - mag_summons(): Summon creatures
   - mag_creations(): Create items from nothing
   - mag_savingthrow(ch, type, modifier): Saving throw rolls
   - Religion-specific damage bonuses (DANNO_SHAARR etc. from fight.c)

4. dalila/combat/class_data.py from class.c:
   - Class definitions: spell/skill assignments per class
   - THAC0 progression tables
   - Level titles (titles[][] array)
   - Stat limits per class
   - Experience thresholds

Test: Cast a damage spell, verify damage matches C formula.
Cast a buff spell, verify affect appears on character.
Check mana cost deduction. Verify saving throws.
Check class-restricted spells are properly gated.
```
Estimated: 5-7h
Dependencies: P3-1
Output: dalila/combat/spell_parser.py, spells.py, magic.py, class_data.py
Test: Cast spells, verify formulas match C version

---

## Phase 4: Advanced Systems

### Task P4-1: DG Scripting Engine
```
Prompt:
Port the DG (Death Gate) scripting engine from all dg_*.c files.

Read CLAUDE.md first. Then read ALL of these files in order:
- src/dg_scripts.h -- trigger types, script data structures
- src/dg_scripts.c (2,592 lines) -- main script engine
- src/dg_triggers.c (898 lines) -- trigger evaluation and firing
- src/dg_db_scripts.c (424 lines) -- script loading from files
- src/dg_mobcmd.c (1,084 lines) -- mob script commands
- src/dg_objcmd.c (748 lines) -- object script commands
- src/dg_wldcmd.c (656 lines) -- room script commands
- src/dg_comm.c (193 lines) -- script output
- src/dg_misc.c (293 lines) -- utility functions
- src/dg_handler.c (69 lines) -- script handler
- src/dg_event.c (106 lines) -- script events

Total: 7,867 lines across 11 files.

Create the full dalila/scripting/ package:

1. dalila/scripting/engine.py (from dg_scripts.c):
   - Script execution loop: read line, evaluate, branch
   - Variable system: %actor%, %self%, %random.name%, %object.vnum%, etc.
   - Global variables (MAX_GBL_VAR_SAVED=128, MAX_NAME_VAR_LENGTH=20, MAX_VAR_LENGTH=150)
   - Control flow: if/elseif/else/end, while/done, switch/case/default/break
   - Wait states: wait command pauses script execution
   - eval/extract/makeuid/nop built-in commands

2. dalila/scripting/triggers.py (from dg_triggers.c):
   - Trigger types for mobs, objects, and rooms:
     MTRIG_GREET, MTRIG_ENTRY, MTRIG_COMMAND, MTRIG_SPEECH, MTRIG_ACT,
     MTRIG_DEATH, MTRIG_FIGHT, MTRIG_HITPRCNT, MTRIG_BRIBE, MTRIG_RECEIVE,
     OTRIG_GET, OTRIG_DROP, OTRIG_GIVE, OTRIG_WEAR, OTRIG_REMOVE, OTRIG_COMMAND,
     WTRIG_ENTER, WTRIG_COMMAND, WTRIG_SPEECH, WTRIG_RESET, WTRIG_DROP, etc.
   - Trigger evaluation: check conditions, fire if matched

3-8. Remaining files: mob_cmds.py, obj_cmds.py, wld_cmds.py, db_scripts.py,
     comm.py, misc.py, handler.py, events.py

All 92 trigger files in lib/world/trg/ must load and parse correctly.
Variable substitution must handle nested references.

Test:
- Load all 92 .trg files without errors
- Create a test trigger that fires on room entry (WTRIG_ENTER), verify it fires
- Test variable substitution: %actor.name%, %self.vnum%, %random.name%
- Test control flow: if/else/end, while loop with counter
- Test mob commands: mecho, msend, mkill
```
Estimated: 8-12h
Dependencies: P2-2, P1-3
Output: dalila/scripting/*.py (10 files)
Test: Load all triggers, fire test triggers, variable substitution

---

### Task P4-2: Crafting System (Mestieri)
```
Prompt:
Port the crafting system from mestieri.c.

Read CLAUDE.md first. Then read:
- src/mestieri.c (5,901 lines) -- complete crafting system
- src/mestieri.h -- mestieri data structures and constants
- src/act.create.c (736 lines) -- creation commands that integrate with mestieri
- src/structs.h -- tipo_materiale, num_materiale fields in obj_flag_data

Create:

1. dalila/systems/mestieri.py from mestieri.c + mestieri.h:
   - All mestiere types (professions/trades)
   - Recipe system: what materials + what skill = what product
   - Skill progression: practice, failure rates, mastery
   - Material system (tipo_materiale, num_materiale on objects)
   - menu_mestieri() -- the character creation trade selection menu
   - All crafting commands

2. dalila/commands/create.py from act.create.c:
   - do_acostruzione: Construction commands
   - do_affila: Sharpening/whetstoning
   - Other creation-related commands from the cmd_info table

Port EVERY function. The crafting system is Dalila's largest custom feature.
Preserve all Italian function names, variable names, and string constants.

Test: Select a mestiere during character creation. Use crafting commands.
Verify material requirements are checked. Verify skill progression works.
Verify created objects have correct tipo_materiale and num_materiale.
```
Estimated: 4-6h
Dependencies: P2-2
Output: dalila/systems/mestieri.py, dalila/commands/create.py
Test: Craft items, check recipes, skill progression

---

### Task P4-3: Kingdom System (Regni/Clan)
```
Prompt:
Port the kingdom/clan system from clan.c, clan2.c, and eserciti.c.

Read CLAUDE.md first. Then read:
- src/clan.c (4,009 lines) -- core clan management
- src/clan.h (311 lines) -- clan data structures
- src/clan2.c (2,854 lines) -- extended kingdom features
- src/clan2.h -- clan2 structures
- src/eserciti.c (534 lines) -- army management
- src/eserciti.h -- army structures
- src/structs.h -- clan_rank, stipendio (PlayerFee) in player_special_data
- lib/etc/clans/ and lib/etc/new_clans/ -- clan data files
- lib/etc/eserciti/ -- army data files
- lib/text/regni -- kingdom text descriptions

Create:

1. dalila/systems/clan.py from clan.c + clan.h:
   - Clan creation, destruction, editing
   - Membership: join, leave, promote, demote
   - Rank system (clan_rank in player_special_data)
   - Fee/stipendio system (PlayerFee struct)
   - Clan data loading/saving from lib/etc/clans/ and lib/etc/new_clans/
   - All clan commands from cmd_info table

2. dalila/systems/clan2.py from clan2.c + clan2.h:
   - Inter-clan diplomacy: alliances, wars, treaties
   - Territory control
   - Extended kingdom management
   - Religion-kingdom integration (assign_to_regno)

3. dalila/systems/eserciti.py from eserciti.c + eserciti.h:
   - Army creation and management
   - Army data from lib/etc/eserciti/
   - Integration with kingdom system

Test: Create a clan, add members, set ranks. Test fee collection.
Load existing clan data from lib/etc/clans/. Test diplomacy between clans.
Verify army management commands.
```
Estimated: 4-6h
Dependencies: P2-2
Output: dalila/systems/clan.py, clan2.py, eserciti.py
Test: Clan operations, data loading, diplomacy

---

### Task P4-4: Wilderness System
```
Prompt:
Port the wilderness system from wilderness.c.

Read CLAUDE.md first. Then read:
- src/wilderness.c (1,829 lines) -- wilderness engine
- src/wilderness.h (95 lines) -- wilderness structures
- src/wedit.c (620 lines) -- wilderness OLC editor
- lib/world/wild/ -- all .map and .wld files, wild_table
- src/structs.h -- wild_modif, wild_rnum in room_data;
  wildhunt, client, wild_max_x_range, wild_max_y_range in char_special_data

Create:

1. dalila/systems/wilderness.py from wilderness.c + wilderness.h:
   - Wilderness map loading from .map files
   - wild_table terrain type definitions
   - Map display rendering (ASCII map sent to player)
   - Client-specific output (client field for different terminal types)
   - Wilderness movement (sector costs, visibility range)
   - Wilderness hunting (wildhunt tracking)
   - Room generation for wilderness coordinates
   - wild_max_x_range / wild_max_y_range player visibility settings

2. dalila/olc/wedit.py from wedit.c:
   - Wilderness OLC editor for building wilderness areas

Test: Enter a wilderness area. See ASCII map display.
Move through wilderness, verify map updates. Check terrain types
from wild_table are applied correctly. Verify .map files all parse.
```
Estimated: 2-3h
Dependencies: P0-4, P2-1
Output: dalila/systems/wilderness.py, dalila/olc/wedit.py
Test: Map display, wilderness movement, .map parsing

---

## Phase 5: Everything Else

### Task P5-1: OLC Editors
```
Prompt:
Port all Online Creation (OLC) editors.

Read CLAUDE.md first. Then read:
- src/olc.c (715 lines) -- OLC framework
- src/olc.h (356 lines) -- OLC constants and structures
- src/redit.c (1,229 lines) -- Room editor
- src/oedit.c (1,826 lines) -- Object editor
- src/medit.c (1,562 lines) -- Mobile/NPC editor
- src/sedit.c (1,498 lines) -- Shop editor
- src/zedit.c (1,631 lines) -- Zone editor
- src/dg_olc.c (804 lines) -- Trigger editor

Total: 9,885 lines across 8 files.

Create the full dalila/olc/ package:

1. dalila/olc/olc.py -- OLC framework, state management, save/cleanup
2. dalila/olc/redit.py -- Room editor: modify room properties, exits, flags
3. dalila/olc/oedit.py -- Object editor: modify obj values, flags, affects
4. dalila/olc/medit.py -- Mob editor: modify mob stats, flags, equipment
5. dalila/olc/sedit.py -- Shop editor: modify buy/sell types, prices
6. dalila/olc/zedit.py -- Zone editor: modify reset commands, zone props
7. dalila/olc/dg_olc.py -- Trigger editor: modify script text, trigger types

OLC editors integrate with nanny() -- when a player enters OLC mode,
their connection state changes and input routes through the OLC parser
instead of the normal command interpreter.

Each editor must be able to save changes back to the world file format
that the parsers can re-read.

Test: Enter OLC as an immortal (LVL_BUILDER=85+). Edit a room (redit),
change its description. Save. Verify the change persists. Test each editor
type at least once.
```
Estimated: 4-6h
Dependencies: P2-2, P0-4
Output: dalila/olc/*.py (7 files)
Test: Edit and save with each OLC editor

---

### Task P5-2: Player Persistence and Migration
```
Prompt:
Port player saving/loading and build the binary playerfile migration tool.

Read CLAUDE.md first. Then read:
- src/structs.h -- char_file_u struct (the binary playerfile format), starting
  around line 1279 with player_special_data_saved, through the end of the file
- src/db.c -- load_char(), save_char(), init_char(), store_to_char()
- src/objsave.c (2,012 lines) -- rent file handling, crash-save
- src/house.c (1,030 lines) -- house saving/loading
- src/alias.c (133 lines) -- alias loading/saving

Create:

1. dalila/save/migration.py:
   - Read binary playerfile (struct char_file_u)
   - Field layout from structs.h -- use Python struct module with exact format:
     passwd[11], name[20], title[80], description[240], sex, class, level,
     hometown, time_data, weight, height, abilities, points, affected_by,
     skills[201], proficienze[101], abilita[101], conditions[3], etc.
   - Handle struct alignment/padding identical to the C compiler
   - Convert each record to Python CharFileRecord dataclass
   - Export to JSON format

2. dalila/save/player_store.py:
   - New player storage in JSON or SQLite
   - save_char(ch): Serialize character to storage
   - load_char(name): Deserialize from storage
   - create_entry(name): New player slot
   - Player index management (replaces player_table array)

3. dalila/save/objsave.py from objsave.c:
   - Crash-save: auto-save player inventory on disconnect
   - Rent system: save/load with rent cost
   - obj_file_elem binary format handling
   - rent_info header handling

4. dalila/save/house.py from house.c:
   - House loading/saving
   - House ownership management

Test: Read an actual C binary playerfile (if available in lib/etc/mobs/ or
similar). Verify field extraction matches. Create a new character in Python,
save, reload, verify all fields preserved. Test crash-save recovery.
```
Estimated: 3-4h
Dependencies: P0-3, P1-2
Output: dalila/save/migration.py, player_store.py, objsave.py, house.py
Test: Binary playerfile read, save/load cycle

---

## Phase 6: Hardening

### Task P6-1: Integration Testing Suite
```
Prompt:
Build a comprehensive integration test suite that validates the Python port
against the C version's behavior.

Read CLAUDE.md first.

Create tests/integration/:

1. tests/integration/test_boot.py:
   - Boot both C and Python versions
   - Compare: room count, mob count, obj count, zone count, shop count, trigger count
   - Verify wilderness map loading matches
   - Verify all index files processed identically

2. tests/integration/test_commands.py:
   - Automated telnet client that connects to both servers
   - Run identical command sequences, compare output
   - Test cases:
     - Login flow (new character + existing character)
     - Movement (walk a predefined path, compare room descriptions)
     - Look (look at room, at mob, at object, in container)
     - Inventory (get, drop, wear, remove)
     - Communication (say, tell, shout)
     - Combat (attack mob, verify hit/damage messages pattern-match)
     - Crafting (basic mestieri operations)
     - Clan commands (if test clan exists)

3. tests/integration/test_scripts.py:
   - Load all 92 trigger files in both versions
   - Fire each trigger type, compare output
   - Test variable substitution edge cases

4. tests/integration/test_persistence.py:
   - Create character in Python version, save, reload, verify
   - Migrate a C playerfile, login in Python, verify stats

Write a runner script: tools/compare_versions.sh that starts C on 4001,
Python on 4002, runs all integration tests, reports differences.

Test: All integration tests pass with zero behavioral differences.
```
Estimated: 3-4h
Dependencies: All previous phases
Output: tests/integration/*.py, tools/compare_versions.sh
Test: Zero differences between C and Python versions

---

### Task P6-2: Performance and Deployment
```
Prompt:
Performance test the Python port and prepare for deployment.

Read CLAUDE.md first.

Create:

1. tools/loadtest.py:
   - Spawn 100+ concurrent asyncio telnet connections
   - Each connection: login, walk random path, send commands, logout
   - Measure: connection latency, command processing time, memory usage
   - Report: p50/p95/p99 latencies, peak memory, connections/second

2. tools/migrate_players.py:
   - Read all records from C binary playerfile
   - Convert to Python JSON/SQLite format
   - Validate each record (stats in range, skills valid, etc.)
   - Report: total players migrated, any errors
   - Password handling: preserve crypt() hashes for backward compat

3. Update pyproject.toml and shell.nix/flake.nix:
   - Proper packaging for deployment
   - NixOS-compatible environment
   - systemd service file template

4. Write DEPLOY.md:
   - Step-by-step deployment guide
   - Cutover procedure: stop C, migrate, start Python
   - Rollback procedure: stop Python, start C (playerfile compat)

Test: 100 concurrent connections sustained for 5 minutes with no drops.
Command latency p99 < 100ms. Memory usage stable (no leaks over 30min run).
Full player migration completes without errors.
```
Estimated: 3-4h
Dependencies: All previous phases
Output: tools/loadtest.py, migrate_players.py, DEPLOY.md
Test: Load test passes, migration completes

---

## Summary

| Phase | Tasks | Est. hours | Key output |
|-------|-------|-----------|------------|
| P0: Foundation | P0-1 through P0-4 | 4-6h | Skeleton, models, parsers |
| P1: Core Engine | P1-1 through P1-3 | 8-12h | Network, game loop, login |
| P2: World Interaction | P2-1 through P2-2 | 7-9h | Movement, items, communication |
| P3: Combat + Magic | P3-1 through P3-2 | 10-14h | Combat, spells, abilities |
| P4: Advanced Systems | P4-1 through P4-4 | 18-27h | DG scripts, mestieri, clans, wilderness |
| P5: Everything Else | P5-1 through P5-2 | 7-10h | OLC, persistence, utilities |
| P6: Hardening | P6-1 through P6-2 | 6-8h | Integration tests, performance, deploy |
| **Total** | **15 tasks** | **60-86h** | **Full port** |

Note: estimates assume agent work with focused, uninterrupted execution.
Real-world agent time may vary. Jhonata review time: ~10-15h total across
all phases (code review, manual testing, Italian text spot-checks).
