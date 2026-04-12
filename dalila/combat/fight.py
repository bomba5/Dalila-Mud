"""Core combat engine.

Ported from fight.c: set_fighting, stop_fighting, hit, damage, damage_nuovo,
perform_violence, death_cry, raw_kill, die, solo_gain, group_gain,
update_pos, change_fama, change_notorieta, critical_hit.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING

from dalila.constants import (
    HIT_DEAD,
    HIT_INCAP,
    HIT_MORTALLYW,
    LVL_IMMORT,
    NOWHERE,
    NUM_OF_DIRS,
    AffectedBy,
    BodyLocation,
    DamageType,
    ItemType,
    MobFlag,
    NotorietaCase,
    Position,
    WearPosition,
)
from dalila.systems.classes import (
    ATTACK_HIT_TEXT,
    SKILL_BACKSTAB,
    SECOND_BACKSTAB,
    SECOND_WEAPON,
    TYPE_HIT,
    TYPE_HUNGER,
    THACO,
    STR_APP,
    DEX_APP,
    backstab_mult,
    get_str_app,
    get_dex_app,
    is_weapon_type,
    level_exp,
    strength_apply_index,
)

if TYPE_CHECKING:
    from dalila.engine.game_loop import GameWorld, LiveRoom
    from dalila.models.character import CharData
    from dalila.net.descriptor import Descriptor

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Combat list: characters currently in combat
# ---------------------------------------------------------------------------

combat_list: list[CharData] = []


# ---------------------------------------------------------------------------
# Damage message table (Italian)
# Ported from dam_weapons[] in fight.c
# ---------------------------------------------------------------------------

DAM_MESSAGES: list[tuple[str, str, str]] = [
    # (to_room, to_char, to_victim)
    (
        "$n tenta di colpire $N, ma fallisce.",
        "Tenti di colpire $N, ma fallisci.",
        "$n tenta di colpirti, ma fallisce.",
    ),
    (
        "$n sfiora $N con il suo colpo.",
        "Sfiori $N con il tuo colpo.",
        "$n ti sfiora con il suo colpo.",
    ),
    (
        "$n colpisce $N di striscio.",
        "Colpisci $N di striscio.",
        "$n ti colpisce di striscio.",
    ),
    (
        "$n colpisce $N.",
        "Colpisci $N.",
        "$n ti colpisce.",
    ),
    (
        "$n colpisce duramente $N.",
        "Colpisci duramente $N.",
        "$n ti colpisce duramente.",
    ),
    (
        "$n colpisce molto duramente $N.",
        "Colpisci molto duramente $N.",
        "$n ti colpisce molto duramente.",
    ),
    (
        "$n colpisce $N con violenza.",
        "Colpisci $N con violenza.",
        "$n ti colpisce con violenza.",
    ),
    (
        "$n colpisce brutalmente $N.",
        "Colpisci brutalmente $N.",
        "$n ti colpisce brutalmente.",
    ),
    (
        "$n colpisce e mutila $N.",
        "Colpisci e mutili $N.",
        "$n ti colpisce e ti mutila.",
    ),
    (
        "$n mutila $N ripetutamente e con rabbia.",
        "Mutili $N ripetutamente e con rabbia.",
        "$n ti mutila ripetutamente e con rabbia.",
    ),
    (
        "$n devasta $N.",
        "Il tuo colpo devasta totalmente $N.",
        "$n ti devasta.",
    ),
    (
        "$n decima $N con ferocia.",
        "Decimi $N con ferocia.",
        "$n ti decima con ferocia.",
    ),
    (
        "$n massacra $N riducendolo in piccoli pezzi sanguinolenti.",
        "Massacri $N riducendolo in piccoli pezzi sanguinolenti.",
        "$n ti massacra riducendoti in piccoli pezzi sanguinolenti.",
    ),
    (
        "$n DEMOLISCE $N.",
        "Il tuo colpo DEMOLISCE $N.",
        "$n ti DEMOLISCE.",
    ),
    (
        "$n ANNICHILISCE $N.",
        "Il tuo colpo ANNICHILISCE $N.",
        "$n ti ANNICHILISCE.",
    ),
]


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _is_npc(ch: CharData) -> bool:
    """Check if a character is an NPC."""
    return ch.nr >= 0


def _fighting(ch: CharData) -> CharData | None:
    """Get the character ch is fighting, if any."""
    return getattr(ch, "_fighting", None)


def _set_fighting_target(ch: CharData, vict: CharData | None) -> None:
    """Internal: set ch's fighting target pointer."""
    ch._fighting = vict  # type: ignore[attr-defined]


