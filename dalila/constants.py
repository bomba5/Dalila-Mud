"""All game constants ported from structs.h, spells.h, utils.h, and db.h.

This module contains every #define constant from the original C codebase,
organized into IntEnum (discrete sets) and IntFlag (bitfields) classes.
Values are exact matches to the C defines -- do not change them.
"""

from __future__ import annotations

import enum


# ---------------------------------------------------------------------------
# Sentinel values
# ---------------------------------------------------------------------------
NOWHERE: int = -1
NOTHING: int = -1
NOBODY: int = -1

# ---------------------------------------------------------------------------
# Format modes
# ---------------------------------------------------------------------------
FORMAT_INDENT: int = 1 << 0


# ===========================================================================
# IntEnum classes -- discrete value sets
# ===========================================================================


class Direction(enum.IntEnum):
    """Cardinal directions: index to room_data.dir_option[]."""
    NORTH = 0
    EAST = 1
    SOUTH = 2
    WEST = 3
    UP = 4
    DOWN = 5

NUM_OF_DIRS: int = 6


class PlayerEvent(enum.IntEnum):
    """Player event timers (Adriano). Used in char_special_data."""
    LAST_BASH = 0
    LAST_STEAL = 1
    LAST_BREATH = 2
    LAST_CHKRIDING = 3
    LAST_PICK = 4
    LAST_TKILLER = 5
    LAST_LOOKCAMUF = 6
    LAST_ALLERT = 7
    LAST_TORNADO = 8
    LAST_AGGUATO = 9
    LAST_AFK = 10

NUM_EVENTS: int = 11


class BodyLocation(enum.IntEnum):
    """Critical hit body locations (PEPPE LOCATION)."""
    LOCATION_TESTA = 1
    LOCATION_BRACCIO_D = 2
    LOCATION_BRACCIO_S = 3
    LOCATION_TORSO = 4
    LOCATION_GAMBA_D = 5
    LOCATION_GAMBA_S = 6
    LOCATION_RANDOM = 7


class Religion(enum.IntEnum):
    """Religions of Dalila."""
    RELIGIONE_NESSUNA = 0
    RELIGIONE_SHAARR = 1
    RELIGIONE_XHYPYS = 2
    RELIGIONE_SILUE = 3
    RELIGIONE_THERION = 4

NUM_RELIGIONI: int = 5
MAX_MEMBRI_RELIGIONE: int = 7


class SectorType(enum.IntEnum):
    """Room sector types: affects movement cost and abilities."""
    SECT_INSIDE = 0
    SECT_CITY = 1
    SECT_FIELD = 2
    SECT_FOREST = 3
    SECT_HILLS = 4
    SECT_MOUNTAIN = 5
    SECT_WATER_SWIM = 6
    SECT_WATER_NOSWIM = 7
    SECT_UNDERWATER = 8
    SECT_FLYING = 9
    SECT_ROAD = 10


class CharClass(enum.IntEnum):
    """PC classes. Dalila names: Pandion, Cyrinic, Alcione, Genidian, Peloi, Daresiano."""
    CLASS_UNDEFINED = -1
    CLASS_MAGIC_USER = 0  # Pandion
    CLASS_CLERIC = 1      # Cyrinic
    CLASS_THIEF = 2       # Alcione
    CLASS_WARRIOR = 3     # Genidian
    CLASS_PELOI = 4
    CLASS_DARESIANO = 5

NUM_CLASSES: int = 6


class NPCClass(enum.IntEnum):
    """NPC classes."""
    CLASS_OTHER = 0
    CLASS_UNDEAD = 1
    CLASS_HUMANOID = 2
    CLASS_ANIMAL = 3
    CLASS_DRAGON = 4
    CLASS_GIANT = 5


class Sex(enum.IntEnum):
    """Character sex."""
    SEX_NEUTRAL = 0
    SEX_MALE = 1
    SEX_FEMALE = 2


class Position(enum.IntEnum):
    """Character position."""
    POS_DEAD = 0
    POS_MORTALLYW = 1
    POS_INCAP = 2
    POS_STUNNED = 3
    POS_SLEEPING = 4
    POS_RESTING = 5
    POS_SITTING = 6
    POS_FIGHTING = 7
    POS_STANDING = 8

# Hit point thresholds
HIT_INCAP: int = -3
HIT_MORTALLYW: int = -6
HIT_DEAD: int = -11


class ClanCriminal(enum.IntEnum):
    """Criminal flag types."""
    CLAN_THIEF = 0
    CLAN_KILLER = 1
    CLAN_TKILLER = 2
    CLAN_WKILLER = 3
    CLAN_WANTED = 4
    CLAN_STRAGE = 5
    CLAN_CORROTTO = 6
    CLAN_MULTA = 7


class WearPosition(enum.IntEnum):
    """Equipment slot positions (index for char_data.equipment[])."""
    WEAR_LIGHT = 0
    WEAR_FINGER_R = 1
    WEAR_FINGER_L = 2
    WEAR_NECK_1 = 3
    WEAR_NECK_2 = 4
    WEAR_BODY = 5
    WEAR_HEAD = 6
    WEAR_LEGS = 7
    WEAR_FEET = 8
    WEAR_HANDS = 9
    WEAR_ARMS = 10
    WEAR_SHIELD = 11
    WEAR_ABOUT = 12
    WEAR_WAIST = 13
    WEAR_WRIST_R = 14
    WEAR_WRIST_L = 15
    WEAR_WIELD = 16
    WEAR_HOLD = 17
    WEAR_LOBSX = 18
    WEAR_LOBDX = 19
    WEAR_SPALLE = 20
    WEAR_IMMOBIL = 21
    WEAR_EYE = 22
    WEAR_BOCCA = 23
    WEAR_ALTRO1 = 24
    WEAR_WIELD_L = 25
    WEAR_HANG = 26
    WEAR_VESTE = 27
    WEAR_RELIQUIA = 28

NUM_WEARS: int = 29


