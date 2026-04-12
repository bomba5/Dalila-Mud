"""Offensive combat commands.

Ported from act.offensive.c: do_kill/uccidi, do_hit/colpisci, do_flee/fuggi,
do_kick/calcia, do_bash/sfondata, do_backstab/pugnala, do_rescue/salva,
do_assist/assisti, do_disarm.
"""

from __future__ import annotations

import asyncio
import random
import logging
from typing import TYPE_CHECKING

from dalila.constants import (
    LVL_IMMORT,
    NOWHERE,
    NUM_OF_DIRS,
    AffectedBy,
    ItemType,
    MobFlag,
    Position,
    WearPosition,
)
from dalila.combat.fight import (
    _fighting,
    _is_npc,
    _send,
    _send_to_char,
    _act_to_room,
    combat_list,
    damage,
    hit,
    set_fighting,
    stop_fighting,
)
from dalila.engine.handler import get_char_room_vis
from dalila.systems.classes import (
    SKILL_BACKSTAB,
    SKILL_BASH,
    SKILL_KICK,
    SKILL_RESCUE,
    TYPE_HIT,
    TYPE_UNDEFINED,
    backstab_mult,
)

if TYPE_CHECKING:
    from dalila.engine.game_loop import GameWorld
    from dalila.models.character import CharData
    from dalila.net.descriptor import Descriptor

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# do_hit / do_kill (colpisci / uccidi)
# Ported from act.offensive.c do_hit() lines 148-260
# ---------------------------------------------------------------------------