def _send(desc, text: str) -> None:
    """Fire-and-forget send to a descriptor."""
    if desc is not None:
        asyncio.ensure_future(desc.send(text))


def _send_to_char(ch: CharData, text: str) -> None:
    """Send text to a character."""
    _send(ch.desc, text)


def _send_to_room(ch: CharData, text: str, world: GameWorld) -> None:
    """Send text to everyone in the room except ch."""
    if ch.in_room == NOWHERE or ch.in_room not in world.rooms:
        return
    room = world.rooms[ch.in_room]
    for other in room._characters:
        if other is not ch and other.desc:
            _send(other.desc, text)


def _act_to_room(
    ch: CharData, vict: CharData | None, text: str, world: GameWorld,
) -> None:
    """Send act-style text to the room, replacing $n and $N."""
    ch_name = ch.player.name
    vict_name = vict.player.name if vict else "qualcuno"
    formatted = text.replace("$n", ch_name).replace("$N", vict_name)
    if ch.in_room == NOWHERE or ch.in_room not in world.rooms:
        return
    room = world.rooms[ch.in_room]
    for other in room._characters:
        if other is not ch and other is not vict and other.desc:
            _send(other.desc, formatted + "\r\n")


# ---------------------------------------------------------------------------
# set_fighting / stop_fighting
# Ported from fight.c lines 576-613
# ---------------------------------------------------------------------------

def set_fighting(ch: CharData, vict: CharData) -> None:
    """Enter combat: add ch to combat list, set fighting target.

    Ported from set_fighting() in fight.c.
    """
    if ch is vict:
        return

    if _fighting(ch) is not None:
        return  # Already fighting

    if ch not in combat_list:
        combat_list.append(ch)

    _set_fighting_target(ch, vict)
    ch.position = Position.POS_FIGHTING


def stop_fighting(ch: CharData) -> None:
    """Leave combat: remove from combat list, clear fighting target.

    Ported from stop_fighting() in fight.c.
    """
    if ch in combat_list:
        combat_list.remove(ch)

    _set_fighting_target(ch, None)
    ch.position = Position.POS_STANDING
    update_pos(ch)


# ---------------------------------------------------------------------------
# update_pos
# Ported from fight.c lines 263-309
# ---------------------------------------------------------------------------

def update_pos(victim: CharData) -> None:
    """Update a character's position based on HP.

    Ported from update_pos() in fight.c.
    """
    hp = victim.points.hit

    if hp > 0 and victim.position > Position.POS_STUNNED:
        return
    elif hp > 0:
        victim.position = Position.POS_STANDING
    elif hp <= HIT_DEAD:
        victim.position = Position.POS_DEAD
    elif hp <= HIT_MORTALLYW:
        victim.position = Position.POS_MORTALLYW
    elif hp <= HIT_INCAP:
        victim.position = Position.POS_INCAP
    else:
        victim.position = Position.POS_STUNNED


# ---------------------------------------------------------------------------
# change_fama / change_notorieta
# Ported from fight.c lines 311-410
# ---------------------------------------------------------------------------

