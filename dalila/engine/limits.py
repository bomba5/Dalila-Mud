"""Character limits: experience gain, level advancement, regen.

Ported from limits.c: gain_exp(), advance_level(), point_update(),
and class.c: titles[][] for level thresholds.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from dalila.constants import (
    LVL_IMMORT,
    LVL_IMPL,
    CharClass,
)
from dalila.systems.classes import level_exp

if TYPE_CHECKING:
    from dalila.models.character import CharData

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# gain_exp
# Ported from gain_exp() in limits.c
# ---------------------------------------------------------------------------

def gain_exp(ch: CharData, gain: int) -> int:
    """Award (or deduct) experience points.

    Ported from gain_exp() in limits.c.
    Returns actual amount gained.
    Checks for level-up if positive gain.
    """
    if ch.nr >= 0:
        # NPCs don't gain experience
        return 0

    gain = int(gain)

    if gain > 0:
        # Don't let them go above the next level's threshold too much
        ch.points.exp += gain

        # Check for level-up
        _check_level_advance(ch)
    else:
        # Experience loss
        ch.points.exp += gain
        if ch.points.exp < 0:
            ch.points.exp = 0

    return gain


def _check_level_advance(ch: CharData) -> None:
    """Check if a character should advance a level.

    Ported from the level-check logic in gain_exp() from limits.c.
    """
    level = ch.player.level
    if level >= LVL_IMMORT:
        return  # Immortals don't auto-level

    next_level = level + 1
    if next_level > 70:
        return  # Mortal cap is 70

    threshold = level_exp(ch.player.class_, next_level)
    if ch.points.exp >= threshold:
        advance_level(ch)


# ---------------------------------------------------------------------------
# advance_level
# Ported from advance_level() in class.c
# ---------------------------------------------------------------------------

def advance_level(ch: CharData) -> None:
    """Level up a character: increase HP, mana, move.

    Ported from advance_level() in class.c.
    """
    import random
    from dalila.combat.fight import _send_to_char

    ch.player.level += 1
    level = ch.player.level

    # HP gain based on class
    match ch.player.class_:
        case CharClass.CLASS_MAGIC_USER:
            hp_gain = random.randint(3, 8)
            mana_gain = random.randint(level, int(1.5 * level))
            move_gain = random.randint(1, 3)
        case CharClass.CLASS_CLERIC:
            hp_gain = random.randint(5, 10)
            mana_gain = random.randint(level, int(1.5 * level))
            move_gain = random.randint(1, 4)
        case CharClass.CLASS_THIEF:
            hp_gain = random.randint(7, 13)
            mana_gain = random.randint(1, level // 2 + 1)
            move_gain = random.randint(2, 6)
        case CharClass.CLASS_WARRIOR:
            hp_gain = random.randint(10, 15)
            mana_gain = random.randint(1, level // 3 + 1)
            move_gain = random.randint(2, 5)
        case CharClass.CLASS_PELOI:
            hp_gain = random.randint(7, 13)
            mana_gain = random.randint(1, level // 2 + 1)
            move_gain = random.randint(2, 6)
        case CharClass.CLASS_DARESIANO:
            hp_gain = random.randint(5, 10)
            mana_gain = random.randint(1, level // 3 + 1)
            move_gain = random.randint(1, 4)
        case _:
            hp_gain = random.randint(5, 10)
            mana_gain = random.randint(1, 5)
            move_gain = random.randint(1, 4)

    # Constitution bonus to HP
    con = ch.aff_abils.con
    if con >= 15:
        hp_gain += (con - 14) // 2

    # Apply gains
    ch.points.max_hit += max(1, hp_gain)
    ch.points.max_mana += max(1, mana_gain)
    ch.points.max_move += max(1, move_gain)

    # Restore to full on level up
    ch.points.hit = ch.points.max_hit
    ch.points.mana = ch.points.max_mana
    ch.points.move = ch.points.max_move

    _send_to_char(
        ch,
        f"\r\n&W*** Congratulazioni! Hai raggiunto il livello {level}! ***&0\r\n"
        f"  HP: +{hp_gain}  Mana: +{mana_gain}  Move: +{move_gain}\r\n\r\n",
    )

    log.info(
        "ADVANCE: %s is now level %d (HP +%d, Mana +%d, Move +%d)",
        ch.player.name, level, hp_gain, mana_gain, move_gain,
    )