class ItemType(enum.IntEnum):
    """Object types: obj_data.obj_flags.type_flag."""
    ITEM_LIGHT = 1
    ITEM_SCROLL = 2
    ITEM_WAND = 3
    ITEM_STAFF = 4
    ITEM_WEAPON = 5
    ITEM_FIREWEAPON = 6
    ITEM_MISSILE = 7
    ITEM_TREASURE = 8
    ITEM_ARMOR = 9
    ITEM_POTION = 10
    ITEM_WORN = 11
    ITEM_OTHER = 12
    ITEM_TRASH = 13
    ITEM_TRAP = 14
    ITEM_CONTAINER = 15
    ITEM_NOTE = 16
    ITEM_DRINKCON = 17
    ITEM_KEY = 18
    ITEM_FOOD = 19
    ITEM_MONEY = 20
    ITEM_PEN = 21
    ITEM_BOAT = 22
    ITEM_FOUNTAIN = 23
    ITEM_FLIGHT = 24
    ITEM_PORTAL = 25
    ITEM_THROW = 26
    ITEM_GRENADE = 27
    ITEM_BOW = 28
    ITEM_SLING = 29
    ITEM_CROSSBOW = 30
    ITEM_BOLT = 31
    ITEM_ARROW = 32
    ITEM_ROCK = 33
    ITEM_RENT_MOUNT = 34
    ITEM_KEY_RENT = 35
    ITEM_MOUNT_FOOD = 36
    ITEM_MARTELLO = 37
    ITEM_SEGA = 38
    ITEM_PICCA = 39
    ITEM_SCUOIATORE = 40
    ITEM_FALCE = 41
    ITEM_ASCIA = 42
    ITEM_MARTELLETTO = 43
    ITEM_PIETRA = 44
    ITEM_ALBERO = 45
    ITEM_MINERALE = 46
    ITEM_NATURALE = 47
    ITEM_MET_GREZZO = 48
    ITEM_TRONCO = 49
    ITEM_PIETRA_GREZ = 50
    ITEM_PELLE_GREZ = 51
    ITEM_PRODOTTO = 52
    ITEM_LINGOTTO = 53
    ITEM_TRAVE_LEGNO = 54
    ITEM_PIETRA_PULI = 55
    ITEM_PELLE_PULI = 56
    ITEM_DA_CUOCERE = 57
    ITEM_TRAVE_COST = 58
    ITEM_ROCCIA_SQUA = 59
    ITEM_MART_COSTR = 60
    ITEM_ASSE_LEGNO = 61
    ITEM_ROCCIA = 62
    ITEM_ROCCIA_GREZ = 63
    ITEM_GEMMA = 64
    ITEM_RENT_DRAGON = 65
    ITEM_ERBA = 66
    ITEM_IMMOBIL = 67
    ITEM_MANGANELLO = 68
    ITEM_BENDA = 69
    ITEM_PICCOZZA = 70
    ITEM_ERBA_GREZ = 71
    ITEM_ERBA_PULITA = 72
    ITEM_BOCCETTA = 73
    ITEM_TRITAERBE = 74
    ITEM_BAVAGLIO = 75
    ITEM_CANNA = 76
    ITEM_STRUM_CUCINA = 77
    ITEM_MATTARELLO = 78
    ITEM_RIPULITURA = 79
    ITEM_PASTELLA = 80
    ITEM_PELLI = 81
    ITEM_CACCIA = 82
    ITEM_STRUM_CONCERIA = 83
    ITEM_MANDATO = 84
    ITEM_PORTA = 85
    ITEM_CONTRATTO = 86
    ITEM_TRAPPOLA = 87
    ITEM_VESTE = 88
    ITEM_RELIQUIA = 89
    ITEM_LIBRO_MAGICO_W = 90
    ITEM_LIBRO_MAGICO_S = 91
    ITEM_WEAPON_2HANDS = 92
    ITEM_TISANA_CALDA = 93
    ITEM_TISANA_FREDDA = 94
    ITEM_BENDE_UNTE = 95
    ITEM_POLVERE = 96


class LiquidType(enum.IntEnum):
    """Drink container liquid types."""
    LIQ_WATER = 0
    LIQ_BEER = 1
    LIQ_WINE = 2
    LIQ_ALE = 3
    LIQ_DARKALE = 4
    LIQ_WHISKY = 5
    LIQ_LEMONADE = 6
    LIQ_FIREBRT = 7
    LIQ_LOCALSPC = 8
    LIQ_SLIME = 9
    LIQ_MILK = 10
    LIQ_TEA = 11
    LIQ_COFFE = 12
    LIQ_BLOOD = 13
    LIQ_SALTWATER = 14
    LIQ_CLEARWATER = 15
    LIQ_CAFFELIMONE = 16


class DamageType(enum.IntEnum):
    """Damage element types."""
    DANNO_FUOCO = 0
    DANNO_GHIACCIO = 1
    DANNO_ELETTRICITA = 2
    DANNO_ACIDO = 3
    DANNO_SHAARR = 4
    DANNO_XHYPHYS = 5
    DANNO_THERION = 6
    DANNO_SILUE = 7
    DANNO_FISICO = 8


class ApplyType(enum.IntEnum):
    """Object affect apply types (APPLY_XXX)."""
    APPLY_NONE = 0
    APPLY_STR = 1
    APPLY_DEX = 2
    APPLY_INT = 3
    APPLY_WIS = 4
    APPLY_CON = 5
    APPLY_CHA = 6
    APPLY_CLASS = 7
    APPLY_LEVEL = 8
    APPLY_AGE = 9
    APPLY_CHAR_WEIGHT = 10
    APPLY_CHAR_HEIGHT = 11
    APPLY_MANA = 12
    APPLY_HIT = 13
    APPLY_MOVE = 14
    APPLY_GOLD = 15
    APPLY_EXP = 16
    APPLY_AC = 17
    APPLY_HITROLL = 18
    APPLY_DAMROLL = 19
    APPLY_SAVING_PARA = 20
    APPLY_SAVING_ROD = 21
    APPLY_SAVING_PETRI = 22
    APPLY_SAVING_BREATH = 23
    APPLY_SAVING_SPELL = 24
    APPLY_HIT_REGEN = 25
    APPLY_MANA_REGEN = 26
    APPLY_RES_FUOCO = 27
    APPLY_RES_GHIACCIO = 28
    APPLY_RES_ELETTRICITA = 29
    APPLY_RES_ACIDO = 30
    APPLY_RES_SHAARR = 31
    APPLY_RES_XHYPHYS = 32
    APPLY_RES_THERION = 33
    APPLY_RES_SILUE = 34
    APPLY_RES_FISICO = 35


class PlayerCondition(enum.IntEnum):
    """Player condition indices."""
    DRUNK = 0
    FULL = 1
    THIRST = 2


class SunState(enum.IntEnum):
    """Sun position for weather."""
    SUN_DARK = 0
    SUN_RISE = 1
    SUN_LIGHT = 2
    SUN_SET = 3


class SkyCondition(enum.IntEnum):
    """Sky weather conditions."""
    SKY_CLOUDLESS = 0
    SKY_CLOUDY = 1
    SKY_RAINING = 2
    SKY_LIGHTNING = 3


class RentCode(enum.IntEnum):
    """Rent file status codes."""
    RENT_UNDEF = 0
    RENT_CRASH = 1
    RENT_RENTED = 2
    RENT_CRYO = 3
    RENT_FORCED = 4
    RENT_TIMEDOUT = 5
    RENT_CAMP = 6


class NotorietaCase(enum.IntEnum):
    """Cases for change_notorieta."""
    KILL = 0
    TKILL = 1
    WKILL = 2
    THIEF = 3
    WANTED = 4
    QUEST = 5
    CAPTURE = 6
    CAPTURED = 7


class ConnState(enum.IntEnum):
    """Modes of connectedness: descriptor_data.state."""
    CON_PLAYING = 0
    CON_CLOSE = 1
    CON_GET_NAME = 2
    CON_NAME_CNFRM = 3
    CON_PASSWORD = 4
    CON_NEWPASSWD = 5
    CON_CNFPASSWD = 6
    CON_QSEX = 7
    CON_QCLASS = 8
    CON_RMOTD = 9
    CON_MENU = 10
    CON_EXDESC = 11
    CON_CHPWD_GETOLD = 12
    CON_CHPWD_GETNEW = 13
    CON_CHPWD_VRFY = 14
    CON_DELCNF1 = 15
    CON_DELCNF2 = 16
    CON_OEDIT = 17
    CON_REDIT = 18
    CON_ZEDIT = 19
    CON_MEDIT = 20
    CON_SEDIT = 21
    CON_QACCETTAROLL = 22
    CON_QCITTA = 23
    CON_TEXTED = 24
    CON_QMESTIERI = 25
    CON_TRIGEDIT = 26
    CON_WEDIT = 27
    CON_CONF_INIZIAZ = 28
    CON_AGPT_INIZIAZ = 29
    CON_PREMI_TASTO = 30
    CON_SCELTA_ABIL = 31
    CON_SCELTA_CULTO = 32


