"""Command interpreter -- dispatch table and starter commands.

Ported from command_interpreter(), cmd_info[] in interpreter.c.
Phase 1 implements: look, movement, say, who, quit, score.
All other commands show "not yet available" placeholder.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from dalila.constants import (
    ConnState,
    Direction,
    ExitInfo,
    LVL_IMMORT,
    NOWHERE,
    NUM_OF_DIRS,
    CharClass,
    Position,
    Sex,
    SkyCondition,
)

if TYPE_CHECKING:
    from dalila.engine.game_loop import GameWorld, LiveRoom
    from dalila.models.character import CharData
    from dalila.net.descriptor import Descriptor

log = logging.getLogger(__name__)

# Type alias for command functions
CommandFunc = Callable[["CharData", str, "Descriptor", "GameWorld"], None]


@dataclass
class CommandInfo:
    """A command table entry.

    Ported from struct command_info in interpreter.h.
    """
    command: str             # Command word (e.g. "look", "guarda")
    minimum_position: int    # Minimum position to execute (POS_*)
    command_func: CommandFunc # Function to call
    minimum_level: int       # Minimum level required
    subcmd: int = 0          # Sub-command number (SCMD_*)


# Direction names for display
DIR_NAMES: list[str] = ["north", "east", "south", "west", "up", "down"]
DIR_NAMES_IT: list[str] = ["nord", "est", "sud", "ovest", "alto", "basso"]

# Class name mapping
CLASS_NAMES: dict[int, str] = {
    CharClass.CLASS_MAGIC_USER: "Pandion",
    CharClass.CLASS_CLERIC: "Cyrinic",
    CharClass.CLASS_THIEF: "Alcione",
    CharClass.CLASS_WARRIOR: "Genidian",
    CharClass.CLASS_PELOI: "Peloi",
    CharClass.CLASS_DARESIANO: "Daresiano",
}

# Sex name mapping
SEX_NAMES: dict[int, str] = {
    Sex.SEX_NEUTRAL: "Neutro",
    Sex.SEX_MALE: "Maschio",
    Sex.SEX_FEMALE: "Femmina",
}


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------

def do_look(ch: CharData, argument: str, desc: Descriptor, world: GameWorld) -> None:
    """Show room name, description, exits, people, and objects.

    Ported from do_look() / look_at_room() in act.informative.c.
    Simplified for Phase 1.
    """
    if ch.in_room == NOWHERE or ch.in_room not in world.rooms:
        _send(desc, "Sei nel vuoto.\r\n")
        return

    room = world.rooms[ch.in_room]

    # Room name
    _send(desc, f"\r\n&c{room.name}&0\r\n")

    # Room description
    if room.description:
        _send(desc, f"{room.description}\r\n")

    # Exits
    exits = _format_exits(room, world)
    if exits:
        _send(desc, f"&g[ Uscite: {exits} ]&0\r\n")
    else:
        _send(desc, "&g[ Uscite: Nessuna ]&0\r\n")

    # People in the room
    for other in room._characters:
        if other is not ch:
            name = other.player.name
            _send(desc, f"&y{name} e' qui.&0\r\n")

    # Objects on the ground (Phase 1: none yet)


def do_move(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
    direction: int = 0,
) -> None:
    """Move the character in a direction.

    Ported from do_move() / perform_move() in act.movement.c.
    Simplified for Phase 1 -- no ride/fly/door checks.
    """
    if ch.in_room == NOWHERE or ch.in_room not in world.rooms:
        _send(desc, "Non puoi andare da nessuna parte.\r\n")
        return

    room = world.rooms[ch.in_room]
    exit_data = room.data.dir_option[direction]

    if exit_data is None or exit_data.to_room == NOWHERE:
        _send(desc, "Non puoi andare in quella direzione.\r\n")
        return

    dest_vnum = exit_data.to_room
    if dest_vnum not in world.rooms:
        _send(desc, "Non puoi andare in quella direzione.\r\n")
        return

    # Check if door is closed
    if exit_data.exit_info & ExitInfo.EX_ISDOOR:
        if exit_data.exit_info & ExitInfo.EX_CLOSED:
            _send(desc, "La porta e' chiusa.\r\n")
            return

    dest_room = world.rooms[dest_vnum]

    # Notify current room
    dir_name = DIR_NAMES_IT[direction] if direction < len(DIR_NAMES_IT) else "?"
    for other in room._characters:
        if other is not ch and other.desc:
            _send_async(
                other.desc,
                f"\r\n{ch.player.name} se ne va verso {dir_name}.\r\n",
            )

    # Remove from current room
    if ch in room._characters:
        room._characters.remove(ch)

    # Move to destination
    ch.in_room = dest_vnum
    if ch not in dest_room._characters:
        dest_room._characters.append(ch)

    # Notify destination room
    for other in dest_room._characters:
        if other is not ch and other.desc:
            _send_async(
                other.desc,
                f"\r\n{ch.player.name} e' arrivato.\r\n",
            )

    # Show the new room
    do_look(ch, "", desc, world)


def do_say(ch: CharData, argument: str, desc: Descriptor, world: GameWorld) -> None:
    """Speak to the room.

    Ported from do_say() in act.comm.c.
    """
    if not argument.strip():
        _send(desc, "Si, ma COSA vuoi dire?\r\n")
        return

    message = argument.strip()
    _send(desc, f"Dici, '{message}'\r\n")

    if ch.in_room in world.rooms:
        room = world.rooms[ch.in_room]
        for other in room._characters:
            if other is not ch and other.desc:
                _send_async(
                    other.desc,
                    f"\r\n{ch.player.name} dice, '{message}'\r\n",
                )


def do_who(ch: CharData, argument: str, desc: Descriptor, world: GameWorld) -> None:
    """List online players.

    Ported from do_who() in act.informative.c.
    Simplified for Phase 1.
    """
    _send(desc, "\r\n&WGiocatori collegati a Dalila:&0\r\n")
    _send(desc, "-" * 40 + "\r\n")

    count = 0
    for player in world.players:
        level = player.player.level
        class_name = CLASS_NAMES.get(player.player.class_, "???")
        name = player.player.name
        _send(desc, f"[{level:2d} {class_name:10s}] {name}\r\n")
        count += 1

    _send(desc, "-" * 40 + "\r\n")
    _send(
        desc,
        f"\r\n{count} giocator{'e' if count == 1 else 'i'} "
        f"collegat{'o' if count == 1 else 'i'}.\r\n",
    )


def do_quit(ch: CharData, argument: str, desc: Descriptor, world: GameWorld) -> None:
    """Disconnect from the game.

    Ported from do_quit() in act.other.c.
    """
    _send(desc, "Arrivederci, avventuriero... Torna presto!\r\n")

    # Notify room
    if ch.in_room in world.rooms:
        room = world.rooms[ch.in_room]
        for other in room._characters:
            if other is not ch and other.desc:
                _send_async(
                    other.desc,
                    f"\r\n{ch.player.name} ha lasciato il gioco.\r\n",
                )

    desc.state = ConnState.CON_CLOSE


def do_score(ch: CharData, argument: str, desc: Descriptor, world: GameWorld) -> None:
    """Show basic character information.

    Ported from do_score() in act.informative.c.
    Simplified for Phase 1.
    """
    name = ch.player.name
    level = ch.player.level
    class_name = CLASS_NAMES.get(ch.player.class_, "???")
    sex_name = SEX_NAMES.get(ch.player.sex, "???")

    lines = [
        f"\r\n&W--- Informazioni su {name} ---&0\r\n",
        f"  Livello: {level}    Classe: {class_name}    Sesso: {sex_name}\r\n",
        f"  HP: {ch.points.hit}/{ch.points.max_hit}"
        f"  Mana: {ch.points.mana}/{ch.points.max_mana}"
        f"  Move: {ch.points.move}/{ch.points.max_move}\r\n",
        f"  Forza: {ch.aff_abils.str}  Int: {ch.aff_abils.intel}"
        f"  Sag: {ch.aff_abils.wis}  Des: {ch.aff_abils.dex}"
        f"  Cos: {ch.aff_abils.con}  Car: {ch.aff_abils.cha}\r\n",
        f"  Oro: {ch.points.gold}  Esperienza: {ch.points.exp}\r\n",
        f"  Armatura: {ch.points.armor // 10}  "
        f"Hitroll: {ch.points.hitroll}  Damroll: {ch.points.damroll}\r\n",
    ]
    for line in lines:
        _send(desc, line)


def do_exits(ch: CharData, argument: str, desc: Descriptor, world: GameWorld) -> None:
    """Show visible exits from the current room.

    Ported from do_exits() in act.informative.c.
    """
    if ch.in_room == NOWHERE or ch.in_room not in world.rooms:
        _send(desc, "Non sei da nessuna parte.\r\n")
        return

    room = world.rooms[ch.in_room]
    _send(desc, "Uscite visibili:\r\n")

    found = False
    for i in range(NUM_OF_DIRS):
        exit_data = room.data.dir_option[i]
        if exit_data is not None and exit_data.to_room != NOWHERE:
            if exit_data.to_room in world.rooms:
                dest = world.rooms[exit_data.to_room]
                dir_name = DIR_NAMES_IT[i] if i < len(DIR_NAMES_IT) else "?"
                _send(desc, f"  {dir_name:8s} - {dest.name}\r\n")
                found = True

    if not found:
        _send(desc, "  Nessuna.\r\n")


def do_not_implemented(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Placeholder for unimplemented commands."""
    _send(desc, "This command is not yet available in the Python port.\r\n")


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _send(desc: Descriptor, text: str) -> None:
    """Fire-and-forget send to a descriptor."""
    asyncio.ensure_future(desc.send(text))


