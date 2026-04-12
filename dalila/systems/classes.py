"""Class system: THAC0 tables, XP tables, saving throws, hit dice, class info.

Ported from class.c: thaco[][], titles[][], saving_throws, hit dice tables.
"""

from __future__ import annotations

from dalila.constants import (
    LVL_IMPL,
    CharClass,
    NUM_CLASSES,
)

# ---------------------------------------------------------------------------
# THAC0 tables: thaco[class][level]
# Ported exactly from class.c lines 443-468
# ---------------------------------------------------------------------------

THACO: list[list[int]] = [
    # CLASS_MAGIC_USER (Pandion)
    [100, 20, 20, 20, 20, 20, 19, 19, 19, 19, 18, 18, 18, 17, 17, 16,
     16, 16, 15, 15, 15, 14, 14, 13, 13, 13, 12, 12, 12, 11, 11, 11,
     10, 10, 10, 9, 9, 9, 9, 9, 8, 8, 8, 8, 7, 7, 7, 7, 6, 6, 6, 6,
     5, 5, 5, 5, 5, 5, 5, 4, 4, 4, 4, 3, 3, 3, 2, 2, 2, 2, 2,
     1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    # CLASS_CLERIC (Cyrinic)
    [100, 20, 20, 20, 20, 19, 19, 19, 18, 18, 17, 17, 16, 16, 16, 15,
     15, 15, 14, 14, 13, 13, 13, 12, 12, 12, 11, 11, 11, 10, 10, 10,
     9, 9, 9, 9, 9, 8, 8, 8, 7, 7, 7, 6, 6, 6, 6, 5, 5, 5, 5, 5,
     5, 5, 4, 4, 4, 4, 3, 3, 3, 3, 2, 2, 2, 2, 2, 1, 1, 1, 1,
     1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    # CLASS_THIEF (Alcione)
    [100, 20, 20, 20, 19, 19, 18, 17, 17, 16, 16, 16, 15, 15, 15, 14,
     14, 13, 13, 13, 12, 12, 12, 11, 11, 10, 10, 9, 9, 9, 9, 8, 8,
     7, 7, 7, 6, 6, 6, 6, 5, 5, 5, 5, 5, 5, 5, 5, 4, 4, 4, 3,
     3, 3, 3, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
     1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    # CLASS_WARRIOR (Genidian)
    [100, 20, 20, 19, 18, 17, 17, 16, 16, 16, 15, 15, 15, 14, 14, 13,
     13, 13, 12, 12, 11, 11, 10, 10, 9, 9, 9, 8, 8, 7, 7, 7, 6, 6,
     6, 5, 5, 5, 5, 4, 4, 4, 4, 3, 3, 3, 3, 2, 2, 2, 2, 2, 2, 2,
     2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
     1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    # CLASS_PELOI
    [100, 20, 20, 20, 19, 19, 18, 17, 17, 16, 16, 16, 15, 15, 15, 14,
     14, 13, 13, 13, 12, 12, 12, 11, 11, 10, 10, 9, 9, 9, 9, 8, 8,
     7, 7, 7, 6, 6, 6, 6, 5, 5, 5, 5, 5, 5, 5, 5, 4, 4, 4, 3,
     3, 3, 3, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
     1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    # CLASS_DARESIANO (= Pandion)
    [100, 20, 20, 20, 20, 20, 19, 19, 19, 19, 18, 18, 18, 17, 17, 16,
     16, 16, 15, 15, 15, 14, 14, 13, 13, 13, 12, 12, 12, 11, 11, 11,
     10, 10, 10, 9, 9, 9, 9, 9, 8, 8, 8, 8, 7, 7, 7, 7, 6, 6, 6, 6,
     5, 5, 5, 5, 5, 5, 5, 4, 4, 4, 4, 3, 3, 3, 2, 2, 2, 2, 2,
     1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
]


def get_thaco(class_: int, level: int) -> int:
    """Get THAC0 for a class and level.

    Ported from thaco[][] in class.c.
    """
    if class_ < 0 or class_ >= NUM_CLASSES:
        class_ = CharClass.CLASS_DARESIANO
    level = max(0, min(level, LVL_IMPL))
    return THACO[class_][level]


# ---------------------------------------------------------------------------
# Experience tables: titles[class][level].exp
# Ported from class.c: titles[][] -- same for all classes in Dalila
# ---------------------------------------------------------------------------

_XP_TABLE: list[int] = [
    0,              # Level 0
    1,              # Level 1
    4000,           # Level 2
    10000,
    18000,
    28000,
    40000,
    54000,
    70000,
    90000,
    115000,         # Level 10
    150000,
    190000,
    238000,
    294000,
    358000,
    422000,
    524000,
    656000,
    818000,
    1010000,        # Level 20
    1230000,
    1530000,
    1820000,
    2190000,
    2610000,
    3080000,
    3600000,
    4170000,
    4790000,
    5460000,        # Level 30
    6180000,
    7000000,
    7920000,
    8950000,
    10100000,
    11400000,
    12850000,
    14450000,
    16200000,
    18100000,       # Level 40
    20200000,
    22700000,
    25700000,
    29200000,
    33200000,
    38200000,
    44200000,
    51200000,
    59200000,
    68200000,       # Level 50
    78200000,
    89700000,
    102700000,
    117200000,
    133200000,
    150700000,
    170700000,
    193200000,
    218200000,
    246000000,      # Level 60
    276000000,
    310000000,
    350000000,
    400000000,
    460000000,
    530000000,
    610000000,
    700000000,
    800000000,
    900000000,      # Level 70
    1000000000,     # Level 71
    1050000000,
    1100000000,
    1150000000,
    1200000000,
    1250000000,
    1300000000,
    1350000000,
    1400000000,
    1450000000,     # Level 80
    1500000000,
    1550000000,
    1600000000,
    1650000000,
    1700000000,
    1750000000,
    1800000000,
    1850000000,
    1900000000,
    1950000000,     # Level 90
    2000000000,     # Level 91
]


def level_exp(class_: int, level: int) -> int:
    """Get the experience threshold for a given class and level.

    Ported from titles[class][level].exp in class.c.
    In Dalila, the XP table is identical for all classes.
    """
    level = max(0, min(level, LVL_IMPL))
    return _XP_TABLE[level]


# ---------------------------------------------------------------------------
# Strength application table
# Ported from str_app[] in constants.c
# ---------------------------------------------------------------------------

class StrApp:
    """Strength modifier table entry."""
    __slots__ = ("tohit", "todam", "carry_w", "wield_w")

    def __init__(self, tohit: int, todam: int, carry_w: int, wield_w: int):
        self.tohit = tohit
        self.todam = todam
        self.carry_w = carry_w
        self.wield_w = wield_w


# Index 0..25 = str 0..25, then 26..30 = str 18/0-50, 18/51-75, 18/76-90,
# 18/91-99, 18/100
STR_APP: list[StrApp] = [
    StrApp(-5, -4, 0, 0),      # str = 0
    StrApp(-5, -4, 3, 1),      # str = 1
    StrApp(-3, -2, 3, 2),
    StrApp(-3, -1, 10, 3),
    StrApp(-2, -1, 25, 4),
    StrApp(-2, -1, 55, 5),     # str = 5
    StrApp(-1, 0, 80, 6),
    StrApp(-1, 0, 90, 7),
    StrApp(0, 0, 100, 8),
    StrApp(0, 0, 100, 9),
    StrApp(0, 0, 115, 10),     # str = 10
    StrApp(0, 0, 115, 11),
    StrApp(0, 1, 150, 13),
    StrApp(1, 1, 160, 14),
    StrApp(1, 1, 175, 15),
    StrApp(1, 2, 185, 16),     # str = 15
    StrApp(2, 2, 195, 17),
    StrApp(2, 3, 220, 18),
    StrApp(3, 4, 255, 20),     # str = 18
    StrApp(4, 9, 640, 40),     # str = 19
    StrApp(4, 10, 700, 40),    # str = 20
    StrApp(4, 11, 810, 40),
    StrApp(4, 12, 970, 40),
    StrApp(5, 13, 1130, 40),
    StrApp(6, 14, 1440, 40),
    StrApp(7, 15, 5000, 40),   # str = 25
    # str = 18/0-50, 18/51-75, 18/76-90, 18/91-99, 18/100
    StrApp(3, 5, 280, 22),
    StrApp(3, 6, 305, 24),
    StrApp(4, 6, 340, 26),
    StrApp(4, 7, 380, 28),
    StrApp(4, 8, 520, 30),
]


def strength_apply_index(ch) -> int:
    """Get the index into str_app[] for a character.

    Ported from STRENGTH_APPLY_INDEX macro in utils.h.
    """
    s = ch.aff_abils.str
    if s <= 0:
        return 0
    if s > 25:
        return 25
    if s == 18:
        add = ch.aff_abils.str_add
        if add <= 50:
            return 26
        if add <= 75:
            return 27
        if add <= 90:
            return 28
        if add <= 99:
            return 29
        return 30
    return s


# ---------------------------------------------------------------------------
# Dexterity application table
# Ported from dex_app[] in constants.c
# ---------------------------------------------------------------------------

class DexApp:
    """Dexterity modifier table entry."""
    __slots__ = ("reaction", "miss_att", "defensive", "item_carry")

    def __init__(
        self, reaction: int, miss_att: int, defensive: int, item_carry: int,
    ):
        self.reaction = reaction
        self.miss_att = miss_att
        self.defensive = defensive
        self.item_carry = item_carry


DEX_APP: list[DexApp] = [
    DexApp(-7, -7, 6, 1),     # dex = 0
    DexApp(-7, -6, 5, 2),     # dex = 1
    DexApp(-6, -4, 4, 3),
    DexApp(-6, -4, 3, 4),
    DexApp(-5, -3, 3, 5),
    DexApp(-4, -2, 2, 6),     # dex = 5
    DexApp(-3, -1, 2, 7),
    DexApp(-2, -1, 1, 8),
    DexApp(-1, -1, 1, 9),
    DexApp(0, 0, 0, 15),
    DexApp(0, 0, 0, 18),      # dex = 10
    DexApp(0, 0, 0, 20),
    DexApp(0, 0, 0, 22),
    DexApp(1, 1, -1, 24),
    DexApp(1, 1, -1, 26),
    DexApp(2, 2, -2, 28),     # dex = 15
    DexApp(3, 2, -3, 30),
    DexApp(4, 3, -4, 32),
    DexApp(5, 3, -5, 35),     # dex = 18
    DexApp(6, 4, -6, 40),
    DexApp(6, 4, -6, 50),     # dex = 20
    DexApp(7, 5, -7, 60),
    DexApp(7, 5, -7, 70),
    DexApp(8, 6, -7, 80),
    DexApp(8, 7, -8, 100),
    DexApp(9, 7, -8, 200),    # dex = 25
]


def get_dex_app(dex: int) -> DexApp:
    """Get the dexterity modifier table entry."""
    return DEX_APP[max(0, min(dex, 25))]


def get_str_app(ch) -> StrApp:
    """Get the strength modifier table entry for a character."""
    return STR_APP[strength_apply_index(ch)]


# ---------------------------------------------------------------------------
# Backstab multiplier
# Ported from backstab_mult() in fight.c
# ---------------------------------------------------------------------------

def backstab_mult(level: int) -> int:
    """Backstab damage multiplier based on level.

    Ported from backstab_mult() in fight.c.
    """
    if level <= 0:
        return 1
    if level <= 7:
        return 2
    if level <= 13:
        return 3
    if level <= 20:
        return 4
    if level <= 28:
        return 5
    if level <= 36:
        return 6
    if level <= 45:
        return 7
    if level <= 55:
        return 8
    return 9


# ---------------------------------------------------------------------------
# Class abbreviations and hometowns
# Ported from class.c
# ---------------------------------------------------------------------------

CLASS_ABBREVS: list[str] = [
    "Pandion", "Cyrinic", "Alcione", "Genidian", "Peloi", "Daresiano",
]

HOMETOWN_NAMES: list[str] = [
    "Deira", "Jiroch", "Cimmura", "Chyrellos", "Lamorka", "Aldeeran",
]

RELIGION_NAMES: list[str] = [
    "Nessuna", "Shaarr", "Xhyphys", "Silue", "Therion",
]


# ---------------------------------------------------------------------------
# Attack hit text table
# Ported from attack_hit_text[] in fight.c
# ---------------------------------------------------------------------------

class AttackHitType:
    """Weapon attack text entry."""
    __slots__ = ("singular", "plural", "weapon")

    def __init__(self, singular: str, plural: str, weapon: str):
        self.singular = singular
        self.plural = plural
        self.weapon = weapon


ATTACK_HIT_TEXT: list[AttackHitType] = [
    AttackHitType("hit", "urt", "ALTRO"),           # 0
    AttackHitType("sting", "pungol", "PUGNALE(1)"),
    AttackHitType("whip", "frust", "FRUSTA"),
    AttackHitType("slash", "squarci", "ASCIA(1)"),
    AttackHitType("bite", "azzann", "ZANNE"),
    AttackHitType("bludgeon", "randell", "MAZZA(1)"),  # 5
    AttackHitType("crush", "frantum", "MAZZA(2)"),
    AttackHitType("pound", "trapass", "LANCIA(1)"),
    AttackHitType("claw", "artigli", "ARTIGLI"),
    AttackHitType("maul", "pest", "MAZZA(3)"),
    AttackHitType("thrash", "lacer", "SPADA(1)"),      # 10
    AttackHitType("pierce", "infilz", "LANCIA(2)"),
    AttackHitType("blast", "sferz", "SPADA(2)"),
    AttackHitType("punch", "picchi", "PUGNI"),
    AttackHitType("stab", "pugnal", "PUGNALE(2)"),
    AttackHitType("slay", "massacr", "ASCIA(2)"),      # 15
]


# ---------------------------------------------------------------------------
# Weapon type constants
# Ported from spells.h
# ---------------------------------------------------------------------------

TYPE_UNDEFINED: int = -1
TYPE_HIT: int = 300
TYPE_STING: int = 301
TYPE_WHIP: int = 302
TYPE_SLASH: int = 303
TYPE_BITE: int = 304
TYPE_BLUDGEON: int = 305
TYPE_CRUSH: int = 306
TYPE_POUND: int = 307
TYPE_CLAW: int = 308
TYPE_MAUL: int = 309
TYPE_THRASH: int = 310
TYPE_PIERCE: int = 311
TYPE_BLAST: int = 312
TYPE_PUNCH: int = 313
TYPE_STAB: int = 314
TYPE_SLAY: int = 315
TYPE_HUNGER: int = 398
TYPE_SUFFERING: int = 399

# Skill numbers from spells.h
SKILL_BACKSTAB: int = 131
SKILL_BASH: int = 132
SKILL_HIDE: int = 133
SKILL_KICK: int = 134
SKILL_PICK_LOCK: int = 135
SKILL_RESCUE: int = 137
SKILL_SNEAK: int = 138
SKILL_STEAL: int = 139
SKILL_TRACK: int = 140
SKILL_DISARM: int = 141
SKILL_SECOND_ATTACK: int = 142
SKILL_THIRD_ATTACK: int = 143
SKILL_ENH_DAMAGE: int = 144
SKILL_PARRY: int = 145
SKILL_FOURTH_ATTACK: int = 154
SKILL_FIFTH_ATTACK: int = 155
SECOND_WEAPON: int = 166
SECOND_BACKSTAB: int = 167
SKILL_COLPO_MORTALE: int = 169

# Spell numbers from spells.h (key ones for combat/magic)
SPELL_ARMOR: int = 1
SPELL_BLESS: int = 3
SPELL_BLINDNESS: int = 4
SPELL_BURNING_HANDS: int = 5
SPELL_CALL_LIGHTNING: int = 6
SPELL_CHARM: int = 7
SPELL_CHILL_TOUCH: int = 8
SPELL_COLOR_SPRAY: int = 10
SPELL_CREATE_FOOD: int = 12
SPELL_CREATE_WATER: int = 13
SPELL_CURE_BLIND: int = 14
SPELL_CURE_CRITIC: int = 15
SPELL_CURE_LIGHT: int = 16
SPELL_CURSE: int = 17
SPELL_DETECT_ALIGN: int = 18
SPELL_DETECT_INVIS: int = 19
SPELL_DETECT_MAGIC: int = 20
SPELL_DETECT_POISON: int = 21
SPELL_DISPEL_EVIL: int = 22
SPELL_EARTHQUAKE: int = 23
SPELL_ENERGY_DRAIN: int = 25
SPELL_FIREBALL: int = 26
SPELL_HARM: int = 27
SPELL_HEAL: int = 28
SPELL_INVISIBLE: int = 29
SPELL_LIGHTNING_BOLT: int = 30
SPELL_MAGIC_MISSILE: int = 32
SPELL_POISON: int = 33
SPELL_PROT_FROM_EVIL: int = 34
SPELL_REMOVE_CURSE: int = 35
SPELL_SANCTUARY: int = 36
SPELL_SHOCKING_GRASP: int = 37
SPELL_SLEEP: int = 38
SPELL_STRENGTH: int = 39
SPELL_SUMMON: int = 40
SPELL_WORD_OF_RECALL: int = 42
SPELL_REMOVE_POISON: int = 43
SPELL_SENSE_LIFE: int = 44
SPELL_ANIMATE_DEAD: int = 45
SPELL_DISPEL_GOOD: int = 46
SPELL_GROUP_ARMOR: int = 47
SPELL_GROUP_HEAL: int = 48
SPELL_INFRAVISION: int = 50
SPELL_WATERWALK: int = 51
SPELL_DISINTEGRATE: int = 53
SPELL_FLY: int = 54
SPELL_CONE_OF_COLD: int = 56
SPELL_CURE_SERIOUS: int = 77
SPELL_SHIELD: int = 84
SPELL_MIRROR_IMAGE: int = 85
SPELL_DEATHDANCE: int = 87
SPELL_REFRESH: int = 93
SPELL_FIRESHD: int = 97
SPELL_PARALIZE: int = 102
SPELL_SILENCE: int = 106
SPELL_ANTIMAGIC: int = 107
SPELL_AID: int = 109
SPELL_ENDURANCE: int = 112

MAX_SPELLS: int = 130

# Disease/NPC spell numbers
DISEASE_RAFFREDDORE: int = 203
DISEASE_PESTE: int = 204
DISEASE_BACCO: int = 205
DISEASE_SHAARR: int = 206
DISEASE_PIAGHE: int = 207
DISEASE_XHYPHYS: int = 208
DISEASE_MORFEO: int = 209

TOP_SPELL_DEFINE: int = 299

# Natura constants for affects
SPELLSKILL: int = 0
PROFICIENZE: int = 1
ABILITA: int = 2


def is_weapon_type(attack_type: int) -> bool:
    """Check if an attack type is a weapon attack.

    Ported from IS_WEAPON macro in fight.c.
    """
    return TYPE_HIT <= attack_type < TYPE_HUNGER