class ActEvent(enum.IntEnum):
    """Act event types for char_data.points_act_event[]."""
    DRAGON_RECALL_EVENT = 0
    PESCA_EVENT = 1

MAX_ACT_EVENTS: int = 2


# ---------------------------------------------------------------------------
# Level constants
# ---------------------------------------------------------------------------
LVL_IMPL: int = 91
LVL_IMPLEMENTOR: int = 90
LVL_BUILDER: int = 85
LVL_GOD: int = 80
LVL_QUEST_MASTER: int = 76
LVL_MINIBUILD: int = 75
LVL_AVATAR: int = 73
LVL_IMMORT: int = 71

LVL_GRGOD: int = LVL_GOD
LVL_FREEZE: int = LVL_IMMORT


# ===========================================================================
# IntFlag classes -- bitfield sets
# ===========================================================================


class RoomFlag(enum.IntFlag):
    """Room flags: room_data.room_flags (up to 64-bit)."""
    ROOM_DARK = 1 << 0
    ROOM_DEATH = 1 << 1
    ROOM_NOMOB = 1 << 2
    ROOM_INDOORS = 1 << 3
    ROOM_PEACEFUL = 1 << 4
    ROOM_SOUNDPROOF = 1 << 5
    ROOM_NOTRACK = 1 << 6
    ROOM_NOMAGIC = 1 << 7
    ROOM_TUNNEL = 1 << 8
    ROOM_PRIVATE = 1 << 9
    ROOM_GODROOM = 1 << 10
    ROOM_HOUSE = 1 << 11
    ROOM_HOUSE_CRASH = 1 << 12
    ROOM_ATRIUM = 1 << 13
    ROOM_OLC = 1 << 14
    ROOM_BFS_MARK = 1 << 15
    ROOM_DAMAGE = 1 << 16
    ROOM_ARENA = 1 << 17
    ROOM_LANDMARK = 1 << 18
    ROOM_NO_DRAW = 1 << 19
    ROOM_WAR_ROOM = 1 << 20
    ROOM_FORGIA = 1 << 21
    ROOM_FABBRO = 1 << 22
    ROOM_FALEGNAMERIA = 1 << 23
    ROOM_CARPENTERIA = 1 << 24
    ROOM_PIETRE_PREZIOSE = 1 << 25
    ROOM_GIOIELLERIA = 1 << 26
    ROOM_SQUADRATURA = 1 << 27
    ROOM_PRISON = 1 << 28
    ROOM_ERBORISTERIA = 1 << 29
    ROOM_LAB_ALCHIMIA = 1 << 30
    ROOM_MULINO_RIPUL = 1 << 31
    ROOM_CUCINA = 1 << 32
    ROOM_SCUOIATURA = 1 << 33
    ROOM_CONCERIA = 1 << 34
    ROOM_CONSTRUZIONE = 1 << 35
    ROOM_STOP_COSTR = 1 << 36
    ROOM_FIRST_ROOM = 1 << 37
    ROOM_NOSELL = 1 << 38
    ROOM_NOBUY = 1 << 39
    ROOM_ZECCA = 1 << 40
    ROOM_TRADE = 1 << 41
    ROOM_MAGAZZINO = 1 << 42
    ROOM_EDIFICABILE = 1 << 43
    ROOM_TEMPIO = 1 << 44
    ROOM_NOWRAITH = 1 << 45
    ROOM_DAMAGE_FUOCO = 1 << 46
    ROOM_DAMAGE_ACQUA = 1 << 47
    ROOM_DAMAGE_ARIA = 1 << 48
    ROOM_DAMAGE_TERRA = 1 << 49
    ROOM_BIG_HOUSE = 1 << 50


class ExitInfo(enum.IntFlag):
    """Exit flags: room_direction_data.exit_info."""
    EX_ISDOOR = 1 << 0
    EX_CLOSED = 1 << 1
    EX_LOCKED = 1 << 2
    EX_PICKPROOF = 1 << 3
    EX_HIDDEN = 1 << 4


class PlayerFlag(enum.IntFlag):
    """Player flags: char_data.char_specials.act (for PCs)."""
    PLR_KILLER = 1 << 0
    PLR_THIEF = 1 << 1
    PLR_FROZEN = 1 << 2
    PLR_DONTSET = 1 << 3
    PLR_WRITING = 1 << 4
    PLR_MAILING = 1 << 5
    PLR_CRASH = 1 << 6
    PLR_SITEOK = 1 << 7
    PLR_NOSHOUT = 1 << 8
    PLR_NOTITLE = 1 << 9
    PLR_DELETED = 1 << 10
    PLR_LOADROOM = 1 << 11
    PLR_NOWIZLIST = 1 << 12
    PLR_NODELETE = 1 << 13
    PLR_INVSTART = 1 << 14
    PLR_CRYO = 1 << 15
    PLR_QUESTOR = 1 << 16
    PLR_TKILLER = 1 << 17
    PLR_WAR_KILLER = 1 << 18
    PLR_WANTED = 1 << 19
    PLR_MUTO = 1 << 20
    PLR_NOTAIO = 1 << 21
    PLR_MULTIPLAYER = 1 << 22
    PLR_TRUSTED = 1 << 23
    PLR_FANTASMA = 1 << 24
    PLR_MODIFICATO = 1 << 25
    PLR_CONCENTRATO = 1 << 26
    PLR_ALL_OLC = 1 << 27
    PLR_CATARSI = 1 << 28
    PLR_GO_GILDA = 1 << 29
    PLR_PAPA = 1 << 30


