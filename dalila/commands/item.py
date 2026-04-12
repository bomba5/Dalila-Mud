"""Item manipulation commands: get, drop, put, give, wear, remove, drink, eat.

Ported from act.item.c: do_get, do_drop, do_put, do_give, do_wear,
do_remove, do_wield, do_drink, do_eat.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from dalila.constants import (
    NOWHERE,
    NUM_WEARS,
    ContainerFlag,
    ItemExtraFlag,
    ItemType,
    ItemWearFlag,
    Position,
    WearPosition,
)
from dalila.engine.handler import (
    equip_char,
    find_all_dots,
    get_char_room_vis,
    get_obj_in_equip_vis,
    get_obj_in_list_vis,
    isname,
    obj_from_char,
    obj_from_obj,
    obj_from_room,
    obj_to_char,
    obj_to_obj,
    obj_to_room,
    unequip_char,
)
from dalila.models.object import ObjData

if TYPE_CHECKING:
    from dalila.engine.game_loop import GameWorld, LiveRoom
    from dalila.models.character import CharData
    from dalila.net.descriptor import Descriptor

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _send(desc: Descriptor, text: str) -> None:
    """Fire-and-forget send to a descriptor."""
    asyncio.ensure_future(desc.send(text))


def _send_to_room(
    room: LiveRoom, text: str, exclude: CharData | None = None,
) -> None:
    """Send text to everyone in a room except excluded character."""
    for other in room._characters:
        if other is not exclude and other.desc:
            asyncio.ensure_future(other.desc.send(text))


# ---------------------------------------------------------------------------
# GET (prendi) — pick up objects from room or container
# ---------------------------------------------------------------------------

def _perform_get_from_room(
    ch: CharData, obj: ObjData, desc: Descriptor, world: GameWorld,
) -> bool:
    """Pick up a single object from the room.

    Ported from perform_get_from_room() in act.item.c.
    """
    obj_name = obj.short_description if obj.short_description else "qualcosa"

    # Check NODROP flag (can't pick up)
    if obj.obj_flags.extra_flags & ItemExtraFlag.ITEM_NODROP:
        _send(desc, f"Non riesci a prendere {obj_name}.\r\n")
        return False

    obj_from_room(obj, world)
    obj_to_char(obj, ch)
    _send(desc, f"Prendi {obj_name}.\r\n")

    if ch.in_room in world.rooms:
        _send_to_room(
            world.rooms[ch.in_room],
            f"\r\n{ch.player.name} prende {obj_name}.\r\n",
            exclude=ch,
        )
    return True


def _get_from_room(
    ch: CharData, arg: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Get object(s) from the room floor.

    Ported from get_from_room() in act.item.c.
    """
    if ch.in_room == NOWHERE or ch.in_room not in world.rooms:
        return

    room = world.rooms[ch.in_room]
    dotmode = find_all_dots(arg)

    if dotmode == 1:
        # 'get all'
        if not room._objects:
            _send(desc, "Non c'e' niente qui.\r\n")
            return
        for obj in list(room._objects):
            _perform_get_from_room(ch, obj, desc, world)
    elif dotmode == 2:
        # 'get all.keyword'
        keyword = arg.split(".", 1)[1]
        found = False
        for obj in list(room._objects):
            if isname(keyword, obj.name):
                _perform_get_from_room(ch, obj, desc, world)
                found = True
        if not found:
            _send(desc, f"Non vedi {keyword} qui.\r\n")
    else:
        # 'get keyword'
        obj = get_obj_in_list_vis(ch, arg, room._objects)
        if obj is None:
            _send(desc, f"Non vedi {arg} qui.\r\n")
        else:
            _perform_get_from_room(ch, obj, desc, world)


def _perform_get_from_container(
    ch: CharData, obj: ObjData, container: ObjData,
    desc: Descriptor, world: GameWorld,
) -> bool:
    """Get a single object from a container."""
    obj_name = obj.short_description if obj.short_description else "qualcosa"
    cont_name = container.short_description if container.short_description else "qualcosa"

    obj_from_obj(obj)
    obj_to_char(obj, ch)
    _send(desc, f"Prendi {obj_name} da {cont_name}.\r\n")

    if ch.in_room in world.rooms:
        _send_to_room(
            world.rooms[ch.in_room],
            f"\r\n{ch.player.name} prende {obj_name} da {cont_name}.\r\n",
            exclude=ch,
        )
    return True


