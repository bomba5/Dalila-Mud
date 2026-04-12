"""Command interpreter -- dispatch table and all registered commands.

Ported from command_interpreter(), cmd_info[] in interpreter.c.
Phase 1 implemented: look, movement, say, who, quit, score.
Phase 2 adds: enhanced movement/doors, items, communication, socials.
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
# Import Phase 2 command modules
# ---------------------------------------------------------------------------

from dalila.commands.communication import (
    do_emote,
    do_gossip,
    do_gsay,
    do_say,
    do_shout,
    do_tell,
    do_whisper,
)
from dalila.commands.informative import (
    do_exits,
    do_look,
    look_at_room,
)
from dalila.commands.item import (
    do_drink,
    do_drop,
    do_eat,
    do_equipment,
    do_get,
    do_give,
    do_inventory,
    do_put,
    do_remove,
    do_wear,
    do_wield,
)
from dalila.commands.movement import (
    SCMD_CLOSE,
    SCMD_LOCK,
    SCMD_OPEN,
    SCMD_UNLOCK,
    do_follow,
    do_gen_door,
    do_group,
    do_move,
    do_rest,
    do_sit,
    do_sleep,
    do_stand,
    do_wake,
)
from dalila.commands.social import do_social, find_social

# Import Phase 3 command modules (Combat & Magic)
from dalila.commands.offensive import (
    do_assist,
    do_backstab,
    do_bash,
    do_disarm,
    do_flee,
    do_hit,
    do_kick,
    do_kill,
    do_rescue,
)
from dalila.commands.magic import do_cast


# ---------------------------------------------------------------------------
# Command implementations that remain in interpreter.py
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Movement command factories
# ---------------------------------------------------------------------------

def _make_move_cmd(direction: int) -> CommandFunc:
    """Create a movement command function for a specific direction."""
    def _move(ch: CharData, argument: str, desc: Descriptor, world: GameWorld) -> None:
        do_move(ch, argument, desc, world, direction=direction)
    return _move


# ---------------------------------------------------------------------------
# Door command factories
# ---------------------------------------------------------------------------

def _make_door_cmd(scmd: int) -> CommandFunc:
    """Create a door command function for a specific sub-command."""
    def _door(ch: CharData, argument: str, desc: Descriptor, world: GameWorld) -> None:
        do_gen_door(ch, argument, desc, world, scmd=scmd)
    return _door


# ---------------------------------------------------------------------------
# Command table
# ---------------------------------------------------------------------------

# Build the command dispatch table matching cmd_info[] from interpreter.c.
# Phase 2: directions + core commands + items + communication + positions

CMD_TABLE: list[CommandInfo] = [
    # ---- Directions (must come first, like in C) ----
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

    # ---- Special single-char commands ----
    CommandInfo("'", Position.POS_RESTING, do_say, 0),
    CommandInfo(":", Position.POS_RESTING, do_emote, 0),

    # ---- Core commands ----
    CommandInfo("look", Position.POS_RESTING, do_look, 0),
    CommandInfo("guarda", Position.POS_RESTING, do_look, 0),
    CommandInfo("l", Position.POS_RESTING, do_look, 0),
    CommandInfo("say", Position.POS_RESTING, do_say, 0),
    CommandInfo("dici", Position.POS_RESTING, do_say, 0),
    CommandInfo("who", Position.POS_DEAD, do_who, 0),
    CommandInfo("chi", Position.POS_DEAD, do_who, 0),
    CommandInfo("quit", Position.POS_DEAD, do_quit, 0),
    CommandInfo("abbandonare", Position.POS_DEAD, do_quit, 0),
    CommandInfo("score", Position.POS_DEAD, do_score, 0),
    CommandInfo("punteggio", Position.POS_DEAD, do_score, 0),
    CommandInfo("exits", Position.POS_RESTING, do_exits, 0),
    CommandInfo("uscite", Position.POS_RESTING, do_exits, 0),

    # ---- Communication (Phase 2) ----
    CommandInfo("tell", Position.POS_DEAD, do_tell, 0),
    CommandInfo("parla", Position.POS_DEAD, do_tell, 0),
    CommandInfo("whisper", Position.POS_RESTING, do_whisper, 0),
    CommandInfo("sussurra", Position.POS_RESTING, do_whisper, 0),
    CommandInfo("shout", Position.POS_RESTING, do_shout, 0),
    CommandInfo("urla", Position.POS_RESTING, do_shout, 0),
    CommandInfo("gossip", Position.POS_RESTING, do_gossip, 0),
    CommandInfo("emote", Position.POS_RESTING, do_emote, 0),
    CommandInfo("gsay", Position.POS_RESTING, do_gsay, 0),

    # ---- Item manipulation (Phase 2) ----
    CommandInfo("get", Position.POS_RESTING, do_get, 0),
    CommandInfo("prendi", Position.POS_RESTING, do_get, 0),
    CommandInfo("drop", Position.POS_RESTING, do_drop, 0),
    CommandInfo("lascia", Position.POS_RESTING, do_drop, 0),
    CommandInfo("put", Position.POS_RESTING, do_put, 0),
    CommandInfo("metti", Position.POS_RESTING, do_put, 0),
    CommandInfo("give", Position.POS_RESTING, do_give, 0),
    CommandInfo("dai", Position.POS_RESTING, do_give, 0),
    CommandInfo("wear", Position.POS_RESTING, do_wear, 0),
    CommandInfo("indossa", Position.POS_RESTING, do_wear, 0),
    CommandInfo("wield", Position.POS_RESTING, do_wield, 0),
    CommandInfo("impugna", Position.POS_RESTING, do_wield, 0),
    CommandInfo("remove", Position.POS_RESTING, do_remove, 0),
    CommandInfo("rimuovi", Position.POS_RESTING, do_remove, 0),
    CommandInfo("drink", Position.POS_RESTING, do_drink, 0),
    CommandInfo("bevi", Position.POS_RESTING, do_drink, 0),
    CommandInfo("eat", Position.POS_RESTING, do_eat, 0),
    CommandInfo("mangia", Position.POS_RESTING, do_eat, 0),
    CommandInfo("inventory", Position.POS_DEAD, do_inventory, 0),
    CommandInfo("inventario", Position.POS_DEAD, do_inventory, 0),
    CommandInfo("i", Position.POS_DEAD, do_inventory, 0),
    CommandInfo("equipment", Position.POS_DEAD, do_equipment, 0),
    CommandInfo("equipaggiamento", Position.POS_DEAD, do_equipment, 0),
    CommandInfo("eq", Position.POS_DEAD, do_equipment, 0),

    # ---- Door commands (Phase 2) ----
    CommandInfo("open", Position.POS_STANDING, _make_door_cmd(SCMD_OPEN), 0),
    CommandInfo("apri", Position.POS_STANDING, _make_door_cmd(SCMD_OPEN), 0),
    CommandInfo("close", Position.POS_STANDING, _make_door_cmd(SCMD_CLOSE), 0),
    CommandInfo("chiudi", Position.POS_STANDING, _make_door_cmd(SCMD_CLOSE), 0),
    CommandInfo("lock", Position.POS_STANDING, _make_door_cmd(SCMD_LOCK), 0),
    CommandInfo("blocca", Position.POS_STANDING, _make_door_cmd(SCMD_LOCK), 0),
    CommandInfo("unlock", Position.POS_STANDING, _make_door_cmd(SCMD_UNLOCK), 0),
    CommandInfo("sblocca", Position.POS_STANDING, _make_door_cmd(SCMD_UNLOCK), 0),

    # ---- Position commands (Phase 2) ----
    CommandInfo("stand", Position.POS_SLEEPING, do_stand, 0),
    CommandInfo("alzati", Position.POS_SLEEPING, do_stand, 0),
    CommandInfo("sit", Position.POS_RESTING, do_sit, 0),
    CommandInfo("siediti", Position.POS_RESTING, do_sit, 0),
    CommandInfo("rest", Position.POS_RESTING, do_rest, 0),
    CommandInfo("riposa", Position.POS_RESTING, do_rest, 0),
    CommandInfo("sleep", Position.POS_SLEEPING, do_sleep, 0),
    CommandInfo("dormi", Position.POS_SLEEPING, do_sleep, 0),
    CommandInfo("wake", Position.POS_SLEEPING, do_wake, 0),
    CommandInfo("svegliati", Position.POS_SLEEPING, do_wake, 0),

    # ---- Follow/Group (Phase 2) ----
    CommandInfo("follow", Position.POS_RESTING, do_follow, 0),
    CommandInfo("segui", Position.POS_RESTING, do_follow, 0),
    CommandInfo("group", Position.POS_RESTING, do_group, 0),
    CommandInfo("gruppo", Position.POS_RESTING, do_group, 0),

    # ---- Combat commands (Phase 3) ----
    CommandInfo("kill", Position.POS_FIGHTING, do_kill, 0),
    CommandInfo("uccidi", Position.POS_FIGHTING, do_kill, 0),
    CommandInfo("hit", Position.POS_FIGHTING, do_hit, 0),
    CommandInfo("colpisci", Position.POS_FIGHTING, do_hit, 0),
    CommandInfo("flee", Position.POS_FIGHTING, do_flee, 0),
    CommandInfo("fuggi", Position.POS_FIGHTING, do_flee, 0),
    CommandInfo("kick", Position.POS_FIGHTING, do_kick, 0),
    CommandInfo("calcia", Position.POS_FIGHTING, do_kick, 0),
    CommandInfo("bash", Position.POS_FIGHTING, do_bash, 0),
    CommandInfo("spingi", Position.POS_FIGHTING, do_bash, 0),
    CommandInfo("backstab", Position.POS_STANDING, do_backstab, 0),
    CommandInfo("pugnala", Position.POS_STANDING, do_backstab, 0),
    CommandInfo("rescue", Position.POS_FIGHTING, do_rescue, 0),
    CommandInfo("salva", Position.POS_FIGHTING, do_rescue, 0),
    CommandInfo("assist", Position.POS_FIGHTING, do_assist, 0),
    CommandInfo("assisti", Position.POS_FIGHTING, do_assist, 0),
    CommandInfo("disarm", Position.POS_FIGHTING, do_disarm, 0),

    # ---- Magic commands (Phase 3) ----
    CommandInfo("cast", Position.POS_SITTING, do_cast, 0),
    CommandInfo("lancia", Position.POS_SITTING, do_cast, 0),
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
    Also checks social commands if no built-in command matches.
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

    if matched is not None:
        # Execute the built-in command
        try:
            matched.command_func(ch, cmd_args, desc, world)
        except Exception:
            log.exception("Error executing command '%s'", argument)
            _send(desc, "Errore interno nel comando.\r\n")
        return

    # Check social commands
    social = find_social(cmd_word)
    if social is not None:
        try:
            do_social(ch, cmd_args, desc, world, social)
        except Exception:
            log.exception("Error executing social '%s'", cmd_word)
            _send(desc, "Errore interno nel comando.\r\n")
        return

    _send(desc, "Huh?!?\r\n")