def _send_async(desc: Descriptor, text: str) -> None:
    """Fire-and-forget send for notifications to other players."""
    asyncio.ensure_future(desc.send(text))


def _format_exits(room: LiveRoom, world: GameWorld) -> str:
    """Format visible exits as a string like 'N E S'."""
    short = {"north": "N", "east": "E", "south": "S",
             "west": "W", "up": "U", "down": "D"}
    exits = []
    for i in range(NUM_OF_DIRS):
        exit_data = room.data.dir_option[i]
        if exit_data is not None and exit_data.to_room != NOWHERE:
            if exit_data.to_room in world.rooms:
                dir_abbr = short.get(DIR_NAMES[i], "?")
                exits.append(dir_abbr)
    return " ".join(exits)


# ---------------------------------------------------------------------------
# Movement command factories
# ---------------------------------------------------------------------------

def _make_move_cmd(direction: int) -> CommandFunc:
    """Create a movement command function for a specific direction."""
    def _move(ch: CharData, argument: str, desc: Descriptor, world: GameWorld) -> None:
        do_move(ch, argument, desc, world, direction=direction)
    return _move


# ---------------------------------------------------------------------------
# Command table
# ---------------------------------------------------------------------------

# Build the command dispatch table matching cmd_info[] from interpreter.c.
# Phase 1: directions + starter commands. Everything else -> placeholder.