def _get_from_container(
    ch: CharData, arg: str, container: ObjData,
    desc: Descriptor, world: GameWorld,
) -> None:
    """Get object(s) from a container.

    Ported from get_from_container() in act.item.c.
    """
    # Check if container is closed
    if container.obj_flags.value[1] & ContainerFlag.CONT_CLOSED:
        cont_name = container.short_description or "qualcosa"
        _send(desc, f"{cont_name} e' chiuso.\r\n")
        return

    contents = getattr(container, "contains", [])

    dotmode = find_all_dots(arg)
    if dotmode == 1:
        # 'get all container'
        if not contents:
            _send(desc, "Non c'e' niente dentro.\r\n")
            return
        for obj in list(contents):
            _perform_get_from_container(ch, obj, container, desc, world)
    elif dotmode == 2:
        # 'get all.keyword container'
        keyword = arg.split(".", 1)[1]
        found = False
        for obj in list(contents):
            if isname(keyword, obj.name):
                _perform_get_from_container(ch, obj, container, desc, world)
                found = True
        if not found:
            _send(desc, f"Non trovi {keyword} dentro.\r\n")
    else:
        obj = get_obj_in_list_vis(ch, arg, contents)
        if obj is None:
            _send(desc, f"Non trovi {arg} dentro.\r\n")
        else:
            _perform_get_from_container(ch, obj, container, desc, world)