class MobFlag(enum.IntFlag):
    """Mobile flags: char_data.char_specials.act (for NPCs)."""
    MOB_SPEC = 1 << 0
    MOB_SENTINEL = 1 << 1
    MOB_SCAVENGER = 1 << 2
    MOB_ISNPC = 1 << 3
    MOB_AWARE = 1 << 4
    MOB_AGGRESSIVE = 1 << 5
    MOB_STAY_ZONE = 1 << 6
    MOB_WIMPY = 1 << 7
    MOB_AGGR_EVIL = 1 << 8
    MOB_AGGR_GOOD = 1 << 9
    MOB_AGGR_NEUTRAL = 1 << 10
    MOB_MEMORY = 1 << 11
    MOB_HELPER = 1 << 12
    MOB_NOCHARM = 1 << 13
    MOB_NOSUMMON = 1 << 14
    MOB_NOSLEEP = 1 << 15
    MOB_NOBASH = 1 << 16
    MOB_NOBLIND = 1 << 17
    MOB_WILDHUNT = 1 << 18
    MOB_QUEST = 1 << 19
    MOB_QUESTMASTER = 1 << 20
    MOB_ASSASSIN = 1 << 21
    MOB_HUNTER = 1 << 22
    MOB_MOUNTABLE = 1 << 23
    MOB_HARD_TAME = 1 << 24
    MOB_DRAGONBREATH = 1 << 25
    MOB_SAVEINV = 1 << 26
    MOB_SHOPKEEPER = 1 << 27
    MOB_BOUNTY = 1 << 28
    MOB_NOKILL = 1 << 29
    MOB_CIVILIAN = 1 << 30
    MOB_CRIMINAL = 1 << 31
    MOB_SEARCHER = 1 << 32
    MOB_SAVE = 1 << 33
    MOB_GO_FAST = 1 << 34
    MOB_SELVAGGINA = 1 << 35
    MOB_RIS_CARNE = 1 << 36
    MOB_RIS_PELLE = 1 << 37
    MOB_RIS_STOFFA = 1 << 38
    MOB_RIS_PELLICCIA = 1 << 39
    MOB_RIS_SCAGLIE = 1 << 40
    MOB_BGUARD = 1 << 41
    MOB_NECRO = 1 << 42
    MOB_AGGR_NO_PROP = 1 << 43
    MOB_AGGR_NO_AL_CLAN = 1 << 44
    MOB_AGGR_NO_EN_CLAN = 1 << 45
    MOB_AGGR_NO_PC_CLAN = 1 << 46
    MOB_AGGR_NO_CLAN = 1 << 47
    MOB_AGGR_VAS_CLAN = 1 << 48
    MOB_AMMAESTRABILE = 1 << 49
    MOB_WORKER = 1 << 50
    MOB_CRIMINALHELPER = 1 << 51
    MOB_CRASH = 1 << 52
    MOB_SAVE_DELETE = 1 << 53
    MOB_CRASH_EQ = 1 << 54
    MOB_NOEXP = 1 << 55
    MOB_STIPENDIO = 1 << 56
    MOB_STIPENDIO_EQ = 1 << 57
    MOB_ESERCITO = 1 << 58
    MOB_NODECAPITA = 1 << 59


class PreferenceFlag(enum.IntFlag):
    """Player preference flags: char_data.player_specials.pref."""
    PRF_BRIEF = 1 << 0
    PRF_COMPACT = 1 << 1
    PRF_DEAF = 1 << 2
    PRF_NOTELL = 1 << 3
    PRF_DISPHP = 1 << 4
    PRF_DISPMANA = 1 << 5
    PRF_DISPMOVE = 1 << 6
    PRF_AUTOEXIT = 1 << 7
    PRF_NOHASSLE = 1 << 8
    PRF_QUEST = 1 << 9
    PRF_SUMMONABLE = 1 << 10
    PRF_NOREPEAT = 1 << 11
    PRF_HOLYLIGHT = 1 << 12
    PRF_COLOR_1 = 1 << 13
    PRF_COLOR_2 = 1 << 14
    PRF_NOWIZ = 1 << 15
    PRF_LOG1 = 1 << 16
    PRF_LOG2 = 1 << 17
    PRF_NOAUCT = 1 << 18
    PRF_NOGOSS = 1 << 19
    PRF_NOGRATZ = 1 << 20
    PRF_ROOMFLAGS = 1 << 21
    PRF_AFK = 1 << 22
    PRF_DISPGOLD = 1 << 23
    PRF_DISPXP = 1 << 24
    PRF_DISPDAM = 1 << 25
    PRF_AUTODIR = 1 << 26
    PRF_ARENA = 1 << 27
    PRF_SOUNDS = 1 << 28
    PRF_HIDE_SNEAK = 1 << 29
    PRF_NO_EROE = 1 << 30
    PRF_DISPCAV = 1 << 31
    PRF_RPG = 1 << 32
    PRF_NOKILL = 1 << 33
    PRF_REGNOTELL = 1 << 34
    PRF_NOC = 1 << 35
    PRF_DISPSTATIC = 1 << 36


class AffectedBy(enum.IntFlag):
    """Affect flags bank 0: char_data.char_specials.saved.affected_by[0].

    The Dalila 4-bank bitvector system: affects are spread across 4 banks
    of 64 bits each. Bank 0 has bits 0..63, bank 1 has the next set, etc.
    The BITV_* constants identify which bank each affect belongs to.
    """
    AFF_BLIND = 1 << 0
    AFF_INVISIBLE = 1 << 1
    AFF_DETECT_ALIGN = 1 << 2
    AFF_DETECT_INVIS = 1 << 3
    AFF_DETECT_MAGIC = 1 << 4
    AFF_SENSE_LIFE = 1 << 5
    AFF_WATERWALK = 1 << 6
    AFF_SANCTUARY = 1 << 7
    AFF_GROUP = 1 << 8
    AFF_CURSE = 1 << 9
    AFF_INFRAVISION = 1 << 10
    AFF_POISON = 1 << 11
    AFF_PROTECT_EVIL = 1 << 12
    AFF_PROTECT_GOOD = 1 << 13
    AFF_SLEEP = 1 << 14
    AFF_NOTRACK = 1 << 15
    AFF_MARK = 1 << 16
    AFF_PASSDOOR = 1 << 17
    AFF_SNEAK = 1 << 18
    AFF_HIDE = 1 << 19
    AFF_FIRESHD = 1 << 20
    AFF_CHARM = 1 << 21
    AFF_FLYING = 1 << 22
    AFF_WATERBREATH = 1 << 23
    AFF_PROT_FIRE = 1 << 24
    AFF_SHIELD = 1 << 25
    AFF_DEATHDANCE = 1 << 26
    AFF_MIRRORIMAGE = 1 << 27
    AFF_BLINK = 1 << 28
    AFF_WIZEYE = 1 << 29
    AFF_PARALIZE = 1 << 30
    AFF_TAMED = 1 << 31
    AFF_ACCAMPATO = 1 << 32
    AFF_TRAMORTITO = 1 << 33
    AFF_IMMOBIL = 1 << 34
    AFF_CAPTURING = 1 << 35
    AFF_TRANSPORTED = 1 << 36
    AFF_PROTECT_LIGHT = 1 << 37
    AFF_DET_SNEAK = 1 << 38
    AFF_SILENCE = 1 << 39
    AFF_DISGUISE = 1 << 40
    AFF_ANTIMAGIC = 1 << 41
    AFF_AID = 1 << 42
    AFF_CONGIUNZIONE = 1 << 43
    AFF_CRITICAL_TESTA_1 = 1 << 44
    AFF_CRITICAL_BRACCIO_D_1 = 1 << 45
    AFF_CRITICAL_BRACCIO_S_1 = 1 << 46
    AFF_CRITICAL_TORSO_1 = 1 << 47
    AFF_CRITICAL_GAMBA_D_1 = 1 << 48
    AFF_CRITICAL_GAMBA_S_1 = 1 << 49
    AFF_CRITICAL_TESTA_2 = 1 << 50
    AFF_CRITICAL_BRACCIO_D_2 = 1 << 51
    AFF_CRITICAL_BRACCIO_S_2 = 1 << 52
    AFF_CRITICAL_TORSO_2 = 1 << 53
    AFF_CRITICAL_GAMBA_D_2 = 1 << 54
    AFF_CRITICAL_GAMBA_S_2 = 1 << 55
    AFF_CRITICAL_TESTA_3 = 1 << 56
    AFF_CRITICAL_BRACCIO_D_3 = 1 << 57
    AFF_CRITICAL_BRACCIO_S_3 = 1 << 58
    AFF_CRITICAL_TORSO_3 = 1 << 59
    AFF_CRITICAL_GAMBA_D_3 = 1 << 60
    AFF_CRITICAL_GAMBA_S_3 = 1 << 61
    AFF_FERITO = 1 << 62
    AFF_ENDURANCE = 1 << 63


