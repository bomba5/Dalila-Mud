"""Informative commands: look, exits, room display.

Ported from act.informative.c: look_at_room, do_look, do_exits,
list_char_to_char, list_obj_to_char, show_obj_to_char.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from dalila.constants import (
    NOWHERE,
    NUM_OF_DIRS,
    AffectedBy,
    Direction,
    ExitInfo,
    ItemType,
    Position,
    RoomFlag,
    WearPosition,
)
from dalila.engine.handler import (
    get_char_room_vis,
    get_obj_in_list_vis,
    isname,
)
from dalila.models.object import ObjData

if TYPE_CHECKING:
    from dalila.engine.game_loop import GameWorld, LiveRoom
    from dalila.models.character import CharData
    from dalila.net.descriptor import Descriptor

log = logging.getLogger(__name__)

# Direction names for display
DIR_NAMES: list[str] = ["north", "east", "south", "west", "up", "down"]
DIR_NAMES_IT: list[str] = ["nord", "est", "sud", "ovest", "alto", "basso"]
DIR_SHORT: dict[str, str] = {
    "north": "N", "east": "E", "south": "S",
    "west": "W", "up": "U", "down": "D",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _send(desc: Descriptor, text: str) -> None:
    """Fire-and-forget send to a descriptor."""
    asyncio.ensure_future(desc.send(text))


def _get_position(ch: CharData) -> int:
    """Get character position."""
    return getattr(ch, "position", Position.POS_STANDING)


def _is_affected(ch: CharData, flag: int) -> bool:
    """Check if character has an affect flag (bank 0)."""
    if hasattr(ch, "char_specials_saved"):
        return bool(ch.char_specials_saved.affected_by[0] & flag)
    return False


# ---------------------------------------------------------------------------
# Room display
# ---------------------------------------------------------------------------

def _format_exits(room: LiveRoom, world: GameWorld) -> str:
    """Format visible exits as a string like 'N E S'.

    Ported from do_auto_exits() in act.informative.c.
    """
    exits = []
    for i in range(NUM_OF_DIRS):
        exit_data = room.data.dir_option[i]
        if exit_data is not None and exit_data.to_room != NOWHERE:
            if exit_data.to_room in world.rooms:
                # Hidden exits are not shown
                if exit_data.exit_info & ExitInfo.EX_HIDDEN:
                    continue
                dir_abbr = DIR_SHORT.get(DIR_NAMES[i], "?")
                # Mark closed doors
                if exit_data.exit_info & ExitInfo.EX_CLOSED:
                    dir_abbr = f"({dir_abbr})"
                exits.append(dir_abbr)
    return " ".join(exits)


def list_obj_to_char(
    obj_list: list[ObjData], desc: Descriptor, mode: int = 0,
) -> None:
    """List objects visible to a character.

    Ported from list_obj_to_char() in act.informative.c.
    Groups identical items with counts.
    """
    if not obj_list:
        return

    # Group objects by description for cleaner display
    seen: dict[str, int] = {}
    order: list[str] = []

    for obj in obj_list:
        desc_text = obj.description if obj.description else obj.short_description
        if not desc_text:
            desc_text = "Qualcosa e' qui."
        if desc_text in seen:
            seen[desc_text] += 1
        else:
            seen[desc_text] = 1
            order.append(desc_text)

    for desc_text in order:
        count = seen[desc_text]
        if count > 1:
            _send(desc, f"&g[{count}] {desc_text}&0\r\n")
        else:
            _send(desc, f"&g{desc_text}&0\r\n")


def list_char_to_char(
    char_list: list[CharData], ch: CharData, desc: Descriptor,
) -> None:
    """List characters visible in the room.

    Ported from list_char_to_char() in act.informative.c.
    """
    for other in char_list:
        if other is ch:
            continue
        # Build the display line
        pos = _get_position(other)
        name = other.player.name

        # Use long_descr for NPCs in default position (if available)
        if other.nr >= 0 and other.player.long_descr:
            long_desc = other.player.long_descr.rstrip()
            _send(desc, f"&y{long_desc}&0\r\n")
            continue

        pos_text = _position_text(other)
        _send(desc, f"&y{name} {pos_text}&0\r\n")


def _position_text(ch: CharData) -> str:
    """Get Italian text for character position."""
    pos = _get_position(ch)
    match pos:
        case Position.POS_DEAD:
            return "e' qui, morto!"
        case Position.POS_MORTALLYW:
            return "e' qui, ferito mortalmente!"
        case Position.POS_INCAP:
            return "e' qui, incapacitato."
        case Position.POS_STUNNED:
            return "e' qui, stordito."
        case Position.POS_SLEEPING:
            return "dorme qui."
        case Position.POS_RESTING:
            return "riposa qui."
        case Position.POS_SITTING:
            return "e' seduto qui."
        case Position.POS_FIGHTING:
            return "sta combattendo!"
        case Position.POS_STANDING:
            return "e' qui."
        case _:
            return "e' qui."


def look_at_room(
    ch: CharData, desc: Descriptor, world: GameWorld,
    ignore_brief: bool = False,
) -> None:
    """Display the current room to a character.

    Ported from look_at_room() in act.informative.c.
    """
    if ch.in_room == NOWHERE or ch.in_room not in world.rooms:
        _send(desc, "Sei nel vuoto.\r\n")
        return

    room = world.rooms[ch.in_room]

    # Room name
    _send(desc, f"\r\n&c{room.name}&0\r\n")

    # Room description (skip if brief mode, unless ignore_brief)
    if room.description:
        _send(desc, f"{room.description}\r\n")

    # Exits
    exits = _format_exits(room, world)
    if exits:
        _send(desc, f"&g[ Uscite: {exits} ]&0\r\n")
    else:
        _send(desc, "&g[ Uscite: Nessuna ]&0\r\n")

    # Objects on the ground
    list_obj_to_char(room._objects, desc)

    # People in the room
    list_char_to_char(room._characters, ch, desc)


# ---------------------------------------------------------------------------
# do_look -- the main look command
# ---------------------------------------------------------------------------

def do_look(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """The look command: look at room, person, object, direction, extra desc.

    Ported from ACMD(do_look) in act.informative.c.
    """
    if _get_position(ch) < Position.POS_SLEEPING:
        _send(desc, "Non vedi niente tranne stelle!\r\n")
        return

    if _get_position(ch) == Position.POS_SLEEPING:
        _send(desc, "Non riesci a vedere niente, stai dormendo!\r\n")
        return

    arg = argument.strip()

    if not arg or arg.lower() in ("room", "stanza"):
        # Look at the room
        look_at_room(ch, desc, world)
        return

    # Check if looking in a direction
    direction = _parse_look_direction(arg)
    if direction >= 0:
        _look_in_direction(ch, direction, desc, world)
        return

    # Check 'in' keyword for containers
    parts = arg.split(None, 1)
    if parts[0].lower() in ("in", "dentro"):
        if len(parts) < 2:
            _send(desc, "Guardare dentro cosa?\r\n")
            return
        _look_in_obj(ch, parts[1], desc, world)
        return

    # Check 'at' keyword
    if parts[0].lower() in ("at", "a"):
        if len(parts) < 2:
            _send(desc, "Guardare cosa?\r\n")
            return
        arg = parts[1]

    # Try to look at a character in the room
    vict = get_char_room_vis(ch, arg, world)
    if vict is not None:
        _look_at_char(vict, ch, desc)
        return

    # Try to find an object in inventory
    carrying = getattr(ch, "carrying", [])
    obj = get_obj_in_list_vis(ch, arg, carrying)
    if obj is not None:
        _show_obj_description(obj, desc)
        return

    # Try to find an object in the room
    if ch.in_room in world.rooms:
        room = world.rooms[ch.in_room]
        obj = get_obj_in_list_vis(ch, arg, room._objects)
        if obj is not None:
            _show_obj_description(obj, desc)
            return

    # Try to find an extra description in the room
    if ch.in_room in world.rooms:
        room = world.rooms[ch.in_room]
        for ex in room.data.ex_description:
            if isname(arg, ex.keyword):
                if ex.description:
                    _send(desc, f"{ex.description}\r\n")
                else:
                    _send(desc, "Non vedi niente di speciale.\r\n")
                return

    # Try to find an extra description on objects in inventory/room
    for obj in carrying:
        for ex in obj.ex_description:
            if isname(arg, ex.keyword):
                if ex.description:
                    _send(desc, f"{ex.description}\r\n")
                else:
                    _send(desc, "Non vedi niente di speciale.\r\n")
                return

    _send(desc, "Non vedi niente di speciale.\r\n")


def _parse_look_direction(arg: str) -> int:
    """Parse if a look argument is a direction name."""
    arg_lower = arg.lower()
    dir_map = {
        "north": 0, "nord": 0, "n": 0,
        "east": 1, "est": 1, "e": 1,
        "south": 2, "sud": 2, "s": 2,
        "west": 3, "ovest": 3, "w": 3, "o": 3,
        "up": 4, "alto": 4, "su": 4, "u": 4,
        "down": 5, "basso": 5, "giu": 5, "d": 5,
    }
    return dir_map.get(arg_lower, -1)


def _look_in_direction(
    ch: CharData, direction: int, desc: Descriptor, world: GameWorld,
) -> None:
    """Look in a direction (see exit description, door state).

    Ported from look_in_direction() in act.informative.c.
    """
    if ch.in_room == NOWHERE or ch.in_room not in world.rooms:
        return

    room = world.rooms[ch.in_room]
    exit_data = room.data.dir_option[direction]

    if exit_data is None:
        _send(desc, "Non vedi niente di speciale.\r\n")
        return

    if exit_data.general_description:
        _send(desc, f"{exit_data.general_description}\r\n")
    else:
        _send(desc, "Non vedi niente di speciale.\r\n")

    if exit_data.exit_info & ExitInfo.EX_ISDOOR:
        door_name = exit_data.keyword if exit_data.keyword else "porta"
        if exit_data.exit_info & ExitInfo.EX_CLOSED:
            _send(desc, f"La {door_name} e' chiusa.\r\n")
        else:
            _send(desc, f"La {door_name} e' aperta.\r\n")


def _look_in_obj(
    ch: CharData, arg: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Look inside a container object.

    Ported from look_in_obj() in act.informative.c.
    """
    from dalila.constants import ContainerFlag

    # Find the container
    carrying = getattr(ch, "carrying", [])
    obj = get_obj_in_list_vis(ch, arg, carrying)
    if obj is None and ch.in_room in world.rooms:
        room = world.rooms[ch.in_room]
        obj = get_obj_in_list_vis(ch, arg, room._objects)
    if obj is None:
        _send(desc, f"Non c'e' {arg} qui.\r\n")
        return

    obj_type = obj.obj_flags.type_flag

    if obj_type == ItemType.ITEM_DRINKCON or obj_type == ItemType.ITEM_FOUNTAIN:
        # Drink container
        if obj.obj_flags.value[1] <= 0:
            _send(desc, "E' vuoto.\r\n")
        else:
            _send(desc, f"Contiene del liquido.\r\n")
        return

    if obj_type != ItemType.ITEM_CONTAINER:
        _send(desc, "Non e' un contenitore.\r\n")
        return

    # Check if closed
    if obj.obj_flags.value[1] & ContainerFlag.CONT_CLOSED:
        _send(desc, "E' chiuso.\r\n")
        return

    contents = getattr(obj, "contains", [])
    obj_name = obj.short_description if obj.short_description else "qualcosa"
    _send(desc, f"{obj_name} contiene:\r\n")
    if not contents:
        _send(desc, "  Niente.\r\n")
    else:
        list_obj_to_char(contents, desc)


