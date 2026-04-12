"""Character data structures.

Ported from structs.h: char_data, char_file_u, char_player_data,
char_ability_data, char_point_data, char_special_data, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dalila.constants import (
    MAX_ABILITA,
    MAX_AFFECT,
    MAX_OBJ_AFFECT,
    MAX_PROFICIENZE,
    MAX_SKILLS,
    MAX_TONGUE,
    NOBODY,
    NOWHERE,
    NUM_WEARS,
)
from dalila.models.common import AffectedType, Bitvector, TrigProto


@dataclass
class CharAbilityData:
    """Character abilities. Used in char_file_u.

    Ported from struct char_ability_data in structs.h.
    DO NOT CHANGE -- matches binary playerfile.
    """
    str: int = 0
    str_add: int = 0       # 000-100 if strength 18
    intel: int = 0
    wis: int = 0
    dex: int = 0
    con: int = 0
    cha: int = 0


@dataclass
class CharPointData:
    """Character points. Used in char_file_u.

    Ported from struct char_point_data in structs.h.
    DO NOT CHANGE -- matches binary playerfile.
    """
    mana: int = 0
    max_mana: int = 0
    hit: int = 0
    max_hit: int = 0
    move: int = 0
    max_move: int = 0
    armor: int = 0           # Internal -100..100, external -10..10 AC
    gold: int = 0
    bank_gold: int = 0
    exp: int = 0
    fama: int = 0            # La fama del giocatore
    notorieta: int = 0       # La notorieta del giocatore
    hitroll: int = 0
    damroll: int = 0


@dataclass
class TimeData:
    """Character time data.

    Ported from struct time_data in structs.h.
    """
    birth: int = 0           # Time of birth (time_t)
    logon: int = 0           # Time of last logon (time_t)
    played: int = 0          # Total accumulated time played in secs


@dataclass
class TimeInfoData:
    """MUD time information.

    Ported from struct time_info_data in structs.h.
    """
    hours: int = 0
    day: int = 0
    month: int = 0
    year: int = 0


@dataclass
class PlayerFee:
    """Player fee/stipendio structure.

    Ported from struct player_fee in structs.h.
    """
    has_fee: bool = False
    clan_fee: int = 0
    idclan: int = 0
    char_fee: int = 0
    idchar: int = 0


@dataclass
class CharResistenze:
    """Character resistances.

    Ported from struct char_resistenze in structs.h.
    """
    res_fuoco: int = 0
    res_ghiaccio: int = 0
    res_elettricita: int = 0
    res_acido: int = 0
    res_shaarr: int = 0
    res_xhyphys: int = 0
    res_therion: int = 0
    res_silue: int = 0
    res_fisico: int = 0


@dataclass
class CharSpecialDataSaved:
    """Specials shared by PC and NPC, saved to playerfile.

    Ported from struct char_special_data_saved in structs.h.
    WARNING: Do not change -- will ruin playerfile.
    """
    alignment: int = 0
    idnum: int = -1                  # Player idnum; -1 for mobiles
    act: int = 0                     # act flags (long long int)
    affected_by: list[int] = field(
        default_factory=lambda: [0, 0, 0, 0]
    )                                # 4-bank bitvector
    apply_saving_throw: list[int] = field(
        default_factory=lambda: [0, 0, 0, 0, 0]
    )


@dataclass
class PlayerSpecialSaved:
    """PC-only specials saved to playerfile.

    Ported from struct player_special_data_saved in structs.h.
    DO NOT add/delete/move variables -- will ruin playerfile.
    """
    skills: list[int] = field(
        default_factory=lambda: [0] * (MAX_SKILLS + 1)
    )
    proficienze: list[int] = field(
        default_factory=lambda: [0] * (MAX_PROFICIENZE + 1)
    )
    prof_choice: list[int] = field(default_factory=lambda: [0, 0])
    abilita: list[int] = field(
        default_factory=lambda: [0] * (MAX_ABILITA + 1)
    )
    abil_choice: list[int] = field(default_factory=lambda: [0, 0, 0])
    padding0: int = 0               # Was spells_to_learn
    talks: list[bool] = field(
        default_factory=lambda: [False] * MAX_TONGUE
    )
    wimp_level: int = 0
    freeze_level: int = 0
    invis_level: int = 0
    load_room: int = NOWHERE
    pref: int = 0                    # Preference flags (long long)
    bad_pws: int = 0
    conditions: list[int] = field(
        default_factory=lambda: [0, 0, 0]
    )                                # Drunk, full, thirsty
    stipendio: PlayerFee = field(default_factory=PlayerFee)

    # Spares repurposed
    clan_rank: int = 0
    wild_max_x_range: int = 0
    wild_max_y_range: int = 0
    class_title: int = 0
    stato_sociale: int = 0
    new_clan_rank: int = 0
    trust_level: int = 0
    spare5: int = 0                  # Culto (PEPPE RELIGIONE)
    resuscita: int = 0               # Ore mancanti per resuscitare
    fiato: int = 0
    te_t_concentrazione: int = 0     # Tempo/tipo di concentrazione
    spare9: int = 0
    spare10: int = 0
    spells_to_learn: int = 0
    clan: int = 0
    privilegi: int = 0
    olc_zone: int = 0
    gohome: int = 0
    questmrr: int = 0               # Mob-Room-Risultato
    questobj: int = 0
    questpoints: int = 0
    tipoquest: int = 0
    countdown: int = 0
    shop: int = 0
    arena_hit: int = 0
    arena_move: int = 0
    arena_mana: int = 0
    arena_room: int = 0
    bet_amt: int = 0
    betted_on: int = 0
    rip_cnt: int = 0
    kill_cnt: int = 0
    dt_cnt: int = 0
    morti_per_livello: int = 0
    abilita_to_learn: int = 0
    num_thief: int = 0
    num_kills: int = 0
    num_tkills: int = 0
    num_warkills: int = 0
    num_wanted: int = 0
    new_clan: int = 0
    new_privilegi: int = 0
    culto: int = 0
    as_room: int = 0
    as_rnum: int = 0
    new_stipendio_hasfee: int = 0
    new_stipendio_clanfee: int = 0
    numero_unita_armate: int = 0
    morte_peste: int = 0
    morti_da_pg: int = 0
    xp_giornalieri: int = 0
    spare27: int = 0
    spare28: int = 0
    spare29: int = 0
    spare30: int = 0


@dataclass
class CharPlayerData:
    """General player-related info for PC and NPC.

    Ported from struct char_player_data in structs.h.
    """
    passwd: str = ""
    name: str = ""
    short_descr: str = ""
    long_descr: str = ""
    description: str = ""
    title: str = ""
    poofin: str = ""
    poofout: str = ""
    sex: int = 0
    class_: int = 0          # 'class' is reserved in Python
    level: int = 0
    hometown: int = 0
    time: TimeData = field(default_factory=TimeData)
    weight: int = 0
    height: int = 0
    # Disguise/camuffamento fields (PEPPE DISGUISE)
    namedisguise: str = ""
    long_descr_disguise: str = ""
    l_descr_disguise: str = ""
    classdisguise: int = 0
    livdisguise: int = 0
    sexdisguise: int = 0
    clandisguise: int = 0
    clanrankdisguise: int = 0
    classtitledisguise: int = 0


@dataclass
class MobSpecialData:
    """NPC-only special data.

    Ported from struct mob_special_data in structs.h.
    """
    idmob: int = 0
    last_direction: int = 0
    attack_type: int = 0
    default_pos: int = 0
    damnodice: int = 0
    damsizedice: int = 0
    wait_state: int = 0
    # Lance go-patrol fields
    clanid: int = 0
    masterid: int = 0
    pospath: int = 0
    lastdir: int = 0
    go_path: str = ""
    go_chtarget: int = 0
    go_nametarget: str = ""
    go_room: int = 0
    search_mode: int = 0
    cmd_mode: int = 0
    searchcommand: str = ""
    savedmaster: int = 0
    newclanid: int = 0
    stipendiomob: int = 0
    paga: int = 0
    conditions: list[int] = field(default_factory=lambda: [-1, -1, -1])


@dataclass
class CharData:
    """Full character structure for player/non-player.

    Ported from struct char_data in structs.h.
    Linked list pointers are replaced with optional IDs/references.
    """
    pfilepos: int = -1
    nr: int = -1                     # Mob rnum (-1 for PCs)
    in_room: int = NOWHERE
    was_in_room: int = NOWHERE

    player: CharPlayerData = field(default_factory=CharPlayerData)
    real_abils: CharAbilityData = field(default_factory=CharAbilityData)
    aff_abils: CharAbilityData = field(default_factory=CharAbilityData)
    points: CharPointData = field(default_factory=CharPointData)
    char_specials_saved: CharSpecialDataSaved = field(
        default_factory=CharSpecialDataSaved
    )
    player_specials: PlayerSpecialSaved | None = None
    mob_specials: MobSpecialData = field(default_factory=MobSpecialData)
    resistenze: CharResistenze = field(default_factory=CharResistenze)

    affected: list[AffectedType] = field(default_factory=list)
    equipment: list[None] = field(
        default_factory=lambda: [None] * NUM_WEARS
    )

    # DG triggers
    id: int = 0
    proto_script: list[TrigProto] = field(default_factory=list)

    # Iniziazione fields
    iniz_classe: int = 0
    iniz_ptagg: list[int] = field(default_factory=lambda: [0] * 6)
    iniz_da_aggiungere: int = 0

    # Runtime reference to network descriptor (not persisted)
    # Uses Any to avoid circular import with dalila.net.descriptor
    desc: object | None = None