class AffectedByBank1(enum.IntFlag):
    """Affect flags bank 1 (BITV_ = 1)."""
    AFF_BURNED = 1 << 0
    AFF_CHILLED = 1 << 1
    AFF_LEVITATE = 1 << 2
    AFF_RAFFREDDATO = 1 << 3
    AFF_APPESTATO = 1 << 4
    AFF_UBRIACO = 1 << 5
    AFF_MALEDETTO_SHAARR = 1 << 6
    AFF_PIAGATO = 1 << 7
    AFF_MALEDETTO_XHYPHYS = 1 << 8
    AFF_ADDORMENTATO = 1 << 9


class AffectedByBank2(enum.IntFlag):
    """Affect flags bank 2 (BITV_ = 2). Currently only placeholder."""
    AFF_VUOTO_2 = 1 << 0


class AffectedByBank3(enum.IntFlag):
    """Affect flags bank 3 (BITV_ = 3). Currently only placeholder."""
    AFF_VUOTO_3 = 1 << 0


# Bitvector bank mapping: affect name -> bank index (0-3)
# All bank-0 affects have BITV_ = 0, bank-1 affects have BITV_ = 1, etc.
# This dict is used by the Bitvector class to route IS_SET/SET_BIT operations.
AFFECT_BANK: dict[str, int] = {
    # Bank 0 (all the main affects)
    "AFF_BLIND": 0, "AFF_INVISIBLE": 0, "AFF_DETECT_ALIGN": 0,
    "AFF_DETECT_INVIS": 0, "AFF_DETECT_MAGIC": 0, "AFF_SENSE_LIFE": 0,
    "AFF_WATERWALK": 0, "AFF_SANCTUARY": 0, "AFF_GROUP": 0, "AFF_CURSE": 0,
    "AFF_INFRAVISION": 0, "AFF_POISON": 0, "AFF_PROTECT_EVIL": 0,
    "AFF_PROTECT_GOOD": 0, "AFF_SLEEP": 0, "AFF_NOTRACK": 0, "AFF_MARK": 0,
    "AFF_PASSDOOR": 0, "AFF_SNEAK": 0, "AFF_HIDE": 0, "AFF_FIRESHD": 0,
    "AFF_CHARM": 0, "AFF_FLYING": 0, "AFF_WATERBREATH": 0,
    "AFF_PROT_FIRE": 0, "AFF_SHIELD": 0, "AFF_DEATHDANCE": 0,
    "AFF_MIRRORIMAGE": 0, "AFF_BLINK": 0, "AFF_WIZEYE": 0,
    "AFF_PARALIZE": 0, "AFF_TAMED": 0, "AFF_ACCAMPATO": 0,
    "AFF_TRAMORTITO": 0, "AFF_IMMOBIL": 0, "AFF_CAPTURING": 0,
    "AFF_TRANSPORTED": 0, "AFF_PROTECT_LIGHT": 0, "AFF_DET_SNEAK": 0,
    "AFF_SILENCE": 0, "AFF_DISGUISE": 0, "AFF_ANTIMAGIC": 0,
    "AFF_AID": 0, "AFF_CONGIUNZIONE": 0,
    "AFF_CRITICAL_TESTA_1": 0, "AFF_CRITICAL_BRACCIO_D_1": 0,
    "AFF_CRITICAL_BRACCIO_S_1": 0, "AFF_CRITICAL_TORSO_1": 0,
    "AFF_CRITICAL_GAMBA_D_1": 0, "AFF_CRITICAL_GAMBA_S_1": 0,
    "AFF_CRITICAL_TESTA_2": 0, "AFF_CRITICAL_BRACCIO_D_2": 0,
    "AFF_CRITICAL_BRACCIO_S_2": 0, "AFF_CRITICAL_TORSO_2": 0,
    "AFF_CRITICAL_GAMBA_D_2": 0, "AFF_CRITICAL_GAMBA_S_2": 0,
    "AFF_CRITICAL_TESTA_3": 0, "AFF_CRITICAL_BRACCIO_D_3": 0,
    "AFF_CRITICAL_BRACCIO_S_3": 0, "AFF_CRITICAL_TORSO_3": 0,
    "AFF_CRITICAL_GAMBA_D_3": 0, "AFF_CRITICAL_GAMBA_S_3": 0,
    "AFF_FERITO": 0, "AFF_ENDURANCE": 0,
    # Bank 1
    "AFF_BURNED": 1, "AFF_CHILLED": 1, "AFF_LEVITATE": 1,
    "AFF_RAFFREDDATO": 1, "AFF_APPESTATO": 1, "AFF_UBRIACO": 1,
    "AFF_MALEDETTO_SHAARR": 1, "AFF_PIAGATO": 1,
    "AFF_MALEDETTO_XHYPHYS": 1, "AFF_ADDORMENTATO": 1,
    # Bank 2
    "AFF_VUOTO_2": 2,
    # Bank 3
    "AFF_VUOTO_3": 3,
}


class ItemWearFlag(enum.IntFlag):
    """Take/Wear flags: obj_data.obj_flags.wear_flags."""
    ITEM_WEAR_TAKE = 1 << 0
    ITEM_WEAR_FINGER = 1 << 1
    ITEM_WEAR_NECK = 1 << 2
    ITEM_WEAR_BODY = 1 << 3
    ITEM_WEAR_HEAD = 1 << 4
    ITEM_WEAR_LEGS = 1 << 5
    ITEM_WEAR_FEET = 1 << 6
    ITEM_WEAR_HANDS = 1 << 7
    ITEM_WEAR_ARMS = 1 << 8
    ITEM_WEAR_SHIELD = 1 << 9
    ITEM_WEAR_ABOUT = 1 << 10
    ITEM_WEAR_WAIST = 1 << 11
    ITEM_WEAR_WRIST = 1 << 12
    ITEM_WEAR_WIELD = 1 << 13
    ITEM_WEAR_HOLD = 1 << 14
    ITEM_WEAR_LOBSX = 1 << 15
    ITEM_WEAR_SPALLE = 1 << 16
    ITEM_WEAR_IMMOBIL = 1 << 17
    ITEM_WEAR_EYE = 1 << 18
    ITEM_WEAR_BOCCA = 1 << 19
    ITEM_WEAR_ALTRO1 = 1 << 20
    ITEM_WEAR_HANG = 1 << 21
    ITEM_WEAR_VESTE = 1 << 22
    ITEM_WEAR_RELIQUIA = 1 << 23


