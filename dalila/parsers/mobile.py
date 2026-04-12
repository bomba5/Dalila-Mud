"""Mobile (.mob) file parser.

Ported from parse_mobile(), parse_simple_mob(), parse_enhanced_mob() in db.c.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TextIO

from dalila.models.character import CharData, CharAbilityData, MobSpecialData
from dalila.models.common import TrigProto
from dalila.parsers.utils import (
    asciiflag_conv,
    fread_string,
    get_line,
    read_index_file,
)

log = logging.getLogger(__name__)


def parse_simple_mob(fp: TextIO, mob: CharData, vnum: int) -> None:
    """Parse the simple mob section (after 'S' flag).

    Mirrors parse_simple_mob() from db.c.
    """
    mob.real_abils = CharAbilityData(
        str=11, intel=11, wis=11, dex=11, con=11, cha=11
    )

    # Line 1: level hitroll armor #d#+# #d#+#
    line = get_line(fp)
    if line is None:
        raise ValueError(f"Unexpected EOF in simple mob #{vnum}")

    parts = line.split()
    mob.player.level = int(parts[0])
    mob.points.hitroll = 20 - int(parts[1])
    mob.points.armor = 10 * int(parts[2])

    # Parse #d#+# for hit dice
    dice_str = parts[3]  # e.g. "10d8+100"
    d_pos = dice_str.index("d")
    plus_pos = dice_str.index("+")
    mob.points.max_hit = 0  # Flag: H, M, V is xdy+z
    mob.points.hit = int(dice_str[:d_pos])
    mob.points.mana = int(dice_str[d_pos + 1:plus_pos])
    mob.points.move = int(dice_str[plus_pos + 1:])

    mob.points.max_mana = 100
    mob.points.max_move = 50

    # Parse damage dice: #d#+#
    dmg_str = parts[4]  # e.g. "3d6+5"
    d_pos = dmg_str.index("d")
    plus_pos = dmg_str.index("+")
    mob.mob_specials.damnodice = int(dmg_str[:d_pos])
    mob.mob_specials.damsizedice = int(dmg_str[d_pos + 1:plus_pos])
    mob.points.damroll = int(dmg_str[plus_pos + 1:])

    # Line 2: gold exp
    line = get_line(fp)
    if line is None:
        raise ValueError(f"Unexpected EOF in simple mob #{vnum}")
    parts = line.split()
    # Gold is recalculated at runtime, but store exp
    mob.points.gold = int(parts[0])
    mob.points.exp = int(parts[1])

    # Line 3: position default_pos sex
    line = get_line(fp)
    if line is None:
        raise ValueError(f"Unexpected EOF in simple mob #{vnum}")
    parts = line.split()
    mob.mob_specials.default_pos = int(parts[1])
    mob.player.sex = int(parts[2])


def parse_enhanced_mob(fp: TextIO, mob: CharData, vnum: int) -> None:
    """Parse enhanced mob section (after 'E' flag).

    Mirrors parse_enhanced_mob() from db.c.
    First parses simple mob data, then reads E-spec lines until 'E' terminator.
    """
    parse_simple_mob(fp, mob, vnum)

    while True:
        line = get_line(fp)
        if line is None:
            raise ValueError(f"Unexpected EOF in enhanced mob #{vnum}")
        if line == "E":
            return
        if line.startswith("#"):
            raise ValueError(f"Unterminated E section in mob #{vnum}")

        # Parse e-spec: "Keyword: value"
        if ":" in line:
            keyword, _, value = line.partition(":")
            keyword = keyword.strip()
            value = value.strip()
            _apply_espec(mob, keyword, value, vnum)
        else:
            _apply_espec(mob, line.strip(), "", vnum)


def _apply_espec(mob: CharData, keyword: str, value: str, vnum: int) -> None:
    """Apply an e-spec keyword/value to a mob.

    Mirrors interpret_espec() from db.c.
    """
    num_arg = int(value) if value and value.lstrip("-").isdigit() else 0

    kw = keyword.lower()
    if kw == "barehandattack":
        mob.mob_specials.attack_type = max(0, min(99, num_arg))
    elif kw == "str":
        mob.real_abils.str = max(3, min(25, num_arg))
    elif kw == "stradd":
        mob.real_abils.str_add = max(0, min(100, num_arg))
    elif kw == "int":
        mob.real_abils.intel = max(3, min(25, num_arg))
    elif kw == "wis":
        mob.real_abils.wis = max(3, min(25, num_arg))
    elif kw == "dex":
        mob.real_abils.dex = max(3, min(25, num_arg))
    elif kw == "con":
        mob.real_abils.con = max(3, min(25, num_arg))
    elif kw == "cha":
        mob.real_abils.cha = max(3, min(25, num_arg))
    elif kw == "spec":
        pass  # Spec procs assigned at runtime
    else:
        log.debug("Unrecognized espec '%s' in mob #%d", keyword, vnum)


def parse_mobile(fp: TextIO, vnum: int) -> CharData:
    """Parse a single mob record from a .mob file.

    Mirrors parse_mobile() from db.c.
    """
    mob = CharData()
    mob.nr = vnum

    # String data: name, short_descr, long_descr, description
    mob.player.name = fread_string(fp)
    mob.player.short_descr = fread_string(fp)
    mob.player.long_descr = fread_string(fp)
    mob.player.description = fread_string(fp)
    mob.player.title = ""

    # Three unused fread_strings (Dalila legacy)
    fread_string(fp)
    fread_string(fp)
    fread_string(fp)

    # Numeric data: flags aff_flags alignment extra_fields... letter
    line = get_line(fp)
    if line is None:
        raise ValueError(f"Unexpected EOF in mob #{vnum} numeric line")

    parts = line.split()
    # Format: f1 f2 alignment z[0] z[1] z[2] l[0] z[3] letter
    mob_flags = asciiflag_conv(parts[0])
    mob_flags |= (1 << 3)  # MOB_ISNPC always set
    mob.char_specials_saved.act = mob_flags
    mob.char_specials_saved.affected_by[0] = asciiflag_conv(parts[1])
    mob.char_specials_saved.alignment = int(parts[2])

    # Parse optional extra fields (clanid, masterid, etc.) -- variable count
    # The last element is the type letter (S or E)
    letter = parts[-1] if parts[-1] in ("S", "E") else "S"

    if letter == "S":
        parse_simple_mob(fp, mob, vnum)
    elif letter == "E":
        parse_enhanced_mob(fp, mob, vnum)

    # Copy real abilities to affected abilities
    mob.aff_abils = CharAbilityData(
        str=mob.real_abils.str,
        str_add=mob.real_abils.str_add,
        intel=mob.real_abils.intel,
        wis=mob.real_abils.wis,
        dex=mob.real_abils.dex,
        con=mob.real_abils.con,
        cha=mob.real_abils.cha,
    )

    # Parse trailing T (trigger) lines
    _parse_trailing_triggers(fp, mob)

    return mob


def _parse_trailing_triggers(fp: TextIO, mob: CharData) -> None:
    """Parse T trigger lines following mob S/E section."""
    while True:
        pos = fp.tell()
        line = fp.readline()
        if not line:
            break
        stripped = line.strip()
        if stripped.startswith("T"):
            parts = stripped.split()
            if len(parts) >= 2:
                try:
                    trig_vnum = int(parts[1])
                    mob.proto_script.append(TrigProto(vnum=trig_vnum))
                except ValueError:
                    fp.seek(pos)
                    break
            else:
                fp.seek(pos)
                break
        else:
            fp.seek(pos)
            break


def parse_mob_file(filepath: Path) -> list[CharData]:
    """Parse all mobs from a single .mob file.

    Mirrors discrete_load(fl, DB_BOOT_MOB) from db.c.
    """
    mobs: list[CharData] = []

    with open(filepath, "r", encoding="latin-1") as fp:
        while True:
            line = get_line(fp)
            if line is None:
                break
            if line.startswith("$"):
                break
            if line.startswith("#"):
                vnum = int(line[1:])
                if vnum >= 1999999:
                    break
                mob = parse_mobile(fp, vnum)
                mobs.append(mob)

    return mobs


def load_mobiles(lib_path: Path) -> list[CharData]:
    """Load all .mob files via the index file.

    Mirrors index_boot(DB_BOOT_MOB) from db.c.
    """
    prefix = lib_path / "world" / "mob"
    filenames = read_index_file(prefix)
    all_mobs: list[CharData] = []

    for fname in filenames:
        fpath = prefix / fname
        if not fpath.exists():
            log.warning("Mob file not found: %s", fpath)
            continue
        try:
            mobs = parse_mob_file(fpath)
            all_mobs.extend(mobs)
        except Exception as e:
            log.error("Error parsing %s: %s", fpath, e)

    return all_mobs
