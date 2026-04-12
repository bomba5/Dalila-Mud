"""Magic commands: cast/lancia, recite/recita, quaff/bevi_pozione.

Ported from spell_parser.c: do_cast, do_recite, do_quaff.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from dalila.constants import (
    NOWHERE,
    Position,
)
from dalila.combat.spells import (
    TAR_CHAR_ROOM,
    TAR_FIGHT_VICT,
    TAR_FIGHT_SELF,
    TAR_SELF_ONLY,
    TAR_NOT_SELF,
    cast_spell,
    find_spell_num,
    get_spell_name,
    mag_manacost,
    spell_info,
)
from dalila.combat.fight import (
    _fighting,
    _send_to_char,
    _act_to_room,
)
from dalila.engine.handler import get_char_room_vis

if TYPE_CHECKING:
    from dalila.engine.game_loop import GameWorld
    from dalila.models.character import CharData
    from dalila.net.descriptor import Descriptor

log = logging.getLogger(__name__)


def _send(desc, text: str) -> None:
    """Fire-and-forget send to a descriptor."""
    if desc is not None:
        asyncio.ensure_future(desc.send(text))


# ---------------------------------------------------------------------------
# do_cast / do_lancia
# Ported from ACMD(do_cast) in spell_parser.c
# ---------------------------------------------------------------------------

def do_cast(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Cast a spell.

    Ported from ACMD(do_cast) in spell_parser.c.
    Usage: cast 'spell name' [target]
    """
    argument = argument.strip()

    if not argument:
        _send(desc, "Quale incantesimo vuoi lanciare?\r\n")
        return

    # Parse spell name -- may be in single quotes
    spell_name = ""
    target_name = ""

    if argument.startswith("'"):
        end = argument.find("'", 1)
        if end == -1:
            _send(desc, "L'incantesimo dev'essere tra apici: lancia 'nome'\r\n")
            return
        spell_name = argument[1:end]
        target_name = argument[end + 1:].strip()
    else:
        parts = argument.split(None, 1)
        spell_name = parts[0]
        target_name = parts[1] if len(parts) > 1 else ""

    # Find spell
    spellnum = find_spell_num(spell_name)
    if spellnum < 0:
        _send(desc, "Non conosci questo incantesimo!\r\n")
        return

    si = spell_info.get(spellnum)
    if si is None:
        _send(desc, "Non conosci questo incantesimo!\r\n")
        return

    # Check minimum level
    class_ = ch.player.class_
    if 0 <= class_ < len(si.min_level):
        if ch.player.level < si.min_level[class_]:
            _send(desc, "Non hai ancora raggiunto il livello per usarlo.\r\n")
            return

    # Check position
    if ch.position < si.min_position:
        match ch.position:
            case Position.POS_SLEEPING:
                _send(desc, "Dormendo??\r\n")
            case Position.POS_RESTING:
                _send(desc, "Non puoi concentrarti abbastanza riposando.\r\n")
            case Position.POS_SITTING:
                _send(desc, "Non puoi farlo da seduto!\r\n")
            case Position.POS_FIGHTING:
                _send(desc, "Impossibile! Stai combattendo!\r\n")
            case _:
                _send(desc, "Non puoi farlo adesso.\r\n")
        return

    # Find target
    victim = None

    if si.targets & TAR_FIGHT_VICT and not target_name:
        # Default to fighting target
        victim = _fighting(ch)
        if victim is None:
            _send(desc, "Con chi stai combattendo?\r\n")
            return
    elif si.targets & TAR_FIGHT_SELF and not target_name:
        victim = ch
    elif si.targets & TAR_SELF_ONLY:
        victim = ch
    elif si.targets & TAR_CHAR_ROOM:
        if target_name:
            victim = get_char_room_vis(ch, target_name, world)
            if victim is None:
                _send(desc, "Non trovi quella persona.\r\n")
                return
        else:
            # Self for non-violent, fight target for violent
            if si.violent:
                victim = _fighting(ch)
                if victim is None:
                    _send(desc, "Su chi vuoi lanciare l'incantesimo?\r\n")
                    return
            else:
                victim = ch

    # TAR_NOT_SELF check
    if si.targets & TAR_NOT_SELF and victim is ch:
        _send(desc, "Non puoi lanciarlo su te stesso!\r\n")
        return

    # Check mana
    mana = mag_manacost(ch, spellnum)
    if ch.points.mana < mana:
        _send(desc, "Non hai abbastanza mana!\r\n")
        return

    # Announce
    spell_n = get_spell_name(spellnum)
    _send(desc, f"Lanci '{spell_n}'.\r\n")
    _act_to_room(
        ch, victim,
        f"$n pronuncia le parole di un incantesimo.",
        world,
    )

    # Cast
    cast_spell(ch, victim, None, spellnum, world)