class ItemExtraFlag(enum.IntFlag):
    """Extra object flags: obj_data.obj_flags.extra_flags."""
    ITEM_GLOW = 1 << 0
    ITEM_HUM = 1 << 1
    ITEM_NORENT = 1 << 2
    ITEM_NODONATE = 1 << 3
    ITEM_NOINVIS = 1 << 4
    ITEM_INVISIBLE = 1 << 5
    ITEM_MAGIC = 1 << 6
    ITEM_NODROP = 1 << 7
    ITEM_BLESS = 1 << 8
    ITEM_ANTI_GOOD = 1 << 9
    ITEM_ANTI_EVIL = 1 << 10
    ITEM_ANTI_NEUTRAL = 1 << 11
    ITEM_ANTI_MAGIC_USER = 1 << 12
    ITEM_ANTI_CLERIC = 1 << 13
    ITEM_ANTI_THIEF = 1 << 14
    ITEM_ANTI_WARRIOR = 1 << 15
    ITEM_NOSELL = 1 << 16
    ITEM_ANTI_PELOI = 1 << 17
    ITEM_LIVE_GRENADE = 1 << 18
    ITEM_NOLOCATE = 1 << 19
    ITEM_NO_5_LIV = 1 << 20
    ITEM_NO_10_LIV = 1 << 21
    ITEM_NO_20_LIV = 1 << 22
    ITEM_NO_25_LIV = 1 << 23
    ITEM_NO_30_LIV = 1 << 24
    ITEM_NO_40_LIV = 1 << 25
    ITEM_RESTRING = 1 << 26
    ITEM_ISCORPSE = 1 << 27
    ITEM_FORGED = 1 << 28
    ITEM_AFFILATO = 1 << 29
    ITEM_RINOM_ALIAS = 1 << 30
    ITEM_RINOM_NAME = 1 << 31
    ITEM_RINOM_DESCR = 1 << 32
    ITEM_NO_IDENT = 1 << 33
    ITEM_QUEST = 1 << 34


class ContainerFlag(enum.IntFlag):
    """Container flags: value[1] for containers."""
    CONT_CLOSEABLE = 1 << 0
    CONT_PICKPROOF = 1 << 1
    CONT_CLOSED = 1 << 2
    CONT_LOCKED = 1 << 3


# ===========================================================================
# Spell and skill constants (from spells.h)
# ===========================================================================

class Spell(enum.IntEnum):
    """Spell numbers. From spells.h."""
    SPELL_RESERVED_DBC = 0
    SPELL_ARMOR = 1
    SPELL_TELEPORT = 2
    SPELL_BLESS = 3
    SPELL_BLINDNESS = 4
    SPELL_BURNING_HANDS = 5
    SPELL_CALL_LIGHTNING = 6
    SPELL_CHARM = 7
    SPELL_CHILL_TOUCH = 8
    SPELL_CLONE = 9
    SPELL_COLOR_SPRAY = 10
    SPELL_CONTROL_WEATHER = 11
    SPELL_CREATE_FOOD = 12
    SPELL_CREATE_WATER = 13
    SPELL_CURE_BLIND = 14
    SPELL_CURE_CRITIC = 15
    SPELL_CURE_LIGHT = 16
    SPELL_CURSE = 17
    SPELL_DETECT_ALIGN = 18
    SPELL_DETECT_INVIS = 19
    SPELL_DETECT_MAGIC = 20
    SPELL_DETECT_POISON = 21
    SPELL_DISPEL_EVIL = 22
    SPELL_EARTHQUAKE = 23
    SPELL_ENCHANT_WEAPON = 24
    SPELL_ENERGY_DRAIN = 25
    SPELL_FIREBALL = 26
    SPELL_HARM = 27
    SPELL_HEAL = 28
    SPELL_INVISIBLE = 29
    SPELL_LIGHTNING_BOLT = 30
    SPELL_LOCATE_OBJECT = 31
    SPELL_MAGIC_MISSILE = 32
    SPELL_POISON = 33
    SPELL_PROT_FROM_EVIL = 34
    SPELL_REMOVE_CURSE = 35
    SPELL_SANCTUARY = 36
    SPELL_SHOCKING_GRASP = 37
    SPELL_SLEEP = 38
    SPELL_STRENGTH = 39
    SPELL_SUMMON = 40
    SPELL_VENTRILOQUATE = 41
    SPELL_WORD_OF_RECALL = 42
    SPELL_REMOVE_POISON = 43
    SPELL_SENSE_LIFE = 44
    SPELL_ANIMATE_DEAD = 45
    SPELL_DISPEL_GOOD = 46
    SPELL_GROUP_ARMOR = 47
    SPELL_GROUP_HEAL = 48
    SPELL_GROUP_RECALL = 49
    SPELL_INFRAVISION = 50
    SPELL_WATERWALK = 51
    SPELL_RELOCATE = 52
    SPELL_DISINTEGRATE = 53
    SPELL_FLY = 54
    SPELL_MINUTE_METEOR = 55
    SPELL_CONE_OF_COLD = 56
    SPELL_AREA_LIGHTNING = 57
    SPELL_FIRE_BREATH = 58
    SPELL_GAS_BREATH = 59
    SPELL_FROST_BREATH = 60
    SPELL_ACID_BREATH = 61
    SPELL_LIGHTNING_BREATH = 62
    SPELL_BLADEBARRIER = 63
    SPELL_PEACE = 64
    SPELL_PIDENTIFY = 65
    SPELL_ACID_ARROW = 66
    SPELL_FLAME_ARROW = 67
    SPELL_LEVITATE = 68
    SPELL_PROT_FIRE = 69
    SPELL_WATERBREATH = 70
    SPELL_BARKSKIN = 71
    SPELL_STONESKIN = 72
    SPELL_GROUP_FLY = 73
    SPELL_GROUP_INVIS = 74
    SPELL_GROUP_PROT_EVIL = 75
    SPELL_GROUP_WATBREATH = 76
    SPELL_CURE_SERIOUS = 77
    SPELL_MONSUM_I = 78
    SPELL_MONSUM_II = 79
    SPELL_MONSUM_III = 80
    SPELL_MONSUM_IV = 81
    SPELL_MONSUM_V = 82
    SPELL_CONJ_ELEMENTAL = 83
    SPELL_SHIELD = 84
    SPELL_MIRROR_IMAGE = 85
    SPELL_BLINK = 86
    SPELL_DEATHDANCE = 87
    SPELL_PORTAL = 88
    SPELL_WRAITHFORM = 89
    SPELL_CREATE_LIGHT = 90
    SPELL_FEAST = 91
    SPELL_HEROES_FEAST = 92
    SPELL_REFRESH = 93
    SPELL_CONTINUAL_LIGHT = 94
    SPELL_LOCATE_TARGET = 95
    SPELL_FEAR = 96
    SPELL_FIRESHD = 97
    SPELL_DISPEL_MAGIC = 98
    SPELL_WIZEYE = 99
    SPELL_MATER_ARMOUR = 100
    SPELL_MATER_WEAP = 101
    SPELL_PARALIZE = 102
    SPELL_CALL_DRAGON = 103
    SPELL_PROTECT_LIGHT = 104
    SPELL_DET_SNEAK = 105
    SPELL_SILENCE = 106
    SPELL_ANTIMAGIC = 107
    SPELL_DISGUISE = 108
    SPELL_AID = 109
    SPELL_CONGIUNZIONE = 110
    SPELL_ENCHANT_WOOD = 111
    SPELL_ENDURANCE = 112
    SPELL_TIME_DISTORTION = 113

