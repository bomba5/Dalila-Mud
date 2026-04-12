"""Spell system: definitions, casting, effects.

Ported from spell_parser.c, spells.c, magic.c.
Spell definitions: spell info table, mana costs, targets, routines.
Spell effects: damage, healing, buffs/debuffs, group spells.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from dalila.constants import (
    LVL_IMMORT,
    NOWHERE,
    AffectedBy,
    DamageType,
    Position,
)
from dalila.models.common import AffectedType, Bitvector
from dalila.systems.classes import (
    MAX_SPELLS,
    SPELL_ARMOR,
    SPELL_BLESS,
    SPELL_BLINDNESS,
    SPELL_BURNING_HANDS,
    SPELL_CALL_LIGHTNING,
    SPELL_CHARM,
    SPELL_CHILL_TOUCH,
    SPELL_COLOR_SPRAY,
    SPELL_CURE_BLIND,
    SPELL_CURE_CRITIC,
    SPELL_CURE_LIGHT,
    SPELL_CURE_SERIOUS,
    SPELL_CURSE,
    SPELL_DETECT_ALIGN,
    SPELL_DETECT_INVIS,
    SPELL_DETECT_MAGIC,
    SPELL_DISPEL_EVIL,
    SPELL_DISPEL_GOOD,
    SPELL_EARTHQUAKE,
    SPELL_ENERGY_DRAIN,
    SPELL_FIREBALL,
    SPELL_GROUP_ARMOR,
    SPELL_GROUP_HEAL,
    SPELL_HARM,
    SPELL_HEAL,
    SPELL_INFRAVISION,
    SPELL_INVISIBLE,
    SPELL_LIGHTNING_BOLT,
    SPELL_MAGIC_MISSILE,
    SPELL_POISON,
    SPELL_PROT_FROM_EVIL,
    SPELL_REFRESH,
    SPELL_REMOVE_CURSE,
    SPELL_REMOVE_POISON,
    SPELL_SANCTUARY,
    SPELL_SENSE_LIFE,
    SPELL_SHIELD,
    SPELL_SHOCKING_GRASP,
    SPELL_SLEEP,
    SPELL_STRENGTH,
    SPELL_WATERWALK,
    SPELL_WORD_OF_RECALL,
    SPELL_AID,
    SPELL_ENDURANCE,
    SPELLSKILL,
    NUM_CLASSES,
    TYPE_UNDEFINED,
)

if TYPE_CHECKING:
    from dalila.engine.game_loop import GameWorld
    from dalila.models.character import CharData
    from dalila.net.descriptor import Descriptor

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Magic routine flags from spells.h
# ---------------------------------------------------------------------------

MAG_DAMAGE: int = 1 << 0
MAG_AFFECTS: int = 1 << 1
MAG_UNAFFECTS: int = 1 << 2
MAG_POINTS: int = 1 << 3
MAG_ALTER_OBJS: int = 1 << 4
MAG_GROUPS: int = 1 << 5
MAG_MASSES: int = 1 << 6
MAG_AREAS: int = 1 << 7
MAG_SUMMONS: int = 1 << 8
MAG_CREATIONS: int = 1 << 9
MAG_MANUAL: int = 1 << 10

# Target flags
TAR_IGNORE: int = 1
TAR_CHAR_ROOM: int = 2
TAR_CHAR_WORLD: int = 4
TAR_FIGHT_SELF: int = 8
TAR_FIGHT_VICT: int = 16
TAR_SELF_ONLY: int = 32
TAR_NOT_SELF: int = 64
TAR_OBJ_INV: int = 128
TAR_OBJ_ROOM: int = 256

# Cast types
CAST_SPELL: int = 0
CAST_POTION: int = 1
CAST_WAND: int = 2
CAST_STAFF: int = 3
CAST_SCROLL: int = 4


# ---------------------------------------------------------------------------
# Spell info table entry
# Ported from struct spell_info_type in spells.h
# ---------------------------------------------------------------------------

@dataclass
class SpellInfo:
    """Definition of a single spell/skill."""
    min_position: int = Position.POS_FIGHTING
    mana_min: int = 0       # Mana at highest level
    mana_max: int = 0       # Mana at lowest level
    mana_change: int = 0    # Mana decrease per level
    min_level: list[int] = field(
        default_factory=lambda: [LVL_IMMORT] * NUM_CLASSES,
    )
    routines: int = 0
    violent: bool = False
    targets: int = 0
    name: str = "unknown"


# ---------------------------------------------------------------------------
# Spell info table: spell_info[] equivalent
# ---------------------------------------------------------------------------

spell_info: dict[int, SpellInfo] = {}


def _spello(
    spl: int, name: str,
    max_mana: int, min_mana: int, mana_change: int,
    min_pos: int, targets: int, violent: bool,
    routines: int,
    min_levels: list[int] | None = None,
) -> None:
    """Register a spell in the spell_info table.

    Ported from spello() macro in spell_parser.c.
    """
    si = SpellInfo(
        name=name,
        min_position=min_pos,
        mana_min=min_mana,
        mana_max=max_mana,
        mana_change=mana_change,
        routines=routines,
        violent=violent,
        targets=targets,
    )
    if min_levels:
        si.min_level = min_levels + [LVL_IMMORT] * (NUM_CLASSES - len(min_levels))
    spell_info[spl] = si


def _init_spell_table() -> None:
    """Initialize the spell info table.

    Key spells from spell_parser.c init_spell_levels() + spello() calls.
    Min levels: [Pandion, Cyrinic, Alcione, Genidian, Peloi, Daresiano]
    """
    # Damage spells
    _spello(SPELL_MAGIC_MISSILE, "dardo magico",
            25, 10, 3, Position.POS_FIGHTING,
            TAR_CHAR_ROOM | TAR_FIGHT_VICT, True, MAG_DAMAGE,
            [1, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_BURNING_HANDS, "mani fiammeggianti",
            35, 15, 3, Position.POS_FIGHTING,
            TAR_CHAR_ROOM | TAR_FIGHT_VICT, True, MAG_DAMAGE,
            [5, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_SHOCKING_GRASP, "stretta folgorante",
            40, 20, 3, Position.POS_FIGHTING,
            TAR_CHAR_ROOM | TAR_FIGHT_VICT, True, MAG_DAMAGE,
            [7, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_COLOR_SPRAY, "ventaglio prismatico",
            50, 25, 3, Position.POS_FIGHTING,
            TAR_CHAR_ROOM | TAR_FIGHT_VICT, True, MAG_DAMAGE,
            [11, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_LIGHTNING_BOLT, "fulmine",
            60, 30, 3, Position.POS_FIGHTING,
            TAR_CHAR_ROOM | TAR_FIGHT_VICT, True, MAG_DAMAGE,
            [9, 15, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_FIREBALL, "palla di fuoco",
            80, 40, 3, Position.POS_FIGHTING,
            TAR_CHAR_ROOM | TAR_FIGHT_VICT, True, MAG_DAMAGE,
            [15, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_CALL_LIGHTNING, "invocazione del fulmine",
            60, 30, 3, Position.POS_FIGHTING,
            TAR_CHAR_ROOM | TAR_FIGHT_VICT, True, MAG_DAMAGE,
            [LVL_IMMORT, 12, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_EARTHQUAKE, "terremoto",
            60, 30, 3, Position.POS_FIGHTING,
            TAR_IGNORE, True, MAG_AREAS,
            [LVL_IMMORT, 12, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_HARM, "infliggi ferite",
            75, 40, 3, Position.POS_FIGHTING,
            TAR_CHAR_ROOM | TAR_FIGHT_VICT, True, MAG_DAMAGE,
            [LVL_IMMORT, 19, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_DISPEL_EVIL, "punisci il male",
            60, 30, 3, Position.POS_FIGHTING,
            TAR_CHAR_ROOM | TAR_FIGHT_VICT, True, MAG_DAMAGE,
            [LVL_IMMORT, 14, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_DISPEL_GOOD, "punisci il bene",
            60, 30, 3, Position.POS_FIGHTING,
            TAR_CHAR_ROOM | TAR_FIGHT_VICT, True, MAG_DAMAGE,
            [LVL_IMMORT, 14, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_ENERGY_DRAIN, "risucchio energetico",
            80, 40, 3, Position.POS_FIGHTING,
            TAR_CHAR_ROOM | TAR_FIGHT_VICT, True, MAG_DAMAGE | MAG_MANUAL,
            [25, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])

    # Healing spells
    _spello(SPELL_CURE_LIGHT, "cura leggera",
            30, 10, 2, Position.POS_FIGHTING,
            TAR_CHAR_ROOM, False, MAG_POINTS,
            [LVL_IMMORT, 1, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_CURE_SERIOUS, "cura seria",
            45, 20, 2, Position.POS_FIGHTING,
            TAR_CHAR_ROOM, False, MAG_POINTS,
            [LVL_IMMORT, 7, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_CURE_CRITIC, "cura critica",
            60, 30, 2, Position.POS_FIGHTING,
            TAR_CHAR_ROOM, False, MAG_POINTS,
            [LVL_IMMORT, 11, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_HEAL, "cura completa",
            100, 50, 3, Position.POS_FIGHTING,
            TAR_CHAR_ROOM, False, MAG_POINTS | MAG_UNAFFECTS,
            [LVL_IMMORT, 16, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_GROUP_HEAL, "cura di gruppo",
            150, 80, 5, Position.POS_FIGHTING,
            TAR_IGNORE, False, MAG_GROUPS,
            [LVL_IMMORT, 22, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_REFRESH, "ristoro",
            40, 20, 2, Position.POS_FIGHTING,
            TAR_CHAR_ROOM, False, MAG_POINTS,
            [LVL_IMMORT, 5, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])

    # Buff spells
    _spello(SPELL_ARMOR, "armatura magica",
            30, 15, 3, Position.POS_FIGHTING,
            TAR_CHAR_ROOM, False, MAG_AFFECTS,
            [4, 1, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_BLESS, "benedizione",
            35, 15, 3, Position.POS_STANDING,
            TAR_CHAR_ROOM | TAR_OBJ_INV, False, MAG_AFFECTS | MAG_ALTER_OBJS,
            [LVL_IMMORT, 5, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_STRENGTH, "forza",
            35, 20, 1, Position.POS_STANDING,
            TAR_CHAR_ROOM, False, MAG_AFFECTS,
            [6, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_INVISIBLE, "invisibilita'",
            35, 20, 1, Position.POS_STANDING,
            TAR_CHAR_ROOM | TAR_OBJ_INV | TAR_OBJ_ROOM, False, MAG_AFFECTS | MAG_ALTER_OBJS,
            [4, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_DETECT_INVIS, "vedi invisibile",
            20, 10, 2, Position.POS_STANDING,
            TAR_CHAR_ROOM | TAR_SELF_ONLY, False, MAG_AFFECTS,
            [2, 6, 3, LVL_IMMORT, 5, LVL_IMMORT])
    _spello(SPELL_DETECT_MAGIC, "percepire magia",
            20, 10, 2, Position.POS_STANDING,
            TAR_CHAR_ROOM | TAR_SELF_ONLY, False, MAG_AFFECTS,
            [2, 5, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_INFRAVISION, "infravisione",
            25, 10, 1, Position.POS_STANDING,
            TAR_CHAR_ROOM | TAR_SELF_ONLY, False, MAG_AFFECTS,
            [3, 7, 4, LVL_IMMORT, 5, LVL_IMMORT])
    _spello(SPELL_SANCTUARY, "santuario",
            110, 85, 5, Position.POS_STANDING,
            TAR_CHAR_ROOM, False, MAG_AFFECTS,
            [15, 13, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_PROT_FROM_EVIL, "protezione dal male",
            40, 20, 3, Position.POS_STANDING,
            TAR_CHAR_ROOM | TAR_SELF_ONLY, False, MAG_AFFECTS,
            [LVL_IMMORT, 8, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_SENSE_LIFE, "percepire vita",
            20, 10, 2, Position.POS_STANDING,
            TAR_CHAR_ROOM | TAR_SELF_ONLY, False, MAG_AFFECTS,
            [5, 7, 4, LVL_IMMORT, 5, LVL_IMMORT])
    _spello(SPELL_SHIELD, "scudo magico",
            50, 30, 3, Position.POS_FIGHTING,
            TAR_CHAR_ROOM | TAR_SELF_ONLY, False, MAG_AFFECTS,
            [8, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_WATERWALK, "cammino sull'acqua",
            40, 20, 2, Position.POS_STANDING,
            TAR_CHAR_ROOM, False, MAG_AFFECTS,
            [12, 8, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_GROUP_ARMOR, "armatura di gruppo",
            60, 30, 2, Position.POS_STANDING,
            TAR_IGNORE, False, MAG_GROUPS,
            [8, 5, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])

    # Debuff spells
    _spello(SPELL_BLINDNESS, "cecita'",
            35, 25, 1, Position.POS_STANDING,
            TAR_CHAR_ROOM | TAR_NOT_SELF, True, MAG_AFFECTS,
            [9, 6, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_CURSE, "maledizione",
            80, 50, 2, Position.POS_STANDING,
            TAR_CHAR_ROOM | TAR_OBJ_INV, True, MAG_AFFECTS | MAG_ALTER_OBJS,
            [14, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_POISON, "veleno",
            50, 30, 3, Position.POS_STANDING,
            TAR_CHAR_ROOM | TAR_NOT_SELF | TAR_OBJ_INV, True, MAG_AFFECTS | MAG_ALTER_OBJS,
            [14, 8, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_SLEEP, "sonno",
            40, 25, 5, Position.POS_STANDING,
            TAR_CHAR_ROOM, True, MAG_AFFECTS,
            [8, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])

    # Cure/remove spells
    _spello(SPELL_CURE_BLIND, "cura cecita'",
            30, 10, 2, Position.POS_STANDING,
            TAR_CHAR_ROOM, False, MAG_UNAFFECTS,
            [LVL_IMMORT, 4, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_REMOVE_CURSE, "rimuovi maledizione",
            65, 40, 5, Position.POS_STANDING,
            TAR_CHAR_ROOM | TAR_OBJ_INV, False, MAG_UNAFFECTS | MAG_ALTER_OBJS,
            [LVL_IMMORT, 9, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])
    _spello(SPELL_REMOVE_POISON, "rimuovi veleno",
            40, 20, 4, Position.POS_STANDING,
            TAR_CHAR_ROOM | TAR_OBJ_INV, False, MAG_UNAFFECTS | MAG_ALTER_OBJS,
            [10, 3, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])

    # Utility
    _spello(SPELL_WORD_OF_RECALL, "parola del ritorno",
            20, 10, 2, Position.POS_FIGHTING,
            TAR_CHAR_ROOM | TAR_SELF_ONLY, False, MAG_MANUAL,
            [LVL_IMMORT, 15, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT, LVL_IMMORT])


# Initialize on module load
_init_spell_table()


# ---------------------------------------------------------------------------
# Spell name lookup
# ---------------------------------------------------------------------------

def find_spell_num(name: str) -> int:
    """Find spell number by name (prefix match).

    Ported from find_skill_num() in spell_parser.c.
    """
    name_lower = name.lower()
    for spl_num, si in spell_info.items():
        if si.name.lower().startswith(name_lower):
            return spl_num
    return -1


def get_spell_name(spl: int) -> str:
    """Get spell name by number."""
    si = spell_info.get(spl)
    return si.name if si else "sconosciuto"


# ---------------------------------------------------------------------------
# Mana cost calculation
# ---------------------------------------------------------------------------

def mag_manacost(ch, spl: int) -> int:
    """Calculate mana cost for a spell.

    Ported from mag_manacost() in spell_parser.c.
    """
    si = spell_info.get(spl)
    if si is None:
        return 100

    level = ch.player.level
    mana = si.mana_max - (si.mana_change * (level - 1))
    return max(si.mana_min, mana)


# ---------------------------------------------------------------------------
# mag_damage: damage spells
# Ported from mag_damage() in magic.c
# ---------------------------------------------------------------------------

def mag_damage(
    level: int, ch, victim, spellnum: int, world,
) -> int:
    """Apply spell damage.

    Ported from mag_damage() in magic.c.
    """
    from dalila.combat.fight import damage as combat_damage

    dam = 0
    tipo = DamageType.DANNO_FISICO

    match spellnum:
        case s if s == SPELL_MAGIC_MISSILE:
            dam = random.randint(1, 8) + (level // 5)
            tipo = DamageType.DANNO_FISICO
        case s if s == SPELL_BURNING_HANDS:
            dam = random.randint(3, 8) + (level // 3)
            tipo = DamageType.DANNO_FUOCO
        case s if s == SPELL_SHOCKING_GRASP:
            dam = random.randint(5, 10) + (level // 3)
            tipo = DamageType.DANNO_ELETTRICITA
        case s if s == SPELL_CHILL_TOUCH:
            dam = random.randint(3, 6) + (level // 4)
            tipo = DamageType.DANNO_GHIACCIO
        case s if s == SPELL_COLOR_SPRAY:
            dam = random.randint(7, 14) + (level // 2)
            tipo = DamageType.DANNO_FISICO
        case s if s == SPELL_LIGHTNING_BOLT:
            dam = random.randint(7, 14) + level
            tipo = DamageType.DANNO_ELETTRICITA
        case s if s == SPELL_FIREBALL:
            dam = random.randint(10, 20) + level
            tipo = DamageType.DANNO_FUOCO
        case s if s == SPELL_CALL_LIGHTNING:
            dam = random.randint(7, 14) + level
            tipo = DamageType.DANNO_ELETTRICITA
        case s if s == SPELL_HARM:
            dam = random.randint(20, 40) + level
            tipo = DamageType.DANNO_FISICO
        case s if s == SPELL_ENERGY_DRAIN:
            dam = random.randint(15, 30) + level
            tipo = DamageType.DANNO_FISICO
        case s if s == SPELL_EARTHQUAKE:
            dam = random.randint(5, 10) + (level // 2)
            tipo = DamageType.DANNO_FISICO
        case s if s == SPELL_DISPEL_EVIL:
            dam = random.randint(6, 12) + level
            tipo = DamageType.DANNO_FISICO
        case s if s == SPELL_DISPEL_GOOD:
            dam = random.randint(6, 12) + level
            tipo = DamageType.DANNO_FISICO
        case _:
            dam = random.randint(1, 6)

    dam = max(0, dam)
    combat_damage(ch, victim, dam, spellnum, world, maxato=False, tipo=tipo)
    return dam


# ---------------------------------------------------------------------------
# mag_points: healing/restoration spells
# Ported from mag_points() in magic.c
# ---------------------------------------------------------------------------

def mag_points(level: int, ch, victim, spellnum: int) -> None:
    """Apply point restoration spells (healing, refresh).

    Ported from mag_points() in magic.c.
    """
    from dalila.combat.fight import _send_to_char

    heal = 0
    move = 0

    match spellnum:
        case s if s == SPELL_CURE_LIGHT:
            heal = random.randint(1, 8) + (level // 4)
        case s if s == SPELL_CURE_SERIOUS:
            heal = random.randint(5, 15) + (level // 3)
        case s if s == SPELL_CURE_CRITIC:
            heal = random.randint(8, 20) + (level // 2)
        case s if s == SPELL_HEAL:
            heal = 100 + random.randint(0, level)
        case s if s == SPELL_REFRESH:
            move = random.randint(10, 30) + level
        case _:
            return

    if heal > 0:
        victim.points.hit = min(
            victim.points.hit + heal, victim.points.max_hit,
        )
        _send_to_char(victim, "Ti senti meglio.\r\n")

    if move > 0:
        victim.points.move = min(
            victim.points.move + move, victim.points.max_move,
        )
        _send_to_char(victim, "Ti senti ristorato.\r\n")

    from dalila.combat.fight import update_pos
    update_pos(victim)


# ---------------------------------------------------------------------------
# mag_affects: buff/debuff spells
# Ported from mag_affects() in magic.c (simplified)
# ---------------------------------------------------------------------------

def mag_affects(
    level: int, ch, victim, spellnum: int, savetype: int,
) -> None:
    """Apply affect-based spells (buffs/debuffs).

    Ported from mag_affects() in magic.c. Simplified for Phase 3.
    """
    from dalila.combat.fight import _send_to_char
    from dalila.engine.handler import affect_to_char
    from dalila.constants import ApplyType

    duration = 0
    modifier = 0
    location = ApplyType.APPLY_NONE
    bv = Bitvector()

    match spellnum:
        case s if s == SPELL_ARMOR:
            duration = 24
            modifier = -20
            location = ApplyType.APPLY_AC
            _send_to_char(victim, "Ti senti protetto.\r\n")
        case s if s == SPELL_BLESS:
            duration = 12
            modifier = 2
            location = ApplyType.APPLY_HITROLL
            _send_to_char(victim, "Ti senti virtuoso.\r\n")
        case s if s == SPELL_STRENGTH:
            duration = level // 2
            modifier = 1 + (level > 18) + (level > 25)
            location = ApplyType.APPLY_STR
            _send_to_char(victim, "Ti senti piu' forte!\r\n")
        case s if s == SPELL_INVISIBLE:
            duration = 12 + level // 4
            bv.set_bit(AffectedBy.AFF_INVISIBLE)
            _send_to_char(victim, "Svanisci nel nulla.\r\n")
        case s if s == SPELL_BLINDNESS:
            duration = 2
            bv.set_bit(AffectedBy.AFF_BLIND)
            _send_to_char(victim, "Sei stato accecato!\r\n")
            _send_to_char(ch, f"{victim.player.name} e' stato accecato!\r\n")
        case s if s == SPELL_CURSE:
            duration = level * 2
            modifier = -1
            location = ApplyType.APPLY_HITROLL
            bv.set_bit(AffectedBy.AFF_CURSE)
            _send_to_char(victim, "Ti senti maledetto!\r\n")
        case s if s == SPELL_DETECT_INVIS:
            duration = 12 + level
            bv.set_bit(AffectedBy.AFF_DETECT_INVIS)
            _send_to_char(victim, "I tuoi occhi bruciano per un momento.\r\n")
        case s if s == SPELL_DETECT_MAGIC:
            duration = 12 + level
            bv.set_bit(AffectedBy.AFF_DETECT_MAGIC)
            _send_to_char(victim, "I tuoi occhi brillano di luce gialla.\r\n")
        case s if s == SPELL_INFRAVISION:
            duration = 12 + level
            bv.set_bit(AffectedBy.AFF_INFRAVISION)
            _send_to_char(victim, "I tuoi occhi brillano di luce rossa.\r\n")
        case s if s == SPELL_POISON:
            duration = level
            modifier = -2
            location = ApplyType.APPLY_STR
            bv.set_bit(AffectedBy.AFF_POISON)
            _send_to_char(victim, "Ti senti molto male.\r\n")
        case s if s == SPELL_SANCTUARY:
            duration = 4
            bv.set_bit(AffectedBy.AFF_SANCTUARY)
            _send_to_char(
                victim,
                "Una luce bianca avvolge il tuo corpo.\r\n",
            )
        case s if s == SPELL_SLEEP:
            duration = 4 + level // 4
            bv.set_bit(AffectedBy.AFF_SLEEP)
            if victim.position > Position.POS_SLEEPING:
                _send_to_char(victim, "Ti senti molto assonnato...ZZzzz...\r\n")
                victim.position = Position.POS_SLEEPING
        case s if s == SPELL_PROT_FROM_EVIL:
            duration = 24
            bv.set_bit(AffectedBy.AFF_PROTECT_EVIL)
            _send_to_char(victim, "Ti senti invulnerabile!\r\n")
        case s if s == SPELL_SENSE_LIFE:
            duration = level
            bv.set_bit(AffectedBy.AFF_SENSE_LIFE)
            _send_to_char(victim, "I tuoi sensi si affinano.\r\n")
        case s if s == SPELL_SHIELD:
            duration = 8
            modifier = -10
            location = ApplyType.APPLY_AC
            bv.set_bit(AffectedBy.AFF_SHIELD)
            _send_to_char(victim, "Uno scudo magico ti avvolge.\r\n")
        case s if s == SPELL_WATERWALK:
            duration = 24
            bv.set_bit(AffectedBy.AFF_WATERWALK)
            _send_to_char(victim, "Senti le piante dei piedi formicolanti.\r\n")
        case _:
            return

    af = AffectedType(
        natura=SPELLSKILL,
        type=spellnum,
        duration=duration,
        modifier=modifier,
        location=location,
        bitvector=bv,
    )
    affect_to_char(victim, af)

    # Apply the affect flags to the character's saved bitvector
    if bv.any_set():
        victim.char_specials_saved.affected_by[0] |= bv.banks[0]


# ---------------------------------------------------------------------------
# mag_unaffects: remove affect spells
# Ported from mag_unaffects() in magic.c
# ---------------------------------------------------------------------------

def mag_unaffects(
    level: int, ch, victim, spellnum: int, savetype: int,
) -> None:
    """Remove affects (cure blind, remove curse, etc.).

    Ported from mag_unaffects() in magic.c.
    """
    from dalila.combat.fight import _send_to_char
    from dalila.engine.handler import affect_from_char

    match spellnum:
        case s if s == SPELL_CURE_BLIND:
            affect_from_char(victim, SPELLSKILL, SPELL_BLINDNESS)
            victim.char_specials_saved.affected_by[0] &= ~AffectedBy.AFF_BLIND
            _send_to_char(victim, "La tua vista ritorna!\r\n")
        case s if s == SPELL_REMOVE_CURSE:
            affect_from_char(victim, SPELLSKILL, SPELL_CURSE)
            victim.char_specials_saved.affected_by[0] &= ~AffectedBy.AFF_CURSE
            _send_to_char(victim, "Senti un peso levarsi da te.\r\n")
        case s if s == SPELL_REMOVE_POISON:
            affect_from_char(victim, SPELLSKILL, SPELL_POISON)
            victim.char_specials_saved.affected_by[0] &= ~AffectedBy.AFF_POISON
            _send_to_char(victim, "Un calore piacevole ti attraversa.\r\n")
        case s if s == SPELL_HEAL:
            # Heal also removes blindness and poison
            affect_from_char(victim, SPELLSKILL, SPELL_BLINDNESS)
            affect_from_char(victim, SPELLSKILL, SPELL_POISON)
            victim.char_specials_saved.affected_by[0] &= ~(
                AffectedBy.AFF_BLIND | AffectedBy.AFF_POISON
            )


# ---------------------------------------------------------------------------
# mag_groups: group spells
# ---------------------------------------------------------------------------

def mag_groups(
    level: int, ch, spellnum: int, world,
) -> None:
    """Apply group spells.

    Ported from mag_groups() in magic.c.
    """
    if ch.in_room == NOWHERE or ch.in_room not in world.rooms:
        return
    room = world.rooms[ch.in_room]

    for target in room._characters:
        # Apply to grouped characters
        if target.char_specials_saved.affected_by[0] & AffectedBy.AFF_GROUP:
            match spellnum:
                case s if s == SPELL_GROUP_HEAL:
                    mag_points(level, ch, target, SPELL_HEAL)
                case s if s == SPELL_GROUP_ARMOR:
                    mag_affects(level, ch, target, SPELL_ARMOR, 0)


# ---------------------------------------------------------------------------
# cast_spell: main casting entry point
# Ported from cast_spell() in spell_parser.c
# ---------------------------------------------------------------------------

def cast_spell(
    ch, victim, obj, spellnum: int, world,
) -> bool:
    """Cast a spell: check requirements, deduct mana, apply effects.

    Ported from cast_spell() in spell_parser.c.
    Returns True if spell was cast.
    """
    from dalila.combat.fight import _send_to_char

    si = spell_info.get(spellnum)
    if si is None:
        _send_to_char(ch, "Quell'incantesimo non esiste!\r\n")
        return False

    # Check mana
    mana_cost = mag_manacost(ch, spellnum)
    if ch.points.mana < mana_cost:
        _send_to_char(ch, "Non hai abbastanza mana!\r\n")
        return False

    # Deduct mana
    ch.points.mana -= mana_cost

    # Apply spell effects based on routines
    if si.routines & MAG_DAMAGE and victim:
        mag_damage(ch.player.level, ch, victim, spellnum, world)

    if si.routines & MAG_AFFECTS and victim:
        mag_affects(ch.player.level, ch, victim, spellnum, 0)

    if si.routines & MAG_UNAFFECTS and victim:
        mag_unaffects(ch.player.level, ch, victim, spellnum, 0)

    if si.routines & MAG_POINTS and victim:
        mag_points(ch.player.level, ch, victim, spellnum)

    if si.routines & MAG_GROUPS:
        mag_groups(ch.player.level, ch, spellnum, world)

    return True
