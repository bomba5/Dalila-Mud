"""Object and character management functions.

Ported from handler.c: char_from_room, char_to_room, obj_to_char,
obj_from_char, obj_to_room, obj_from_room, equip_char, unequip_char,
affect_to_char, affect_remove, isname, get_number, find functions.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from dalila.constants import (
    NOBODY,
    NOTHING,
    NOWHERE,
    NUM_OF_DIRS,
    NUM_WEARS,
    AffectedBy,
    ApplyType,
    ItemType,
    MobFlag,
    Position,
    WearPosition,
)
from dalila.models.common import AffectedType
from dalila.models.object import ObjData

if TYPE_CHECKING:
    from dalila.engine.game_loop import GameWorld, LiveRoom
    from dalila.models.character import CharData

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Name matching (CircleMUD style abbreviation)
# ---------------------------------------------------------------------------

def isname(needle: str, namelist: str) -> bool:
    """Check if needle is an abbreviation of any word in namelist.

    Ported from isname() in handler.c.
    'sw' matches 'sword', 'shield' would need 'sh'.
    """
    if not needle or not namelist:
        return False
    needle_lower = needle.lower()
    for token in namelist.split():
        if token.lower().startswith(needle_lower):
            return True
    return False


def get_number(name: str) -> tuple[int, str]:
    """Parse '2.sword' into (2, 'sword'), plain 'sword' into (1, 'sword').

    Ported from get_number() in handler.c.
    Returns (count, stripped_name). count=0 means error.
    """
    if "." in name:
        parts = name.split(".", 1)
        num_str = parts[0]
        rest = parts[1]
        if not num_str.isdigit():
            return (0, name)
        return (int(num_str), rest)
    return (1, name)


def find_all_dots(arg: str) -> int:
    """Determine if arg is 'all', 'all.keyword', or just a name.

    Returns:
        0 = normal name
        1 = 'all'
        2 = 'all.keyword'
    """
    if arg.lower() == "all":
        return 1
    if arg.lower().startswith("all."):
        return 2
    return 0


# ---------------------------------------------------------------------------
# Character room management
# ---------------------------------------------------------------------------

def char_from_room(ch: CharData, world: GameWorld) -> None:
    """Remove a character from their current room.

    Ported from char_from_room() in handler.c.
    """
    if ch.in_room == NOWHERE or ch.in_room not in world.rooms:
        log.warning("char_from_room: ch not in a valid room")
        return

    room = world.rooms[ch.in_room]

    # Handle light sources
    if ch.equipment[WearPosition.WEAR_LIGHT] is not None:
        obj = ch.equipment[WearPosition.WEAR_LIGHT]
        if (isinstance(obj, ObjData)
                and obj.obj_flags.type_flag == ItemType.ITEM_LIGHT
                and obj.obj_flags.value[2]):
            room.data.light -= 1

    if ch in room._characters:
        room._characters.remove(ch)

    ch.in_room = NOWHERE


def char_to_room(ch: CharData, room_vnum: int, world: GameWorld) -> None:
    """Place a character in a room.

    Ported from char_to_room() in handler.c.
    """
    if room_vnum not in world.rooms:
        log.warning("char_to_room: invalid room %d", room_vnum)
        return

    room = world.rooms[room_vnum]
    if ch not in room._characters:
        room._characters.append(ch)
    ch.in_room = room_vnum

    # Handle light sources
    if ch.equipment[WearPosition.WEAR_LIGHT] is not None:
        obj = ch.equipment[WearPosition.WEAR_LIGHT]
        if (isinstance(obj, ObjData)
                and obj.obj_flags.type_flag == ItemType.ITEM_LIGHT
                and obj.obj_flags.value[2]):
            room.data.light += 1


# ---------------------------------------------------------------------------
# Object <-> Character management
# ---------------------------------------------------------------------------

def obj_to_char(obj: ObjData, ch: CharData) -> None:
    """Give an object to a character (inventory).

    Ported from obj_to_char() in handler.c.
    """
    if not hasattr(ch, "carrying"):
        ch.carrying: list[ObjData] = []  # type: ignore[annotation-unchecked]
    ch.carrying.insert(0, obj)
    obj.in_room = NOWHERE
    obj.carried_by = ch  # type: ignore[attr-defined]


def obj_from_char(obj: ObjData, ch: CharData) -> None:
    """Remove an object from a character's inventory.

    Ported from obj_from_char() in handler.c.
    """
    if hasattr(ch, "carrying") and obj in ch.carrying:
        ch.carrying.remove(obj)
    obj.carried_by = None  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Object <-> Room management
# ---------------------------------------------------------------------------

def obj_to_room(obj: ObjData, room_vnum: int, world: GameWorld) -> None:
    """Place an object in a room.

    Ported from obj_to_room() in handler.c.
    """
    if room_vnum not in world.rooms:
        log.warning("obj_to_room: invalid room %d", room_vnum)
        return

    room = world.rooms[room_vnum]
    if obj not in room._objects:
        room._objects.insert(0, obj)
    obj.in_room = room_vnum
    obj.carried_by = None  # type: ignore[attr-defined]


def obj_from_room(obj: ObjData, world: GameWorld) -> None:
    """Remove an object from a room.

    Ported from obj_from_room() in handler.c.
    """
    if obj.in_room == NOWHERE or obj.in_room not in world.rooms:
        log.warning("obj_from_room: obj not in valid room")
        return

    room = world.rooms[obj.in_room]
    if obj in room._objects:
        room._objects.remove(obj)
    obj.in_room = NOWHERE


# ---------------------------------------------------------------------------
# Object <-> Object (container) management
# ---------------------------------------------------------------------------

def obj_to_obj(obj: ObjData, container: ObjData) -> None:
    """Place an object inside a container.

    Ported from obj_to_obj() in handler.c.
    """
    if not hasattr(container, "contains"):
        container.contains: list[ObjData] = []  # type: ignore[annotation-unchecked]
    container.contains.insert(0, obj)
    obj.in_room = NOWHERE
    obj.carried_by = None  # type: ignore[attr-defined]
    obj.in_obj = container  # type: ignore[attr-defined]


def obj_from_obj(obj: ObjData) -> None:
    """Remove an object from its container.

    Ported from obj_from_obj() in handler.c.
    """
    container = getattr(obj, "in_obj", None)
    if container is not None and hasattr(container, "contains"):
        if obj in container.contains:
            container.contains.remove(obj)
    obj.in_obj = None  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Equipment management
# ---------------------------------------------------------------------------

def equip_char(ch: CharData, obj: ObjData, pos: int) -> None:
    """Equip an object on a character at the given position.

    Ported from equip_char() in handler.c.
    Simplified for Phase 2: no affect_modify() application yet.
    """
    if pos < 0 or pos >= NUM_WEARS:
        log.warning("equip_char: invalid position %d", pos)
        return

    if ch.equipment[pos] is not None:
        log.warning(
            "equip_char: %s already equipped at pos %d",
            ch.player.name, pos,
        )
        return

    ch.equipment[pos] = obj
    obj.worn_by = ch  # type: ignore[attr-defined]
    obj.worn_on = pos  # type: ignore[attr-defined]
    obj.in_room = NOWHERE


def unequip_char(ch: CharData, pos: int) -> ObjData | None:
    """Remove equipment from a character at the given position.

    Ported from unequip_char() in handler.c.
    Returns the removed object or None.
    """
    if pos < 0 or pos >= NUM_WEARS:
        return None

    obj = ch.equipment[pos]
    if obj is None:
        return None

    ch.equipment[pos] = None
    obj.worn_by = None  # type: ignore[attr-defined]
    obj.worn_on = -1  # type: ignore[attr-defined]
    return obj


# ---------------------------------------------------------------------------
# Affect management
# ---------------------------------------------------------------------------

def affect_to_char(ch: CharData, af: AffectedType) -> None:
    """Apply an affect to a character.

    Ported from affect_to_char() in handler.c.
    Simplified for Phase 2.
    """
    ch.affected.append(af)


def affect_remove(ch: CharData, af: AffectedType) -> None:
    """Remove an affect from a character.

    Ported from affect_remove() in handler.c.
    Simplified for Phase 2.
    """
    if af in ch.affected:
        ch.affected.remove(af)


def affect_from_char(ch: CharData, natura: int, spell_type: int) -> None:
    """Remove all affects of a given natura+type from a character.

    Ported from affect_from_char() in handler.c.
    """
    to_remove = [
        af for af in ch.affected
        if af.natura == natura and af.type == spell_type
    ]
    for af in to_remove:
        affect_remove(ch, af)


# ---------------------------------------------------------------------------
# Find functions
# ---------------------------------------------------------------------------

def get_char_room(
    name: str, room: LiveRoom,
) -> CharData | None:
    """Find a character in a room by name (with number prefix).

    Ported from get_char_room() in handler.c.
    """
    number, target = get_number(name)
    if number == 0:
        return None

    j = 0
    for ch in room._characters:
        if isname(target, ch.player.name):
            j += 1
            if j == number:
                return ch
    return None


def get_char_room_vis(
    ch: CharData, name: str, world: GameWorld,
) -> CharData | None:
    """Find a visible character in ch's room by name.

    Ported from get_char_room_vis() in handler.c.
    Phase 2: no visibility checks yet (CAN_SEE).
    """
    if ch.in_room == NOWHERE or ch.in_room not in world.rooms:
        return None

    # Special 'self' / 'me' handling
    if name.lower() in ("self", "me"):
        return ch

    room = world.rooms[ch.in_room]
    return get_char_room(name, room)


def get_char_vis(
    ch: CharData, name: str, world: GameWorld,
) -> CharData | None:
    """Find a visible character anywhere by name.

    Ported from get_char_vis() in handler.c.
    First checks the current room, then all players.
    """
    # Check current room first
    result = get_char_room_vis(ch, name, world)
    if result is not None:
        return result

    # Search all online players
    number, target = get_number(name)
    if number == 0:
        return None

    j = 0
    for player in world.players:
        if isname(target, player.player.name):
            j += 1
            if j == number:
                return player
    return None


def get_obj_in_list_vis(
    ch: CharData, name: str, obj_list: list[ObjData],
) -> ObjData | None:
    """Find an object in a list by name (with number prefix).

    Ported from get_obj_in_list_vis() in handler.c.
    Phase 2: no visibility checks yet.
    """
    number, target = get_number(name)
    if number == 0:
        return None

    j = 0
    for obj in obj_list:
        if isname(target, obj.name):
            j += 1
            if j == number:
                return obj
    return None


def get_obj_vis(
    ch: CharData, name: str, world: GameWorld,
) -> ObjData | None:
    """Find an object visible to ch: inventory, equipment, room, then world.

    Ported from get_obj_vis() in handler.c.
    """
    # Check inventory
    carrying = getattr(ch, "carrying", [])
    result = get_obj_in_list_vis(ch, name, carrying)
    if result is not None:
        return result

    # Check equipment
    for pos in range(NUM_WEARS):
        obj = ch.equipment[pos]
        if obj is not None and isinstance(obj, ObjData):
            if isname(name, obj.name):
                return obj

    # Check room
    if ch.in_room != NOWHERE and ch.in_room in world.rooms:
        room = world.rooms[ch.in_room]
        result = get_obj_in_list_vis(ch, name, room._objects)
        if result is not None:
            return result

    return None


def get_obj_in_equip_vis(
    ch: CharData, name: str,
) -> tuple[ObjData | None, int]:
    """Find an object in ch's equipment by name.

    Returns (obj, position) or (None, -1).
    """
    number, target = get_number(name)
    if number == 0:
        return (None, -1)

    j = 0
    for pos in range(NUM_WEARS):
        obj = ch.equipment[pos]
        if obj is not None and isinstance(obj, ObjData):
            if isname(target, obj.name):
                j += 1
                if j == number:
                    return (obj, pos)
    return (None, -1)