CMD_TABLE: list[CommandInfo] = [
    # Directions (must come first, like in C)
    CommandInfo("north", Position.POS_STANDING, _make_move_cmd(Direction.NORTH), 0),
    CommandInfo("east", Position.POS_STANDING, _make_move_cmd(Direction.EAST), 0),
    CommandInfo("south", Position.POS_STANDING, _make_move_cmd(Direction.SOUTH), 0),
    CommandInfo("west", Position.POS_STANDING, _make_move_cmd(Direction.WEST), 0),
    CommandInfo("up", Position.POS_STANDING, _make_move_cmd(Direction.UP), 0),
    CommandInfo("down", Position.POS_STANDING, _make_move_cmd(Direction.DOWN), 0),
    # Italian directions
    CommandInfo("nord", Position.POS_STANDING, _make_move_cmd(Direction.NORTH), 0),
    CommandInfo("est", Position.POS_STANDING, _make_move_cmd(Direction.EAST), 0),
    CommandInfo("sud", Position.POS_STANDING, _make_move_cmd(Direction.SOUTH), 0),
    CommandInfo("ovest", Position.POS_STANDING, _make_move_cmd(Direction.WEST), 0),
    CommandInfo("alto", Position.POS_STANDING, _make_move_cmd(Direction.UP), 0),
    CommandInfo("basso", Position.POS_STANDING, _make_move_cmd(Direction.DOWN), 0),
    # Italian short directions
    CommandInfo("su", Position.POS_STANDING, _make_move_cmd(Direction.UP), 0),
    CommandInfo("giu", Position.POS_STANDING, _make_move_cmd(Direction.DOWN), 0),
    # Special single-char commands
    CommandInfo("'", Position.POS_RESTING, do_say, 0),
    # Core commands
    CommandInfo("look", Position.POS_RESTING, do_look, 0),
    CommandInfo("guarda", Position.POS_RESTING, do_look, 0),
    CommandInfo("l", Position.POS_RESTING, do_look, 0),
    CommandInfo("say", Position.POS_RESTING, do_say, 0),
    CommandInfo("parla", Position.POS_RESTING, do_say, 0),
    CommandInfo("dici", Position.POS_RESTING, do_say, 0),
    CommandInfo("who", Position.POS_DEAD, do_who, 0),
    CommandInfo("chi", Position.POS_DEAD, do_who, 0),
    CommandInfo("quit", Position.POS_DEAD, do_quit, 0),
    CommandInfo("abbandonare", Position.POS_DEAD, do_quit, 0),
    CommandInfo("score", Position.POS_DEAD, do_score, 0),
    CommandInfo("punteggio", Position.POS_DEAD, do_score, 0),
    CommandInfo("exits", Position.POS_RESTING, do_exits, 0),
    CommandInfo("uscite", Position.POS_RESTING, do_exits, 0),
]