def do_get(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Get command: pick up objects from room or container.

    Ported from ACMD(do_get) in act.item.c.
    Usage: get <item>, get all, get <item> <container>
    """
    args = argument.strip().split(None, 1)
    if not args:
        _send(desc, "Prendi cosa?\r\n")
        return

    obj_arg = args[0]
    from_arg = args[1] if len(args) > 1 else ""

    if from_arg:
        # 'get <item> from <container>' or 'get <item> <container>'
        # Remove 'from'/'da' prefix
        from_parts = from_arg.split(None, 1)
        if from_parts[0].lower() in ("from", "da"):
            from_arg = from_parts[1] if len(from_parts) > 1 else ""
        else:
            from_arg = from_arg

        if not from_arg:
            _send(desc, "Da cosa vuoi prendere?\r\n")
            return

        # Find the container
        carrying = getattr(ch, "carrying", [])
        container = get_obj_in_list_vis(ch, from_arg, carrying)
        if container is None and ch.in_room in world.rooms:
            room = world.rooms[ch.in_room]
            container = get_obj_in_list_vis(ch, from_arg, room._objects)
        if container is None:
            _send(desc, f"Non hai {from_arg}.\r\n")
            return

        if container.obj_flags.type_flag != ItemType.ITEM_CONTAINER:
            _send(desc, "Non e' un contenitore.\r\n")
            return

        _get_from_container(ch, obj_arg, container, desc, world)
    else:
        _get_from_room(ch, obj_arg, desc, world)


# ---------------------------------------------------------------------------
# DROP (lascia) — put objects on the ground
# ---------------------------------------------------------------------------

def _perform_drop(
    ch: CharData, obj: ObjData, desc: Descriptor, world: GameWorld,
) -> bool:
    """Drop a single object to the room.

    Ported from perform_drop() in act.item.c.
    """
    obj_name = obj.short_description if obj.short_description else "qualcosa"

    if obj.obj_flags.extra_flags & ItemExtraFlag.ITEM_NODROP:
        _send(desc, f"Non riesci a lasciar andare {obj_name}!\r\n")
        return False

    obj_from_char(obj, ch)
    obj_to_room(obj, ch.in_room, world)
    _send(desc, f"Lasci {obj_name}.\r\n")

    if ch.in_room in world.rooms:
        _send_to_room(
            world.rooms[ch.in_room],
            f"\r\n{ch.player.name} lascia {obj_name}.\r\n",
            exclude=ch,
        )
    return True


def do_drop(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Drop command: put objects on the ground.

    Ported from ACMD(do_drop) in act.item.c.
    """
    arg = argument.strip()
    if not arg:
        _send(desc, "Cosa vuoi lasciare?\r\n")
        return

    carrying = getattr(ch, "carrying", [])
    dotmode = find_all_dots(arg)

    if dotmode == 1:
        # 'drop all'
        if not carrying:
            _send(desc, "Non porti niente.\r\n")
            return
        for obj in list(carrying):
            _perform_drop(ch, obj, desc, world)
    elif dotmode == 2:
        # 'drop all.keyword'
        keyword = arg.split(".", 1)[1]
        found = False
        for obj in list(carrying):
            if isname(keyword, obj.name):
                _perform_drop(ch, obj, desc, world)
                found = True
        if not found:
            _send(desc, f"Non porti niente del genere.\r\n")
    else:
        obj = get_obj_in_list_vis(ch, arg, carrying)
        if obj is None:
            _send(desc, f"Non hai {arg}.\r\n")
        else:
            _perform_drop(ch, obj, desc, world)


# ---------------------------------------------------------------------------
# PUT (metti) — place objects into containers
# ---------------------------------------------------------------------------

def do_put(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Put an object into a container.

    Ported from ACMD(do_put) in act.item.c.
    Usage: put <item> <container>
    """
    args = argument.strip().split(None, 1)
    if len(args) < 2:
        _send(desc, "Metti cosa in cosa?\r\n")
        return

    obj_arg = args[0]
    cont_arg = args[1]

    # Remove 'in' preposition if present
    cont_parts = cont_arg.split(None, 1)
    if cont_parts[0].lower() in ("in", "dentro"):
        cont_arg = cont_parts[1] if len(cont_parts) > 1 else ""
    if not cont_arg:
        _send(desc, "In cosa vuoi mettere?\r\n")
        return

    # Find the container
    carrying = getattr(ch, "carrying", [])
    container = get_obj_in_list_vis(ch, cont_arg, carrying)
    if container is None and ch.in_room in world.rooms:
        room = world.rooms[ch.in_room]
        container = get_obj_in_list_vis(ch, cont_arg, room._objects)
    if container is None:
        _send(desc, f"Non vedi {cont_arg} qui.\r\n")
        return

    if container.obj_flags.type_flag != ItemType.ITEM_CONTAINER:
        _send(desc, "Non e' un contenitore.\r\n")
        return

    if container.obj_flags.value[1] & ContainerFlag.CONT_CLOSED:
        _send(desc, "E' chiuso.\r\n")
        return

    # Find the object to put
    obj = get_obj_in_list_vis(ch, obj_arg, carrying)
    if obj is None:
        _send(desc, f"Non hai {obj_arg}.\r\n")
        return

    if obj is container:
        _send(desc, "Non puoi mettere un oggetto dentro se stesso.\r\n")
        return

    obj_name = obj.short_description if obj.short_description else "qualcosa"
    cont_name = container.short_description if container.short_description else "qualcosa"

    obj_from_char(obj, ch)
    obj_to_obj(obj, container)
    _send(desc, f"Metti {obj_name} in {cont_name}.\r\n")

    if ch.in_room in world.rooms:
        _send_to_room(
            world.rooms[ch.in_room],
            f"\r\n{ch.player.name} mette {obj_name} in {cont_name}.\r\n",
            exclude=ch,
        )


# ---------------------------------------------------------------------------
# GIVE (dai) — give objects to another character
# ---------------------------------------------------------------------------

def do_give(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Give an object to another character.

    Ported from ACMD(do_give) in act.item.c.
    Usage: give <item> <target>
    """
    args = argument.strip().split(None, 1)
    if len(args) < 2:
        _send(desc, "Dare cosa a chi?\r\n")
        return

    obj_arg = args[0]
    target_arg = args[1]

    # Remove 'a' / 'to' preposition if present
    target_parts = target_arg.split(None, 1)
    if target_parts[0].lower() in ("a", "to"):
        target_arg = target_parts[1] if len(target_parts) > 1 else ""
    if not target_arg:
        _send(desc, "A chi vuoi dare?\r\n")
        return

    # Check for gold: 'give 100 coins <target>'
    # (Simplified: if obj_arg is a number, treat as gold)
    if obj_arg.isdigit():
        _give_gold(ch, int(obj_arg), target_arg, desc, world)
        return

    # Find the object
    carrying = getattr(ch, "carrying", [])
    obj = get_obj_in_list_vis(ch, obj_arg, carrying)
    if obj is None:
        _send(desc, f"Non hai {obj_arg}.\r\n")
        return

    # Find the target
    vict = get_char_room_vis(ch, target_arg, world)
    if vict is None:
        _send(desc, "Non c'e' nessuno qui con quel nome.\r\n")
        return
    if vict is ch:
        _send(desc, "Non puoi darlo a te stesso!\r\n")
        return

    obj_name = obj.short_description if obj.short_description else "qualcosa"

    if obj.obj_flags.extra_flags & ItemExtraFlag.ITEM_NODROP:
        _send(desc, f"Non riesci a lasciar andare {obj_name}!\r\n")
        return

    obj_from_char(obj, ch)
    obj_to_char(obj, vict)
    _send(desc, f"Dai {obj_name} a {vict.player.name}.\r\n")

    if vict.desc:
        _send(vict.desc,
              f"\r\n{ch.player.name} ti da' {obj_name}.\r\n")

    if ch.in_room in world.rooms:
        _send_to_room(
            world.rooms[ch.in_room],
            f"\r\n{ch.player.name} da' {obj_name} a {vict.player.name}.\r\n",
            exclude=ch,
        )


def _give_gold(
    ch: CharData, amount: int, target_arg: str,
    desc: Descriptor, world: GameWorld,
) -> None:
    """Give gold to another character."""
    if amount <= 0:
        _send(desc, "Dai una quantita' positiva!\r\n")
        return
    if ch.points.gold < amount:
        _send(desc, "Non hai tutto quell'oro!\r\n")
        return

    vict = get_char_room_vis(ch, target_arg, world)
    if vict is None:
        _send(desc, "Non c'e' nessuno qui con quel nome.\r\n")
        return
    if vict is ch:
        _send(desc, "Che utile!\r\n")
        return

    ch.points.gold -= amount
    vict.points.gold += amount
    _send(desc, f"Dai {amount} monete d'oro a {vict.player.name}.\r\n")
    if vict.desc:
        _send(vict.desc,
              f"\r\n{ch.player.name} ti da' {amount} monete d'oro.\r\n")


# ---------------------------------------------------------------------------
# WEAR (indossa) — equip items
# ---------------------------------------------------------------------------

# Mapping from wear flag to equipment position(s)
_WEAR_FLAG_TO_POS: list[tuple[int, int]] = [
    (ItemWearFlag.ITEM_WEAR_FINGER, WearPosition.WEAR_FINGER_R),
    (ItemWearFlag.ITEM_WEAR_FINGER, WearPosition.WEAR_FINGER_L),
    (ItemWearFlag.ITEM_WEAR_NECK, WearPosition.WEAR_NECK_1),
    (ItemWearFlag.ITEM_WEAR_NECK, WearPosition.WEAR_NECK_2),
    (ItemWearFlag.ITEM_WEAR_BODY, WearPosition.WEAR_BODY),
    (ItemWearFlag.ITEM_WEAR_HEAD, WearPosition.WEAR_HEAD),
    (ItemWearFlag.ITEM_WEAR_LEGS, WearPosition.WEAR_LEGS),
    (ItemWearFlag.ITEM_WEAR_FEET, WearPosition.WEAR_FEET),
    (ItemWearFlag.ITEM_WEAR_HANDS, WearPosition.WEAR_HANDS),
    (ItemWearFlag.ITEM_WEAR_ARMS, WearPosition.WEAR_ARMS),
    (ItemWearFlag.ITEM_WEAR_SHIELD, WearPosition.WEAR_SHIELD),
    (ItemWearFlag.ITEM_WEAR_ABOUT, WearPosition.WEAR_ABOUT),
    (ItemWearFlag.ITEM_WEAR_WAIST, WearPosition.WEAR_WAIST),
    (ItemWearFlag.ITEM_WEAR_WRIST, WearPosition.WEAR_WRIST_R),
    (ItemWearFlag.ITEM_WEAR_WRIST, WearPosition.WEAR_WRIST_L),
    (ItemWearFlag.ITEM_WEAR_WIELD, WearPosition.WEAR_WIELD),
    (ItemWearFlag.ITEM_WEAR_HOLD, WearPosition.WEAR_HOLD),
]


def _find_eq_pos(ch: CharData, obj: ObjData) -> int:
    """Find the first available equipment position for an object.

    Ported from find_eq_pos() in act.item.c.
    Returns -1 if no valid position found.
    """
    wear_flags = obj.obj_flags.wear_flags

    for flag, pos in _WEAR_FLAG_TO_POS:
        if wear_flags & flag:
            if ch.equipment[pos] is None:
                return pos
    return -1


def _perform_wear(
    ch: CharData, obj: ObjData, where: int, desc: Descriptor,
) -> None:
    """Equip an object at a specific position.

    Ported from perform_wear() in act.item.c.
    """
    obj_name = obj.short_description if obj.short_description else "qualcosa"

    if ch.equipment[where] is not None:
        _send(desc, f"Stai gia' usando qualcosa li'.\r\n")
        return

    obj_from_char(obj, ch)
    equip_char(ch, obj, where)
    _send(desc, f"Indossi {obj_name}.\r\n")


def do_wear(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Wear/equip an item.

    Ported from ACMD(do_wear) in act.item.c.
    """
    arg = argument.strip()
    if not arg:
        _send(desc, "Cosa vuoi indossare?\r\n")
        return

    carrying = getattr(ch, "carrying", [])

    dotmode = find_all_dots(arg)
    if dotmode == 1:
        # 'wear all'
        for obj in list(carrying):
            if not (obj.obj_flags.wear_flags & ItemWearFlag.ITEM_WEAR_TAKE):
                continue
            pos = _find_eq_pos(ch, obj)
            if pos >= 0:
                _perform_wear(ch, obj, pos, desc)
    else:
        obj = get_obj_in_list_vis(ch, arg, carrying)
        if obj is None:
            _send(desc, f"Non hai {arg}.\r\n")
            return

        pos = _find_eq_pos(ch, obj)
        if pos < 0:
            _send(desc, "Non puoi indossare quello.\r\n")
            return
        _perform_wear(ch, obj, pos, desc)


# ---------------------------------------------------------------------------
# WIELD (impugna)
# ---------------------------------------------------------------------------

def do_wield(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Wield a weapon.

    Ported from ACMD(do_wield) in act.item.c.
    """
    arg = argument.strip()
    if not arg:
        _send(desc, "Cosa vuoi impugnare?\r\n")
        return

    carrying = getattr(ch, "carrying", [])
    obj = get_obj_in_list_vis(ch, arg, carrying)
    if obj is None:
        _send(desc, f"Non hai {arg}.\r\n")
        return

    if not (obj.obj_flags.wear_flags & ItemWearFlag.ITEM_WEAR_WIELD):
        _send(desc, "Non puoi impugnare quello.\r\n")
        return

    if ch.equipment[WearPosition.WEAR_WIELD] is not None:
        _send(desc, "Stai gia' impugnando qualcosa.\r\n")
        return

    _perform_wear(ch, obj, WearPosition.WEAR_WIELD, desc)


# ---------------------------------------------------------------------------
# REMOVE (rimuovi) — unequip items
# ---------------------------------------------------------------------------

def _perform_remove(
    ch: CharData, pos: int, desc: Descriptor,
) -> None:
    """Remove an item from an equipment slot.

    Ported from perform_remove() in act.item.c.
    """
    obj = ch.equipment[pos]
    if obj is None:
        return

    obj_name = obj.short_description if obj.short_description else "qualcosa"

    removed = unequip_char(ch, pos)
    if removed is not None:
        obj_to_char(removed, ch)
        _send(desc, f"Smetti di usare {obj_name}.\r\n")


def do_remove(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Remove an equipped item.

    Ported from ACMD(do_remove) in act.item.c.
    """
    arg = argument.strip()
    if not arg:
        _send(desc, "Cosa vuoi togliere?\r\n")
        return

    obj, pos = get_obj_in_equip_vis(ch, arg)
    if obj is None:
        _send(desc, f"Non stai usando {arg}.\r\n")
        return

    _perform_remove(ch, pos, desc)


# ---------------------------------------------------------------------------
# DRINK (bevi) — drink from containers/fountains
# ---------------------------------------------------------------------------

def do_drink(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Drink from a container or fountain.

    Ported from ACMD(do_drink) in act.item.c.
    Simplified for Phase 2.
    """
    arg = argument.strip()
    if not arg:
        _send(desc, "Bevi da cosa?\r\n")
        return

    # Look for drink container in inventory or room
    carrying = getattr(ch, "carrying", [])
    obj = get_obj_in_list_vis(ch, arg, carrying)
    if obj is None and ch.in_room in world.rooms:
        room = world.rooms[ch.in_room]
        obj = get_obj_in_list_vis(ch, arg, room._objects)
    if obj is None:
        _send(desc, f"Non trovi {arg}.\r\n")
        return

    obj_type = obj.obj_flags.type_flag
    if obj_type not in (ItemType.ITEM_DRINKCON, ItemType.ITEM_FOUNTAIN):
        _send(desc, "Non puoi bere da quello!\r\n")
        return

    # Check if empty
    if obj.obj_flags.value[1] <= 0:
        _send(desc, "E' vuoto.\r\n")
        return

    # Drink (simplified: just reduce amount)
    obj_name = obj.short_description if obj.short_description else "qualcosa"
    _send(desc, f"Bevi da {obj_name}.\r\n")
    if ch.in_room in world.rooms:
        _send_to_room(
            world.rooms[ch.in_room],
            f"\r\n{ch.player.name} beve da {obj_name}.\r\n",
            exclude=ch,
        )

    if obj_type == ItemType.ITEM_DRINKCON:
        obj.obj_flags.value[1] = max(0, obj.obj_flags.value[1] - 1)

    # Update thirst condition
    if ch.player_specials is not None:
        ch.player_specials.conditions[2] = min(
            24, ch.player_specials.conditions[2] + 1,
        )


# ---------------------------------------------------------------------------
# EAT (mangia) — eat food items
# ---------------------------------------------------------------------------

def do_eat(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Eat a food item.

    Ported from ACMD(do_eat) in act.item.c.
    Simplified for Phase 2.
    """
    arg = argument.strip()
    if not arg:
        _send(desc, "Mangia cosa?\r\n")
        return

    carrying = getattr(ch, "carrying", [])
    obj = get_obj_in_list_vis(ch, arg, carrying)
    if obj is None:
        _send(desc, f"Non hai {arg}.\r\n")
        return

    if obj.obj_flags.type_flag != ItemType.ITEM_FOOD:
        _send(desc, "Non puoi mangiare QUELLO!\r\n")
        return

    obj_name = obj.short_description if obj.short_description else "qualcosa"
    _send(desc, f"Mangi {obj_name}.\r\n")
    if ch.in_room in world.rooms:
        _send_to_room(
            world.rooms[ch.in_room],
            f"\r\n{ch.player.name} mangia {obj_name}.\r\n",
            exclude=ch,
        )

    # Update hunger condition
    if ch.player_specials is not None:
        ch.player_specials.conditions[1] = min(
            24, ch.player_specials.conditions[1] + obj.obj_flags.value[0],
        )

    # Remove the food object
    obj_from_char(obj, ch)


# ---------------------------------------------------------------------------
# INVENTORY (inventario)
# ---------------------------------------------------------------------------

def do_inventory(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Show character inventory.

    Ported from ACMD(do_inventory) in act.informative.c.
    """
    _send(desc, "Stai portando:\r\n")
    carrying = getattr(ch, "carrying", [])
    if not carrying:
        _send(desc, "  Niente.\r\n")
    else:
        for obj in carrying:
            obj_name = obj.short_description if obj.short_description else "qualcosa"
            _send(desc, f"  {obj_name}\r\n")


# ---------------------------------------------------------------------------
# EQUIPMENT (equipaggiamento)
# ---------------------------------------------------------------------------

def do_equipment(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Show character equipment.

    Ported from ACMD(do_equipment) in act.informative.c.
    """
    from dalila.commands.informative import _wear_position_name

    _send(desc, "Stai usando:\r\n")
    found = False
    for pos in range(NUM_WEARS):
        obj = ch.equipment[pos]
        if obj is not None and isinstance(obj, ObjData):
            wear_name = _wear_position_name(pos)
            obj_name = obj.short_description if obj.short_description else "qualcosa"
            _send(desc, f"  {wear_name:20s} {obj_name}\r\n")
            found = True
    if not found:
        _send(desc, "  <Niente>\r\n")