MAX_SPELLS: int = 130


class Skill(enum.IntEnum):
    """Skill numbers. From spells.h, starting at MAX_SPELLS+1."""
    SKILL_BACKSTAB = 131
    SKILL_BASH = 132
    SKILL_HIDE = 133
    SKILL_KICK = 134
    SKILL_PICK_LOCK = 135
    SKILL_SPOT = 136
    SKILL_RESCUE = 137
    SKILL_SNEAK = 138
    SKILL_STEAL = 139
    SKILL_TRACK = 140
    SKILL_DISARM = 141
    SKILL_SECOND_ATTACK = 142
    SKILL_THIRD_ATTACK = 143
    SKILL_ENH_DAMAGE = 144
    SKILL_PARRY = 145
    SKILL_DODGE = 146
    SKILL_COOK = 147
    SKILL_FILLET = 148
    SKILL_BREW = 149
    SKILL_FORGE = 150
    SKILL_SCRIBE = 151
    SKILL_SCAN = 152
    SKILL_REPAIR = 153
    SKILL_FOURTH_ATTACK = 154
    SKILL_FIFTH_ATTACK = 155
    SKILL_SPY = 156
    SKILL_RETREAT = 157
    SKILL_THROW = 158
    SKILL_BOW = 159
    SKILL_SLING = 160
    SKILL_CROSSBOW = 161
    SKILL_READ_MAGIC = 162
    SKILL_WRITE_MAGIC = 163
    SKILL_PEEP = 164
    SKILL_PUNCH = 165
    SECOND_WEAPON = 166
    SECOND_BACKSTAB = 167
    SKILL_BASH_LOCK = 168
    SKILL_COLPO_MORTALE = 169


# NPC/object spells (201+)
SPELL_IDENTIFY: int = 201
SPELL_NULLA: int = 202
DISEASE_RAFFREDDORE: int = 203
DISEASE_PESTE: int = 204
DISEASE_BACCO: int = 205
DISEASE_SHAARR: int = 206
DISEASE_PIAGHE: int = 207
DISEASE_XHYPHYS: int = 208
DISEASE_MORFEO: int = 209
TOP_SPELL_DEFINE: int = 299


class Proficienza(enum.IntEnum):
    """Proficiency (mestieri) numbers. From spells.h."""
    PROF_RESERVED_DBC = 0
    PROF_MONTARE = 1
    PROF_CAVALCARE = 2
    PROF_DOMARE = 3
    PROF_CACCIARE = 4
    PROF_ADDESTRATORE = 5
    PROF_SARTO = 6
    PROF_COLTIVARE = 7
    PROF_CUCINARE = 8
    PROF_MINATORE = 9
    PROF_FABBRO = 10
    PROF_FALEGNAMERIA = 11
    PROF_CARPENTERIA = 12
    PROF_GIOIELLERIA = 13
    PROF_ARCHITETTURA = 14
    PROF_ERBORISTERIA = 15
    PROF_ALCHIMIA = 16
    PROF_PESCATORE = 17

TOT_PROF_MESTIERI: int = 17


class Abilita(enum.IntEnum):
    """Ability numbers. From spells.h."""
    ABIL_RESERVED = 0
    ABIL_SPADA = 1
    ABIL_ASCIA = 2
    ABIL_PUGNALE = 3
    ABIL_MAZZA = 4
    ABIL_LANCIA = 5
    ABIL_SCUDO = 6
    ABIL_ARM_BASE = 7
    ABIL_ARM_MEDIA = 8
    ABIL_ARM_PESANTE = 9
    ABIL_TRATTATIVA = 10
    ABIL_RIPARAZIONE = 11
    ABIL_BODYBUILDING = 12
    ABIL_MEDITAZIONE = 13
    ABIL_TRAPPOLE = 14
    ABIL_STUDIO = 15
    ABIL_DIPLOMAZIA = 16
    ABIL_PERCEZIONE = 17
    ABIL_REGENERATION = 18
    ABIL_AGGUATO = 19

TOP_ABILITA_DEFINE: int = 20
MAX_ABILITA_LEVELS: int = 15
NUM_ABILITA_TITLES: int = 3

# Abilita mastery levels
BASE: int = 0
EXPERT: int = 1
MASTER: int = 2
EXPERT_LIV: int = 9
MASTER_LIV: int = 15

# Damage multipliers for abilita
SINGLE_DAM: int = 1
DOUBLE_DAM: int = 2
TRIPLE_DAM: int = 3


# Skill/spell/abil nature constants
SPELLSKILL: int = 0
PROFICIENZE: int = 1
ABILITA_NATURE: int = 2  # "ABILITA" in C, renamed to avoid conflict


class WeaponAttackType(enum.IntEnum):
    """Weapon attack types. From spells.h."""
    TYPE_HIT = 300
    TYPE_STING = 301
    TYPE_WHIP = 302
    TYPE_SLASH = 303
    TYPE_BITE = 304
    TYPE_BLUDGEON = 305
    TYPE_CRUSH = 306
    TYPE_POUND = 307
    TYPE_CLAW = 308
    TYPE_MAUL = 309
    TYPE_THRASH = 310
    TYPE_PIERCE = 311
    TYPE_BLAST = 312
    TYPE_PUNCH = 313
    TYPE_STAB = 314
    TYPE_SLAY = 315
    TYPE_HUNGER = 398
    TYPE_SUFFERING = 399
    TYPE_TRAPPOLE = 400
    TYPE_ROOM_DAMAGE_FUOCO = 401
    TYPE_ROOM_DAMAGE_ACQUA = 402
    TYPE_ROOM_DAMAGE_TERRA = 403
    TYPE_ROOM_DAMAGE_ARIA = 404


class SavingThrow(enum.IntEnum):
    """Saving throw types. From spells.h."""
    SAVING_NONE = 0
    SAVING_STR = 1
    SAVING_CON = 2
    SAVING_DEX = 3
    SAVING_INT = 4
    SAVING_WIS = 5
    SAVING_CHA = 6

# Legacy saving throws
SAVING_NEVER: int = -1
SAVING_PARA: int = 0
SAVING_ROD: int = 1
SAVING_PETRI: int = 2
SAVING_BREATH: int = 3
SAVING_SPELL: int = 4


class CastType(enum.IntEnum):
    """Casting source types."""
    CAST_UNDEFINED = -1
    CAST_SPELL = 0
    CAST_POTION = 1
    CAST_WAND = 2
    CAST_STAFF = 3
    CAST_SCROLL = 4
    CAST_BREATH = 5


class MagType(enum.IntFlag):
    """Magic routine flags."""
    MAG_DAMAGE = 1 << 0
    MAG_AFFECTS = 1 << 1
    MAG_UNAFFECTS = 1 << 2
    MAG_POINTS = 1 << 3
    MAG_ALTER_OBJS = 1 << 4
    MAG_GROUPS = 1 << 5
    MAG_MASSES = 1 << 6
    MAG_AREAS = 1 << 7
    MAG_SUMMONS = 1 << 8
    MAG_CREATIONS = 1 << 9
    MAG_MANUAL = 1 << 10
    MAG_PRE_COSTO = 1 << 11