# Build a lookup dict for fast prefix matching
_CMD_LOOKUP: dict[str, CommandInfo] = {}
for _cmd in CMD_TABLE:
    _CMD_LOOKUP[_cmd.command] = _cmd


def command_interpreter(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Parse and dispatch a player command.

    Ported from command_interpreter() in interpreter.c.
    Uses prefix matching: 'n' matches 'north', 'lo' matches 'look'.
    """
    argument = argument.strip()
    if not argument:
        return

    # Split into command word and arguments
    # Handle special single-char non-alpha commands: ' ; : <
    if not argument[0].isalpha() and not argument[0].isdigit():
        cmd_word = argument[0]
        cmd_args = argument[1:].strip()
    else:
        parts = argument.split(None, 1)
        cmd_word = parts[0].lower()
        cmd_args = parts[1] if len(parts) > 1 else ""

    # Prefix match against command table
    cmd_len = len(cmd_word)
    matched: CommandInfo | None = None

    for cmd in CMD_TABLE:
        if cmd.command[:cmd_len] == cmd_word:
            if ch.player.level >= cmd.minimum_level:
                matched = cmd
                break

    if matched is None:
        _send(desc, "Huh?!?\r\n")
        return

    # Execute the command
    try:
        matched.command_func(ch, cmd_args, desc, world)
    except Exception:
        log.exception("Error executing command '%s'", argument)
        _send(desc, "Errore interno nel comando.\r\n")