def _look_at_char(
    target: CharData, ch: CharData, desc: Descriptor,
) -> None:
    """Look at a character (show description and equipment).

    Ported from look_at_char() in act.informative.c.
    """
    if target.player.description:
        _send(desc, f"{target.player.description}\r\n")
    else:
        _send(desc, "Non vedi niente di speciale.\r\n")

    # Show equipment
    _send(desc, f"\r\n{target.player.name} sta usando:\r\n")
    found = False
    for pos in range(len(target.equipment)):
        obj = target.equipment[pos]
        if obj is not None and isinstance(obj, ObjData):
            wear_name = _wear_position_name(pos)
            obj_name = obj.short_description if obj.short_description else "qualcosa"
            _send(desc, f"  {wear_name:20s} {obj_name}\r\n")
            found = True
    if not found:
        _send(desc, "  <Niente>\r\n")


def _show_obj_description(obj: ObjData, desc: Descriptor) -> None:
    """Show an object's description or action description."""
    if obj.action_description:
        _send(desc, f"{obj.action_description}\r\n")
    elif obj.description:
        _send(desc, f"{obj.description}\r\n")
    elif obj.short_description:
        _send(desc, f"Vedi {obj.short_description}.\r\n")
    else:
        _send(desc, "Non vedi niente di speciale.\r\n")

    # Show extra descriptions
    for ex in obj.ex_description:
        if ex.description:
            _send(desc, f"{ex.description}\r\n")
            return


