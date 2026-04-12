"""World (.wld) file parser.

Ported from parse_room() and setup_dir() in db.c.
Reads CircleMUD world files with Dalila extensions (F resource lines, T triggers).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TextIO

from dalila.models.common import ExtraDescr, TrigProto
from dalila.models.room import RoomData, RoomDirection
from dalila.parsers.utils import (
    asciiflag_conv,
    fread_string,
    get_line,
    read_index_file,
)

log = logging.getLogger(__name__)


def parse_direction(fp: TextIO, room_vnum: int, direction: int) -> RoomDirection:
    """Parse a direction block (D line) from a .wld file.

    Mirrors setup_dir() from db.c.
    """
    d = RoomDirection()
    d.general_description = fread_string(fp)
    d.keyword = fread_string(fp)

    line = get_line(fp)
    if line is None:
        raise ValueError(f"Unexpected EOF in direction D{direction} of room #{room_vnum}")

    parts = line.split()
    if len(parts) < 3:
        raise ValueError(
            f"Format error in room #{room_vnum}, direction D{direction}: '{line}'"
        )

    door_flag = int(parts[0])
    d.key = int(parts[1])
    d.to_room = int(parts[2])

    if door_flag == 1:
        d.exit_info = 1  # EX_ISDOOR
    elif door_flag == 2:
        d.exit_info = 1 | 8  # EX_ISDOOR | EX_PICKPROOF
    else:
        d.exit_info = 0

    return d


def parse_room(fp: TextIO, vnum: int) -> RoomData:
    """Parse a single room record from a .wld file.

    Mirrors parse_room() from db.c.
    """
    room = RoomData()
    room.number = vnum
    room.name = fread_string(fp)
    room.description = fread_string(fp)

    # Numeric line: zone_nr flags sector_type
    line = get_line(fp)
    if line is None:
        raise ValueError(f"Unexpected EOF after room #{vnum} description")

    parts = line.split()
    if len(parts) < 3:
        raise ValueError(f"Format error in room #{vnum} numeric line: '{line}'")

    # t[0] is zone number (ignored -- assigned by zone range)
    room.room_flags = asciiflag_conv(parts[1])
    room.sector_type = int(parts[2])

    # Parse optional sections: D (direction), E (extra desc), F (resource), S (end)
    while True:
        line = get_line(fp)
        if line is None:
            raise ValueError(f"Unexpected EOF in room #{vnum}")

        if line.startswith("D"):
            direction = int(line[1:])
            room.dir_option[direction] = parse_direction(fp, vnum, direction)
        elif line.startswith("F"):
            # Dalila resource flags -- read and skip the data line
            _resource_line = get_line(fp)
        elif line.startswith("E"):
            descr = ExtraDescr()
            descr.keyword = fread_string(fp)
            descr.description = fread_string(fp)
            room.ex_description.append(descr)
        elif line.startswith("S"):
            # End of room. Check for T (trigger) lines following S.
            _parse_trailing_triggers(fp, room)
            break
        else:
            raise ValueError(
                f"Unexpected line in room #{vnum}: '{line}'"
            )

    return room


def _parse_trailing_triggers(fp: TextIO, room: RoomData) -> None:
    """Parse T trigger lines that follow the S end-of-room marker.

    Mirrors the post-S trigger reading in parse_room() from db.c.
    """
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
                    room.proto_script.append(TrigProto(vnum=trig_vnum))
                except ValueError:
                    fp.seek(pos)
                    break
            else:
                fp.seek(pos)
                break
        else:
            # Not a T line -- put it back
            fp.seek(pos)
            break


def parse_wld_file(filepath: Path) -> list[RoomData]:
    """Parse all rooms from a single .wld file.

    Mirrors discrete_load(fl, DB_BOOT_WLD) from db.c.
    """
    rooms: list[RoomData] = []

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
                room = parse_room(fp, vnum)
                rooms.append(room)

    return rooms


def load_world(lib_path: Path) -> list[RoomData]:
    """Load all .wld files via the index file.

    Mirrors index_boot(DB_BOOT_WLD) from db.c.
    Returns all rooms from all zone world files.
    """
    prefix = lib_path / "world" / "wld"
    filenames = read_index_file(prefix)
    all_rooms: list[RoomData] = []

    for fname in filenames:
        fpath = prefix / fname
        if not fpath.exists():
            log.warning("World file not found: %s", fpath)
            continue
        try:
            rooms = parse_wld_file(fpath)
            all_rooms.extend(rooms)
        except Exception as e:
            log.error("Error parsing %s: %s", fpath, e)

    return all_rooms