class SpellTarget(enum.IntFlag):
    """Spell target types."""
    TAR_IGNORE = 1
    TAR_CHAR_ROOM = 2
    TAR_CHAR_WORLD = 4
    TAR_FIGHT_SELF = 8
    TAR_FIGHT_VICT = 16
    TAR_SELF_ONLY = 32
    TAR_NOT_SELF = 64
    TAR_OBJ_INV = 128
    TAR_OBJ_ROOM = 256
    TAR_OBJ_WORLD = 512
    TAR_OBJ_EQUIP = 1024
    TAR_NOT_WRITE = 2048


# Distortion rooms
ROOM_DISTORSIONE_1: int = 82
ROOM_DISTORSIONE_2: int = 83
ROOM_DISTORSIONE_3: int = 84

DEFAULT_STAFF_LVL: int = 12
DEFAULT_WAND_LVL: int = 12


# ===========================================================================
# Trigger types (from dg_scripts.h)
# ===========================================================================

MOB_TRIGGER: int = 0
OBJ_TRIGGER: int = 1
WLD_TRIGGER: int = 2
DG_NO_TRIG: int = 256


class MobTrigType(enum.IntFlag):
    """Mob trigger types."""
    MTRIG_GLOBAL = 1 << 0
    MTRIG_RANDOM = 1 << 1
    MTRIG_COMMAND = 1 << 2
    MTRIG_SPEECH = 1 << 3
    MTRIG_ACT = 1 << 4
    MTRIG_DEATH = 1 << 5
    MTRIG_GREET = 1 << 6
    MTRIG_GREET_ALL = 1 << 7
    MTRIG_ENTRY = 1 << 8
    MTRIG_RECEIVE = 1 << 9
    MTRIG_FIGHT = 1 << 10
    MTRIG_HITPRCNT = 1 << 11
    MTRIG_BRIBE = 1 << 12
    MTRIG_LOAD = 1 << 13
    MTRIG_MEMORY = 1 << 14


class ObjTrigType(enum.IntFlag):
    """Object trigger types."""
    OTRIG_GLOBAL = 1 << 0
    OTRIG_RANDOM = 1 << 1
    OTRIG_COMMAND = 1 << 2
    OTRIG_TIMER = 1 << 5
    OTRIG_GET = 1 << 6
    OTRIG_DROP = 1 << 7
    OTRIG_GIVE = 1 << 8
    OTRIG_WEAR = 1 << 9
    OTRIG_LOAD = 1 << 13


class WldTrigType(enum.IntFlag):
    """World/room trigger types."""
    WTRIG_GLOBAL = 1 << 0
    WTRIG_RANDOM = 1 << 1
    WTRIG_COMMAND = 1 << 2
    WTRIG_SPEECH = 1 << 3
    WTRIG_ENTER = 1 << 6
    WTRIG_DROP = 1 << 7


# ===========================================================================
# Game timing constants
# ===========================================================================

OPT_USEC: int = 100000  # 10 game loop passes per second
PASSES_PER_SEC: int = 1000000 // OPT_USEC  # = 10

PULSE_ZONE: int = 10 * PASSES_PER_SEC      # = 100
PULSE_MOBILE: int = 10 * PASSES_PER_SEC    # = 100
PULSE_VIOLENCE: int = 3 * PASSES_PER_SEC   # = 30
PULSE_DG_SCRIPT: int = 13 * PASSES_PER_SEC  # = 130

CAN_NOT_SHOW_ROOM: int = 0
CAN_SHOW_ROOM: int = 1


# ===========================================================================
# Size and limit constants
# ===========================================================================

SMALL_BUFSIZE: int = 1024
LARGE_BUFSIZE: int = 12 * 1024
GARBAGE_SPACE: int = 32
HISTORY_SIZE: int = 5
MAX_STRING_LENGTH: int = 8192
MAX_INPUT_LENGTH: int = 256
MAX_RAW_INPUT_LENGTH: int = 512
MAX_MESSAGES: int = 60
MAX_NAME_LENGTH: int = 20
MAX_PWD_LENGTH: int = 10
MAX_TITLE_LENGTH: int = 80
MAX_POOF_LENGTH: int = 80
HOST_LENGTH: int = 30
SHTDESC_LENGTH: int = 50
LNGDESC_LENGTH: int = 150
EXDSCR_LENGTH: int = 240
MAX_TONGUE: int = 3
MAX_SKILLS: int = 200
MAX_PROFICIENZE: int = 100
MAX_ABILITA: int = 100
MAX_AFFECT: int = 32
MAX_OBJ_AFFECT: int = 6
NUM_OBJ_VAL_POSITIONS: int = 10
TELLS_STORED: int = 10
MAX_GBL_VAR_SAVED: int = 128
MAX_NAME_VAR_LENGTH: int = 20
MAX_VAR_LENGTH: int = 150
NUM_STARTROOMS: int = 6
MAX_SPEC: int = 48
MAX_SCRIPT_DEPTH: int = 10

# MUD time constants (from utils.h)
STARTING_YEAR: int = 1000
SECS_PER_MUD_HOUR: int = 75
SECS_PER_MUD_DAY: int = 24 * SECS_PER_MUD_HOUR
SECS_PER_MUD_MONTH: int = 35 * SECS_PER_MUD_DAY
SECS_PER_MUD_YEAR: int = 17 * SECS_PER_MUD_MONTH
SECS_PER_REAL_MIN: int = 60
SECS_PER_REAL_HOUR: int = 60 * SECS_PER_REAL_MIN
SECS_PER_REAL_DAY: int = 24 * SECS_PER_REAL_HOUR
SECS_PER_REAL_YEAR: int = 365 * SECS_PER_REAL_DAY

# Mestieri
RANGE_CACCIATORE: int = 3


# ===========================================================================
# DB boot modes (from db.h)
# ===========================================================================

DB_BOOT_WLD: int = 0
DB_BOOT_MOB: int = 1
DB_BOOT_OBJ: int = 2
DB_BOOT_ZON: int = 3
DB_BOOT_SHP: int = 4
DB_BOOT_HLP: int = 5
DB_BOOT_TRG: int = 6

# Wilderness zone types (from wilderness.h)
ZONE_NORMAL_AREA: int = 0
ZONE_MINIWILD: int = 2

# Mudlog levels (from utils.h)
OFF: int = 0
BRF: int = 1
NRM: int = 2
CMP: int = 3

# get_filename modes
CRASH_FILE: int = 0
ETEXT_FILE: int = 1
ALIAS_FILE: int = 2
MOB_FILE: int = 3

# BFS
BFS_ERROR: int = -1
BFS_ALREADY_THERE: int = -2
BFS_NO_PATH: int = -3

# Shop constants
MAX_TRADE: int = 5
MAX_PROD: int = 5
MAX_SHOP_OBJ: int = 100

# Trade restrictions
TRADE_NOGOOD: int = 1
TRADE_NOEVIL: int = 2
TRADE_NONEUTRAL: int = 4

# Real/virtual lookups
REAL: int = 0
VIRTUAL: int = 1