def _wear_position_name(pos: int) -> str:
    """Italian name for equipment position."""
    names = {
        WearPosition.WEAR_LIGHT: "<usato come luce>",
        WearPosition.WEAR_FINGER_R: "<dito destro>",
        WearPosition.WEAR_FINGER_L: "<dito sinistro>",
        WearPosition.WEAR_NECK_1: "<collo>",
        WearPosition.WEAR_NECK_2: "<collo>",
        WearPosition.WEAR_BODY: "<corpo>",
        WearPosition.WEAR_HEAD: "<testa>",
        WearPosition.WEAR_LEGS: "<gambe>",
        WearPosition.WEAR_FEET: "<piedi>",
        WearPosition.WEAR_HANDS: "<mani>",
        WearPosition.WEAR_ARMS: "<braccia>",
        WearPosition.WEAR_SHIELD: "<scudo>",
        WearPosition.WEAR_ABOUT: "<spalle>",
        WearPosition.WEAR_WAIST: "<vita>",
        WearPosition.WEAR_WRIST_R: "<polso destro>",
        WearPosition.WEAR_WRIST_L: "<polso sinistro>",
        WearPosition.WEAR_WIELD: "<impugnato>",
        WearPosition.WEAR_HOLD: "<tenuto>",
        WearPosition.WEAR_LOBSX: "<lobo sinistro>",
        WearPosition.WEAR_LOBDX: "<lobo destro>",
        WearPosition.WEAR_SPALLE: "<spalle>",
        WearPosition.WEAR_IMMOBIL: "<immobilizzato>",
        WearPosition.WEAR_EYE: "<occhi>",
        WearPosition.WEAR_BOCCA: "<bocca>",
        WearPosition.WEAR_ALTRO1: "<altro>",
        WearPosition.WEAR_WIELD_L: "<impugnato sinistro>",
        WearPosition.WEAR_HANG: "<appeso>",
        WearPosition.WEAR_VESTE: "<veste>",
        WearPosition.WEAR_RELIQUIA: "<reliquia>",
    }
    return names.get(pos, "<?>")


# ---------------------------------------------------------------------------
# do_exits
# ---------------------------------------------------------------------------

def do_exits(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Show visible exits from the current room.

    Ported from ACMD(do_exits) in act.informative.c.
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
            if exit_data.exit_info & ExitInfo.EX_HIDDEN:
                continue
            if exit_data.to_room in world.rooms:
                dest = world.rooms[exit_data.to_room]
                dir_name = DIR_NAMES_IT[i] if i < len(DIR_NAMES_IT) else "?"
                door_mark = ""
                if exit_data.exit_info & ExitInfo.EX_CLOSED:
                    door_mark = " (chiusa)"
                _send(desc, f"  {dir_name:8s} - {dest.name}{door_mark}\r\n")
                found = True

    if not found:
        _send(desc, "  Nessuna.\r\n")