def do_hit(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Start combat with a target.

    Ported from ACMD(do_hit) in act.offensive.c.
    """
    argument = argument.strip()

    if not argument:
        _send(desc, "Colpire chi?\r\n")
        return

    vict = get_char_room_vis(ch, argument, world)
    if vict is None:
        _send(desc, "Non sembra essere qui.\r\n")
        return

    if vict is ch:
        _send(desc, "Ti colpisci..OUCH!.\r\n")
        return

    if _fighting(ch) is not None and _fighting(ch) is vict:
        _send(desc, "Stai gia' combattendo!\r\n")
        return

    hit(ch, vict, TYPE_UNDEFINED, world)


def do_kill(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Kill command -- same as hit for mortals.

    Ported from ACMD(do_hit) with subcmd SCMD_MURDER.
    """
    do_hit(ch, argument, desc, world)


# ---------------------------------------------------------------------------
# do_flee (fuggi)
# Ported from act.offensive.c do_flee() lines 545-618
# ---------------------------------------------------------------------------

def do_flee(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Attempt to flee from combat.

    Ported from ACMD(do_flee) in act.offensive.c.
    """
    if ch.in_room == NOWHERE:
        return

    # Paralysis check
    aff = ch.char_specials_saved.affected_by[0]
    if aff & AffectedBy.AFF_PARALIZE:
        _send(desc, "Sei &1&bParalizzato&0 non riesci a scappare!\r\n")
        return

    if ch.position < Position.POS_FIGHTING:
        _send(desc, "Uhm... non sei messo bene, non riesci a scappare!\r\n")
        return

    # Dexterity check
    if random.randint(0, 30) > ch.aff_abils.dex:
        _send(desc, "Non riesci a scappare!\r\n")
        return

    # Try random directions
    if ch.in_room not in world.rooms:
        return
    room = world.rooms[ch.in_room]

    for _ in range(6):
        attempt = random.randint(0, NUM_OF_DIRS - 1)

        if (room.data.dir_option
                and attempt < len(room.data.dir_option)
                and room.data.dir_option[attempt] is not None):
            target = room.data.dir_option[attempt].to_room
            if target != NOWHERE and target in world.rooms:
                # Notify room
                _act_to_room(
                    ch, None,
                    "$n va in panico e tenta di fuggire!",
                    world,
                )

                # Stop combat
                victim = _fighting(ch)
                if victim is not None:
                    if _fighting(victim) is ch:
                        stop_fighting(victim)
                    stop_fighting(ch)

                # Move character
                from dalila.engine.handler import char_from_room, char_to_room
                char_from_room(ch, world)
                char_to_room(ch, target, world)

                _send(desc, "Scappi a gambe levate.\r\n")

                # Show the new room
                from dalila.commands.informative import look_at_room
                look_at_room(ch, desc, world)
                return

    _send(desc, "PANICO!  Non puoi scappare!\r\n")


# ---------------------------------------------------------------------------
# do_kick (calcia)
# Ported from act.offensive.c do_kick() lines 1055-1150
# ---------------------------------------------------------------------------

def do_kick(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Kick attack.

    Ported from ACMD(do_kick) in act.offensive.c.
    """
    argument = argument.strip()

    if not argument:
        vict = _fighting(ch)
        if vict is None:
            _send(desc, "Calciare chi?\r\n")
            return
    else:
        vict = get_char_room_vis(ch, argument, world)
        if vict is None:
            _send(desc, "Non sembra essere qui.\r\n")
            return

    if vict is ch:
        _send(desc, "Non essere così masochista...\r\n")
        return

    # Simple kick: damage based on level
    dam = random.randint(1, ch.player.level // 2 + 1)

    # Dexterity check for hit/miss
    if random.randint(1, 100) > (50 + ch.aff_abils.dex * 2):
        dam = 0

    damage(ch, vict, dam, SKILL_KICK, world)


# ---------------------------------------------------------------------------
# do_bash (spingi / sfondata)
# Ported from act.offensive.c do_bash() lines 735-978
# ---------------------------------------------------------------------------

def do_bash(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Bash attack -- attempt to knock opponent down.

    Ported from ACMD(do_bash) in act.offensive.c. Simplified.
    """
    argument = argument.strip()

    if not argument:
        vict = _fighting(ch)
        if vict is None:
            _send(desc, "Chi vuoi spingere?\r\n")
            return
    else:
        vict = get_char_room_vis(ch, argument, world)
        if vict is None:
            _send(desc, "Non sembra essere qui.\r\n")
            return

    if vict is ch:
        _send(desc, "Non puoi sbattere te stesso...\r\n")
        return

    # Need a shield or be a warrior-type
    has_shield = (ch.equipment[WearPosition.WEAR_SHIELD] is not None)

    # Success probability based on strength and dexterity
    prob = 50 + (ch.aff_abils.str - vict.aff_abils.dex) * 3
    if has_shield:
        prob += 15

    if random.randint(1, 100) <= prob:
        # Success: knock them down
        dam = random.randint(1, ch.aff_abils.str)
        vict.position = Position.POS_SITTING
        _send_to_char(
            ch,
            f"Spingi {vict.player.name} facendolo cadere a terra!\r\n",
        )
        _send_to_char(
            vict,
            f"{ch.player.name} ti spinge facendoti cadere a terra!\r\n",
        )
        _act_to_room(
            ch, vict,
            "$n spinge $N facendolo cadere a terra!",
            world,
        )
        damage(ch, vict, dam, SKILL_BASH, world)
    else:
        # Failure: you fall
        ch.position = Position.POS_SITTING
        _send(desc, "Manchi e finisci per terra!\r\n")
        _act_to_room(
            ch, vict,
            "$n manca $N e finisce a terra!",
            world,
        )
        damage(vict, ch, 0, SKILL_BASH, world)


# ---------------------------------------------------------------------------
# do_backstab (pugnala)
# Ported from act.offensive.c do_backstab() lines 263-420
# ---------------------------------------------------------------------------

def do_backstab(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Backstab attack (rogue skill).

    Ported from ACMD(do_backstab) in act.offensive.c.
    """
    argument = argument.strip()

    if not argument:
        _send(desc, "Chi vuoi colpire alle spalle?\r\n")
        return

    vict = get_char_room_vis(ch, argument, world)
    if vict is None:
        _send(desc, "Chi vuoi colpire alle spalle?\r\n")
        return

    if vict is ch:
        _send(desc, "Come puoi farlo su te stesso?\r\n")
        return

    if ch.equipment[WearPosition.WEAR_WIELD] is None:
        _send(desc, "Devi avere un'arma impugnata per poterlo fare.\r\n")
        return

    if _fighting(vict) is not None:
        _send(
            desc,
            "Non puoi farlo su una persona che sta combattendo"
            "-- e' troppo allertato!\r\n",
        )
        return

    # Backstab attempt
    hit(ch, vict, SKILL_BACKSTAB, world)


# ---------------------------------------------------------------------------
# do_rescue (salva)
# Ported from act.offensive.c do_rescue() lines 979-1054
# ---------------------------------------------------------------------------

def do_rescue(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Rescue an ally from combat.

    Ported from ACMD(do_rescue) in act.offensive.c.
    """
    argument = argument.strip()

    if not argument:
        _send(desc, "Chi vuoi salvare?\r\n")
        return

    vict = get_char_room_vis(ch, argument, world)
    if vict is None:
        _send(desc, "Non sembra essere qui.\r\n")
        return

    if vict is ch:
        _send(desc, "Che idea... salva te stesso!\r\n")
        return

    if _fighting(ch) is vict:
        _send(desc, "Come puoi salvare qualcuno che stai combattendo?\r\n")
        return

    # Find who is fighting vict
    if ch.in_room not in world.rooms:
        return

    room = world.rooms[ch.in_room]
    attacker = None
    for other in room._characters:
        if _fighting(other) is vict and other is not ch:
            attacker = other
            break

    if attacker is None:
        _send(desc, "Ma nessuno lo sta combattendo!\r\n")
        return

    # Success check
    if random.randint(1, 100) > (50 + ch.player.level - attacker.player.level):
        _send(desc, "Non riesci a salvarlo!\r\n")
        return

    _send(desc, f"Salvi {vict.player.name} coraggiosamente!\r\n")
    _send_to_char(
        vict,
        f"{ch.player.name} ti salva coraggiosamente!\r\n",
    )
    _act_to_room(
        ch, vict,
        "$n salva coraggiosamente $N!",
        world,
    )

    # Redirect combat
    if _fighting(vict) is attacker:
        stop_fighting(vict)
    stop_fighting(attacker)
    set_fighting(attacker, ch)
    if _fighting(ch) is None:
        set_fighting(ch, attacker)


# ---------------------------------------------------------------------------
# do_assist (assisti)
# Ported from act.offensive.c do_assist() lines 59-145
# ---------------------------------------------------------------------------

def do_assist(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Join combat helping an ally.

    Ported from ACMD(do_assist) in act.offensive.c.
    """
    if _fighting(ch) is not None:
        _send(
            desc,
            "Stai gia' combattendo! Come puoi aiutare qualcun altro?\r\n",
        )
        return

    argument = argument.strip()

    if not argument:
        _send(desc, "Chi desideri aiutare?\r\n")
        return

    helpee = get_char_room_vis(ch, argument, world)
    if helpee is None:
        _send(desc, "Non sembra essere qui.\r\n")
        return

    if helpee is ch:
        _send(desc, "Non puoi aiutarti piu' di cosi'!!\r\n")
        return

    # Find who is fighting helpee
    if ch.in_room not in world.rooms:
        return
    room = world.rooms[ch.in_room]

    opponent = None
    for other in room._characters:
        if _fighting(other) is helpee:
            opponent = other
            break

    if opponent is None:
        _send(desc, "Ma nessuno lo sta combattendo!\r\n")
        return

    _send(desc, "Ti unisci al combattimento!\r\n")
    _send_to_char(
        helpee,
        f"{ch.player.name} si schiera dalla tua parte!\r\n",
    )
    _act_to_room(
        ch, helpee,
        "$n si schiera dalla parte di $N.",
        world,
    )
    hit(ch, opponent, TYPE_UNDEFINED, world)


# ---------------------------------------------------------------------------
# do_disarm
# Ported from act.offensive.c do_disarm() lines 1358+
# ---------------------------------------------------------------------------

def do_disarm(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Attempt to disarm an opponent.

    Ported from ACMD(do_disarm) in act.offensive.c. Simplified.
    """
    vict = _fighting(ch)
    if vict is None:
        _send(desc, "Non stai combattendo nessuno!\r\n")
        return

    if vict.equipment[WearPosition.WEAR_WIELD] is None:
        _send(desc, "Il tuo avversario non ha un'arma da disarmare!\r\n")
        return

    # Probability: dex + level based
    prob = (ch.aff_abils.dex * 2
            + ch.player.level
            - vict.aff_abils.dex * 2
            - vict.player.level)
    prob = max(5, min(95, 40 + prob))

    if random.randint(1, 100) <= prob:
        # Success: unequip weapon, drop to room
        from dalila.engine.handler import unequip_char, obj_to_room
        weapon = unequip_char(vict, WearPosition.WEAR_WIELD)
        if weapon is not None:
            obj_to_room(weapon, vict.in_room, world)
            _send(desc, f"Disarmi {vict.player.name}!\r\n")
            _send_to_char(
                vict,
                f"{ch.player.name} ti disarma! La tua arma cade a terra!\r\n",
            )
            _act_to_room(
                ch, vict,
                "$n disarma $N! L'arma cade a terra!",
                world,
            )
    else:
        _send(desc, "Non riesci a disarmare il tuo avversario.\r\n")