def change_fama(ch: CharData, victim: CharData, amount: int) -> None:
    """Update fama (reputation) for PvP combat.

    Ported from change_fama() in fight.c.
    """
    if ch is None or victim is None:
        return
    if _is_npc(ch) or _is_npc(victim):
        return

    diff = ch.player.level - victim.player.level
    if diff <= -15:
        fama = 20
    elif diff <= -10:
        fama = 10
    elif diff <= -5:
        fama = 5
    elif diff < 0:
        fama = 2
    elif diff < 5:
        fama = 0
    elif diff < 10:
        fama = -1
    else:
        fama = -2

    ch.points.fama = max(1, min(ch.points.fama + fama, 1000))
    victim.points.fama = max(1, min(victim.points.fama - fama, 1000))


def change_notorieta(
    ch: CharData, victim: CharData | None, event: int, amount: int,
) -> None:
    """Update notorieta based on an event.

    Ported from change_notorieta() in fight.c.
    Simplified: clan crime checks are omitted until clan system is ported.
    """
    if ch is None or _is_npc(ch):
        return

    match event:
        case NotorietaCase.KILL:
            if victim and not _is_npc(victim):
                amount = -25
            else:
                amount = 0
        case NotorietaCase.TKILL:
            if victim and not _is_npc(victim):
                amount = -5
            else:
                amount = 0
        case NotorietaCase.WKILL:
            if victim and not _is_npc(victim):
                amount = -5
            else:
                amount = 0
        case NotorietaCase.THIEF:
            amount = -(amount // 100)
        case NotorietaCase.WANTED:
            if victim:
                amount -= victim.player.level // 4
        case _:
            pass

    ch.points.notorieta = max(1, min(ch.points.notorieta + amount, 1000))


# ---------------------------------------------------------------------------
# death_cry
# Ported from fight.c lines 1055-1069
# ---------------------------------------------------------------------------

def death_cry(ch: CharData, world: GameWorld) -> None:
    """Send death cry to room and adjacent rooms.

    Ported from death_cry() in fight.c.
    """
    ch_name = ch.player.name
    msg = (
        f"Ti si gela il sangue quando senti il grido di morte di {ch_name}."
    )
    _send_to_room(ch, msg + "\r\n", world)

    # Send to adjacent rooms
    if ch.in_room == NOWHERE or ch.in_room not in world.rooms:
        return
    room = world.rooms[ch.in_room]
    for door in range(NUM_OF_DIRS):
        if (room.data.dir_option
                and door < len(room.data.dir_option)
                and room.data.dir_option[door] is not None):
            target_vnum = room.data.dir_option[door].to_room
            if target_vnum != NOWHERE and target_vnum in world.rooms:
                target = world.rooms[target_vnum]
                for other in target._characters:
                    if other.desc:
                        _send(
                            other.desc,
                            "Ti si gela il sangue quando senti uno "
                            "straziante grido di morte.\r\n",
                        )


# ---------------------------------------------------------------------------
# raw_kill / die
# Ported from fight.c lines 1071-1228
# ---------------------------------------------------------------------------

def raw_kill(ch: CharData, killer: CharData | None, world: GameWorld) -> None:
    """Kill a character: stop combat, remove affects, extract.

    Ported from raw_kill() in fight.c. Simplified for Phase 3:
    no corpse creation yet, no mail to mob master.
    """
    from dalila.engine.handler import char_from_room

    if _fighting(ch) is not None:
        stop_fighting(ch)

    # Clear all affects
    ch.affected.clear()

    death_cry(ch, world)

    # For NPCs: just remove from the room
    # For PCs: set ghost mode, move to start room
    if _is_npc(ch):
        # Remove mob from room
        char_from_room(ch, world)
        # Remove from players list if somehow there
        if ch in world.players:
            world.players.remove(ch)
        # Remove from any room character lists
    else:
        # PC death: set hit points to 1, move to start room
        ch.points.hit = max(1, ch.points.max_hit)
        ch.points.mana = ch.points.max_mana
        ch.points.move = ch.points.max_move
        ch.position = Position.POS_STANDING
        ch.points.hitroll = 0
        ch.points.damroll = 0

        # Move to mortal start room
        char_from_room(ch, world)
        from dalila.engine.handler import char_to_room
        start = world.mortal_start_room
        char_to_room(ch, start, world)

        _send_to_char(
            ch,
            "\r\n&1Sei morto!&0\r\n"
            "Ti risvegli nella tua citta' natale...\r\n\r\n",
        )


def die(ch: CharData, killer: CharData | None, world: GameWorld) -> None:
    """Handle character death: exp loss, fama, then raw_kill.

    Ported from die() in fight.c. Simplified for Phase 3.
    """
    if not _is_npc(ch) and killer:
        change_fama(killer, ch, 0)

    raw_kill(ch, killer, world)


# ---------------------------------------------------------------------------
# Experience gain
# Ported from solo_gain() and perform_group_gain() in fight.c
# ---------------------------------------------------------------------------

def solo_gain(ch: CharData, victim: CharData) -> int:
    """Calculate and award solo experience.

    Ported from solo_gain() in fight.c. Simplified.
    """
    from dalila.engine.limits import gain_exp

    level = ch.player.level
    # Base XP: fraction of XP needed to next level
    next_exp = level_exp(ch.player.class_, min(level + 1, 91))
    curr_exp = level_exp(ch.player.class_, level)
    base = next_exp - curr_exp

    # Level-dependent fraction
    if level <= 5:
        exp = int(base * 0.025)
    elif level <= 10:
        exp = int(base * 0.0225)
    elif level <= 15:
        exp = int(base * 0.02)
    elif level <= 20:
        exp = int(base * 0.015)
    elif level <= 30:
        exp = int(base * 0.0125)
    elif level <= 40:
        exp = int(base * 0.01)
    elif level <= 45:
        exp = int(base * 0.0075)
    elif level <= 50:
        exp = int(base * 0.005)
    elif level <= 55:
        exp = int(base * 0.0025)
    elif level <= 60:
        exp = int(base * 0.0015)
    else:
        exp = int(base * 0.001)

    # Victim level ratio scaling
    if victim.player.level > 0 and level > 0:
        ratio = victim.player.level / level
        if ratio > 1.3:
            exp = int(exp * (1.3 ** 4))
        elif ratio >= 1.0:
            exp = int(exp * (ratio ** 4))
        else:
            exp = int(exp * (ratio ** 3))

    exp = max(1, min(exp, 100000))  # max_exp_solo_gain

    gained = gain_exp(ch, exp)

    if gained > 0:
        if gained == 1:
            _send_to_char(ch, "Guadagni un solo miserabile XP.\r\n")
        else:
            _send_to_char(ch, f"Guadagni {gained} XP.\r\n")

    return gained


# ---------------------------------------------------------------------------
# dam_message
# Ported from dam_message() in fight.c
# ---------------------------------------------------------------------------

def get_dam_msg_index(dam: int) -> int:
    """Map damage amount to message index.

    Ported from dam_message() in fight.c.
    """
    if dam == 0:
        return 0
    if dam <= 2:
        return 1
    if dam <= 4:
        return 2
    if dam <= 6:
        return 3
    if dam <= 10:
        return 4
    if dam <= 14:
        return 5
    if dam <= 19:
        return 6
    if dam <= 23:
        return 7
    if dam <= 28:
        return 8
    if dam <= 32:
        return 9
    if dam <= 36:
        return 10
    if dam <= 44:
        return 11
    if dam <= 50:
        return 12
    if dam <= 100:
        return 13
    return 14


def dam_message(
    dam: int, ch: CharData, victim: CharData, w_type: int,
    world: GameWorld,
) -> None:
    """Send damage messages to combatants and room.

    Ported from dam_message() in fight.c.
    """
    idx = min(get_dam_msg_index(dam), len(DAM_MESSAGES) - 1)
    to_room, to_char, to_vict = DAM_MESSAGES[idx]

    ch_name = ch.player.name
    vict_name = victim.player.name

    # Send to char
    msg = to_char.replace("$N", vict_name)
    _send_to_char(ch, msg + "\r\n")

    # Send to victim
    msg = to_vict.replace("$n", ch_name)
    _send_to_char(victim, msg + "\r\n")

    # Send to room
    _act_to_room(ch, victim, to_room, world)


# ---------------------------------------------------------------------------
# damage / damage_nuovo
# Ported from fight.c lines 1710-1960, 2154-2157
# ---------------------------------------------------------------------------

def damage(
    ch: CharData, victim: CharData, dam: int, attacktype: int,
    world: GameWorld,
    *,
    maxato: bool = True,
    tipo: int = DamageType.DANNO_FISICO,
) -> None:
    """Apply damage to a victim.

    Ported from damage_nuovo() in fight.c.
    """
    if victim is None:
        return

    if victim.points.hit <= HIT_DEAD:
        die(victim, ch, world)
        return

    # Immortals cannot be damaged
    if not _is_npc(victim) and victim.player.level >= LVL_IMMORT:
        return

    # Start attacker fighting victim
    if victim is not ch:
        if (ch.position > Position.POS_STUNNED
                and _fighting(ch) is None):
            set_fighting(ch, victim)
        if (victim.position > Position.POS_STUNNED
                and _fighting(victim) is None):
            set_fighting(victim, ch)

    # Sanctuary halves damage
    if (victim.char_specials_saved.affected_by[0]
            & AffectedBy.AFF_SANCTUARY) and dam >= 2:
        dam = dam // 2

    # Resistance calculations (by Spini)
    res = victim.resistenze
    match tipo:
        case DamageType.DANNO_FUOCO:
            r = max(0, min(100, res.res_fuoco))
            dam = int(dam * (1 - r / 100))
        case DamageType.DANNO_GHIACCIO:
            r = max(0, min(100, res.res_ghiaccio))
            dam = int(dam * (1 - r / 100))
        case DamageType.DANNO_ELETTRICITA:
            r = max(0, min(100, res.res_elettricita))
            dam = int(dam * (1 - r / 100))
        case DamageType.DANNO_ACIDO:
            r = max(0, min(100, res.res_acido))
            dam = int(dam * (1 - r / 100))
        case DamageType.DANNO_SHAARR:
            r = max(0, min(100, res.res_shaarr))
            dam = int(dam * (1 - r * 3.0 / 400))
        case DamageType.DANNO_XHYPHYS:
            r = max(0, min(100, res.res_xhyphys))
            dam = int(dam * (1 - r * 3.0 / 400))
        case DamageType.DANNO_THERION:
            r = max(0, min(100, res.res_therion))
            dam = int(dam * (1 - r * 3.0 / 400))
        case DamageType.DANNO_SILUE:
            r = max(0, min(100, res.res_silue))
            dam = int(dam * (1 - r * 3.0 / 400))
        case DamageType.DANNO_FISICO:
            r = max(0, min(100, res.res_fisico))
            dam = int(dam * (1 - r / 300))

    # Cap damage
    if maxato:
        dam = min(dam, 200)
    dam = max(dam, 0)

    # Apply damage
    victim.points.hit -= dam
    update_pos(victim)

    # Send damage messages
    dam_message(dam, ch, victim, attacktype, world)

    # Check death
    if victim.position == Position.POS_DEAD:
        if not _is_npc(ch) and _is_npc(victim):
            # Award experience
            solo_gain(ch, victim)

        _act_to_room(
            ch, victim,
            "$N e' morto! R.I.P.",
            world,
        )
        _send_to_char(victim, "Sei morto! Mi dispiace...\r\n")
        _send_to_char(ch, f"Hai ucciso {victim.player.name}!\r\n")

        die(victim, ch, world)
        return

    # Position-based messages
    match victim.position:
        case Position.POS_MORTALLYW:
            _send_to_char(
                victim,
                "Sei ferito mortalmente, e morirai presto "
                "se non verrai curato!\r\n",
            )
            _act_to_room(
                ch, victim,
                "$N e' ferito mortalmente e agonizza a terra.",
                world,
            )
        case Position.POS_INCAP:
            _send_to_char(
                victim,
                "Sei incapacitato e morirai lentamente "
                "se non verrai curato.\r\n",
            )
            _act_to_room(
                ch, victim,
                "$N e' incapacitato e giace a terra.",
                world,
            )
        case Position.POS_STUNNED:
            _send_to_char(
                victim,
                "Sei stordito, ma probabilmente riprenderai "
                "conoscenza.\r\n",
            )
            _act_to_room(
                ch, victim,
                "$N e' stordito, ma probabilmente riprendera' "
                "conoscenza.",
                world,
            )


# ---------------------------------------------------------------------------
# hit()
# Ported from fight.c lines 2769-3000
# ---------------------------------------------------------------------------

def hit(
    ch: CharData, victim: CharData, type_: int, world: GameWorld,
) -> None:
    """Execute a single attack roll against victim.

    Ported from hit() in fight.c.
    """
    from dalila.models.object import ObjData

    if victim is None:
        stop_fighting(ch)
        return

    if ch.in_room != victim.in_room:
        if _fighting(ch) is not None and _fighting(ch) is victim:
            stop_fighting(ch)
        return

    # Paralyzed/stunned/sleeping characters can't attack
    aff = ch.char_specials_saved.affected_by[0]
    if (aff & AffectedBy.AFF_PARALIZE
            or aff & AffectedBy.AFF_TRAMORTITO
            or aff & AffectedBy.AFF_SLEEP):
        if _fighting(ch) is not None:
            stop_fighting(ch)
        return

    # Determine wielded weapon
    r_wielded = ch.equipment[WearPosition.WEAR_WIELD]
    l_wielded = ch.equipment[WearPosition.WEAR_WIELD_L] if len(ch.equipment) > WearPosition.WEAR_WIELD_L else None

    if type_ in (SECOND_WEAPON, SECOND_BACKSTAB):
        wielded = l_wielded
    else:
        wielded = r_wielded

    # Find weapon type for display
    if (wielded is not None
            and isinstance(wielded, ObjData)
            and wielded.obj_flags.type_flag in (
                ItemType.ITEM_WEAPON, 92)):  # ITEM_WEAPON_2HANDS=92
        w_type = wielded.obj_flags.value[3] + TYPE_HIT
    else:
        if _is_npc(ch) and ch.mob_specials.attack_type != 0:
            w_type = ch.mob_specials.attack_type + TYPE_HIT
        else:
            w_type = TYPE_HIT

    # Calculate THAC0
    if not _is_npc(ch):
        class_ = max(0, min(ch.player.class_, 5))
        level = max(0, min(ch.player.level, 91))
        calc_thaco = THACO[class_][level]
    else:
        calc_thaco = 20

    # Strength bonus to hit
    str_idx = strength_apply_index(ch)
    calc_thaco -= STR_APP[str_idx].tohit

    # Hitroll bonus
    calc_thaco -= ch.points.hitroll

    # Intelligence + Wisdom bonus
    calc_thaco -= (ch.aff_abils.intel + ch.aff_abils.wis - 26) // 3

    # Calculate victim AC
    victim_ac = victim.points.armor // 10
    if victim.position > Position.POS_SLEEPING:
        victim_ac = max(-10, victim_ac)

    dex_val = max(0, min(victim.aff_abils.dex, 25))
    victim_ac += DEX_APP[dex_val].defensive

    # Roll the die
    diceroll = random.randint(1, 20)

    # Hit or miss?
    if ((diceroll < 20 and victim.position > Position.POS_SLEEPING)
            and (diceroll == 1 or (calc_thaco - diceroll) > victim_ac)):
        # MISS
        if type_ in (SKILL_BACKSTAB, SECOND_BACKSTAB):
            damage(ch, victim, 0, SKILL_BACKSTAB, world)
        else:
            damage(ch, victim, 0, w_type, world)
    else:
        # HIT -- calculate damage
        dam = STR_APP[str_idx].todam
        dam += ch.points.damroll

        if wielded is not None and isinstance(wielded, ObjData):
            # Weapon damage dice
            ndice = wielded.obj_flags.value[1]
            sdice = wielded.obj_flags.value[2]
            if ndice > 0 and sdice > 0:
                dam += sum(random.randint(1, sdice) for _ in range(ndice))
        else:
            # Bare hands
            if _is_npc(ch):
                ndice = ch.mob_specials.damnodice
                sdice = ch.mob_specials.damsizedice
                if ndice > 0 and sdice > 0:
                    dam += sum(
                        random.randint(1, sdice) for _ in range(ndice)
                    )
            else:
                dam += random.randint(0, 2)

        # Position multiplier
        if victim.position < Position.POS_FIGHTING:
            multiplier = 1 + (Position.POS_FIGHTING - victim.position) / 3
            dam = int(dam * multiplier)

        # Minimum 1 damage
        dam = max(1, dam)

        # Backstab multiplier
        if type_ in (SKILL_BACKSTAB, SECOND_BACKSTAB):
            dam *= backstab_mult(ch.player.level)
            if type_ == SECOND_BACKSTAB:
                dam = min(dam, random.randint(50, 150))
            damage(ch, victim, dam, SKILL_BACKSTAB, world)
        else:
            damage(ch, victim, dam, w_type, world)

    # Critical hit on natural 20
    if diceroll == 20:
        if not _is_npc(ch):
            critical_hit(ch, victim, BodyLocation.LOCATION_RANDOM, world)
        else:
            if random.randint(1, 100) < 20:
                if random.randint(1, 100) < ch.player.level:
                    critical_hit(
                        ch, victim, BodyLocation.LOCATION_RANDOM, world,
                    )


# ---------------------------------------------------------------------------
# critical_hit
# Ported from fight.c lines 2160-2768 (simplified)
# ---------------------------------------------------------------------------

def critical_hit(
    ch: CharData, victim: CharData, location: int, world: GameWorld,
) -> None:
    """Apply a critical hit with body location effects.

    Ported from critical_hit() in fight.c. Simplified: sends messages
    but doesn't apply the full wound flag system (which requires the
    4-bank bitvector affect management from Phase 4+).
    """
    if victim.position < Position.POS_SITTING:
        return

    if location == BodyLocation.LOCATION_RANDOM:
        location = random.randint(1, 6)

    severity = random.randint(1, 8)

    ch_name = ch.player.name
    vict_name = victim.player.name

    match location:
        case BodyLocation.LOCATION_TESTA:
            if severity <= 2:
                _send_to_char(
                    ch,
                    f"&8&3Colpisci {vict_name} alla testa, "
                    f"ma non sembra subire gravi conseguenze.&0\r\n",
                )
                _send_to_char(
                    victim,
                    f"&8&3{ch_name} ti colpisce alla testa... "
                    f"per questa volta sembra esserti andata bene.&0\r\n",
                )
            else:
                _send_to_char(
                    ch,
                    f"&8&2Colpisci {vict_name} alla testa, "
                    f"rimane leggermente intontito.&0\r\n",
                )
                _send_to_char(
                    victim,
                    f"&8&5{ch_name} ti colpisce alla testa... "
                    f"rimani intontito per un po'.&0\r\n",
                )
        case BodyLocation.LOCATION_BRACCIO_D:
            _send_to_char(
                ch,
                f"&8&2Colpisci il braccio destro di {vict_name}.&0\r\n",
            )
            _send_to_char(
                victim,
                f"&8&5{ch_name} ti colpisce al braccio destro.&0\r\n",
            )
        case BodyLocation.LOCATION_BRACCIO_S:
            _send_to_char(
                ch,
                f"&8&2Colpisci il braccio sinistro di {vict_name}.&0\r\n",
            )
            _send_to_char(
                victim,
                f"&8&5{ch_name} ti colpisce al braccio sinistro.&0\r\n",
            )
        case BodyLocation.LOCATION_TORSO:
            _send_to_char(
                ch,
                f"&8&2Colpisci {vict_name} all'addome.&0\r\n",
            )
            _send_to_char(
                victim,
                f"&8&5{ch_name} ti colpisce all'addome.&0\r\n",
            )
        case BodyLocation.LOCATION_GAMBA_D:
            _send_to_char(
                ch,
                f"&8&2Colpisci la gamba destra di {vict_name}.&0\r\n",
            )
            _send_to_char(
                victim,
                f"&8&5{ch_name} ti colpisce alla gamba destra.&0\r\n",
            )
        case BodyLocation.LOCATION_GAMBA_S:
            _send_to_char(
                ch,
                f"&8&2Colpisci la gamba sinistra di {vict_name}.&0\r\n",
            )
            _send_to_char(
                victim,
                f"&8&5{ch_name} ti colpisce alla gamba sinistra.&0\r\n",
            )


# ---------------------------------------------------------------------------
# perform_violence
# Ported from fight.c lines 3056-3256
# ---------------------------------------------------------------------------

def perform_violence(world: GameWorld) -> None:
    """Process one round of combat for all fighting characters.

    Called every PULSE_VIOLENCE (3 seconds) from the game loop.
    Ported from perform_violence() in fight.c.
    """
    # Iterate a copy because combat_list may change during iteration
    for ch in list(combat_list):
        victim = _fighting(ch)
        if victim is None:
            stop_fighting(ch)
            continue

        # Check paralysis / stunned
        aff = ch.char_specials_saved.affected_by[0]
        if (aff & AffectedBy.AFF_PARALIZE
                or aff & AffectedBy.AFF_TRAMORTITO):
            continue

        # Determine number of attacks
        if _is_npc(ch):
            # NPC attack count based on level
            level = ch.player.level
            if level < 6:
                attacks = 1
            elif level < 10:
                attacks = random.randint(1, 2)
            elif level < 20:
                attacks = random.randint(1, 2)
            elif level < 30:
                attacks = random.randint(2, 3)
            elif level < 40:
                attacks = random.randint(2, 3)
            elif level < 50:
                attacks = random.randint(2, 4)
            elif level < 60:
                attacks = random.randint(2, 4)
            else:
                attacks = random.randint(3, 6)

            if ch.position == Position.POS_SITTING:
                attacks = 0
                ch.position = Position.POS_FIGHTING
                _act_to_room(
                    ch, None,
                    "$n si alza in piedi rapidamente!",
                    world,
                )
        else:
            # PC: base 1 attack, more with skills (simplified)
            attacks = 1

            if ch.position == Position.POS_SITTING:
                attacks = 0
                _send_to_char(
                    ch,
                    "&3&bNon puoi combattere da seduto!!&0\r\n",
                )
            elif ch.points.move < 1:
                _send_to_char(
                    ch,
                    "Sei esausto, non riesci a combattere, "
                    "cerchi invano di riprendere fiato.\r\n",
                )
                ch.points.move = 0

        # Execute attacks
        for _ in range(attacks):
            victim = _fighting(ch)
            if victim is None or ch.in_room != victim.in_room:
                stop_fighting(ch)
                break

            hit(ch, victim, -1, world)

            # Consume movement points for PCs
            if not _is_npc(ch) and ch.points.move > 0:
                ch.points.move -= 1
