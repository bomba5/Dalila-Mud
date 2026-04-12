"""Object (.obj) file parser.

Ported from parse_object() in db.c.
Handles NUM_OBJ_VAL_POSITIONS=10, Dalila material fields,
C bitvector lines, T triggers, E extra descriptions, A applies.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TextIO

from dalila.models.common import ExtraDescr, TrigProto
from dalila.models.object import ObjAffectedType, ObjData, ObjFlagData
from dalila.models.common import Bitvector
from dalila.constants import MAX_OBJ_AFFECT
from dalila.parsers.utils import (
    asciiflag_conv,
    fread_string,
    get_line,
    read_index_file,
)

log = logging.getLogger(__name__)


def parse_object(fp: TextIO, vnum: int) -> tuple[ObjData, str]:
    """Parse a single object record from a .obj file.

    Mirrors parse_object() from db.c.
    Returns (obj, next_line) where next_line is the line that terminated
    parsing (# or $) since obj files have no end-of-record marker.
    """
    obj = ObjData()
    obj.vnum = vnum

    # String data
    obj.name = fread_string(fp)
    if not obj.name:
        raise ValueError(f"Null obj name at or near object #{vnum}")
    obj.short_description = fread_string(fp)
    obj.description = fread_string(fp)
    obj.action_description = fread_string(fp)

    # Numeric line 1: type extra_flags wear_flags
    line = get_line(fp)
    if line is None:
        raise ValueError(f"Unexpected EOF in object #{vnum} line 1")
    parts = line.split()
    if len(parts) < 3:
        raise ValueError(f"Format error in object #{vnum} line 1: '{line}'")
    obj.obj_flags.type_flag = int(parts[0])
    obj.obj_flags.extra_flags = asciiflag_conv(parts[1])
    obj.obj_flags.wear_flags = asciiflag_conv(parts[2])

    # Numeric line 2: values (4 or 6 fields)
    line = get_line(fp)
    if line is None:
        raise ValueError(f"Unexpected EOF in object #{vnum} line 2")
    parts = line.split()
    for i in range(min(4, len(parts))):
        obj.obj_flags.value[i] = int(parts[i])
    if len(parts) >= 6:
        t4, t5 = int(parts[4]), int(parts[5])
        if 0 <= t4 <= 100 and 0 <= t5 <= 100:
            obj.obj_flags.curr_slots = t4
            obj.obj_flags.total_slots = t5

    # Numeric line 3: weight cost cost_per_day [min_level [tipo_materiale num_materiale]]
    line = get_line(fp)
    if line is None:
        raise ValueError(f"Unexpected EOF in object #{vnum} line 3")
    parts = line.split()
    if len(parts) < 3:
        raise ValueError(f"Format error in object #{vnum} line 3: '{line}'")
    obj.obj_flags.weight = int(parts[0])
    obj.obj_flags.cost = int(parts[1])
    obj.obj_flags.cost_per_day = int(parts[2])
    if len(parts) >= 4:
        obj.obj_flags.min_level = int(parts[3])
    if len(parts) >= 6:
        obj.obj_flags.tipo_materiale = int(parts[4])
        obj.obj_flags.num_materiale = int(parts[5])

    # Parse optional sections: E (extra desc), A (apply), C (bitvector), T (trigger)
    affect_idx = 0
    next_line = ""

    while True:
        line = get_line(fp)
        if line is None:
            next_line = "$"
            break

        if line.startswith("E"):
            descr = ExtraDescr()
            descr.keyword = fread_string(fp)
            descr.description = fread_string(fp)
            obj.ex_description.append(descr)

        elif line.startswith("A"):
            if affect_idx >= MAX_OBJ_AFFECT:
                log.warning("Too many A fields in object #%d", vnum)
                aline = get_line(fp)
                continue
            aline = get_line(fp)
            if aline is None:
                break
            aparts = aline.split()
            if len(aparts) >= 2:
                obj.affected[affect_idx].location = int(aparts[0])
                obj.affected[affect_idx].modifier = int(aparts[1])
            affect_idx += 1

        elif line.startswith("C"):
            # 4-bank bitvector line
            cline = get_line(fp)
            if cline is not None:
                cparts = cline.split()
                banks = [int(x) for x in cparts[:4]]
                obj.obj_flags.bitvector = Bitvector(banks=banks)

        elif line.startswith("T"):
            # DG trigger
            parts = line.split()
            if len(parts) >= 2:
                try:
                    trig_vnum = int(parts[1])
                    obj.proto_script.append(TrigProto(vnum=trig_vnum))
                except ValueError:
                    pass

        elif line.startswith("$") or line.startswith("#"):
            next_line = line
            break

        else:
            raise ValueError(
                f"Unexpected line in object #{vnum}: '{line}'"
            )

    return obj, next_line


def parse_obj_file(filepath: Path) -> list[ObjData]:
    """Parse all objects from a single .obj file.

    Mirrors discrete_load(fl, DB_BOOT_OBJ) from db.c.
    Special handling: obj files use # as end-of-record (no S marker).
    """
    objects: list[ObjData] = []

    with open(filepath, "r", encoding="latin-1") as fp:
        line = get_line(fp)
        while line is not None:
            if line.startswith("$"):
                break
            if line.startswith("#"):
                vnum = int(line[1:])
                if vnum >= 1999999:
                    break
                obj, next_line = parse_object(fp, vnum)
                objects.append(obj)
                # next_line is the line that terminated parsing
                line = next_line if next_line else get_line(fp)
            else:
                line = get_line(fp)

    return objects


def load_objects(lib_path: Path) -> list[ObjData]:
    """Load all .obj files via the index file.

    Mirrors index_boot(DB_BOOT_OBJ) from db.c.
    """
    prefix = lib_path / "world" / "obj"
    filenames = read_index_file(prefix)
    all_objects: list[ObjData] = []

    for fname in filenames:
        fpath = prefix / fname
        if not fpath.exists():
            log.warning("Object file not found: %s", fpath)
            continue
        try:
            objs = parse_obj_file(fpath)
            all_objects.extend(objs)
        except Exception as e:
            log.error("Error parsing %s: %s", fpath, e)

    return all_objects
