"""Zone (.zon) file parser.

Ported from load_zones() in db.c.
Handles zone metadata, reset commands, wilderness/miniwild extensions.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TextIO

from dalila.constants import ZONE_MINIWILD, ZONE_NORMAL_AREA
from dalila.models.zone import ResetCommand, ZoneData
from dalila.parsers.utils import get_line, read_index_file

log = logging.getLogger(__name__)


def load_zone_file(filepath: Path) -> ZoneData:
    """Parse a single .zon file.

    Mirrors load_zones() from db.c.
    """
    zone = ZoneData()

    with open(filepath, "r", encoding="latin-1") as fp:
        # Line 1: #zone_number
        line = get_line(fp)
        if line is None or not line.startswith("#"):
            raise ValueError(f"Format error in {filepath}: expected #zone_number")
        zone.number = int(line[1:])

        # Line 2: zone name (tilde-terminated on same line)
        line = get_line(fp)
        if line is None:
            raise ValueError(f"Format error in {filepath}: expected zone name")
        if "~" in line:
            zone.name = line[:line.index("~")]
        else:
            zone.name = line

        # Line 3: top lifespan reset_mode [wilderness]
        # Or: number top lifespan reset_mode [wilderness] (5 fields)
        line = get_line(fp)
        if line is None:
            raise ValueError(f"Format error in {filepath}: expected constants line")
        parts = line.split()
        n = len(parts)
        zone.wilderness = ZONE_NORMAL_AREA

        if n == 3:
            zone.top = int(parts[0])
            zone.lifespan = int(parts[1])
            zone.reset_mode = int(parts[2])
        elif n == 4:
            zone.top = int(parts[0])
            zone.lifespan = int(parts[1])
            zone.reset_mode = int(parts[2])
            zone.wilderness = int(parts[3])
        elif n >= 5:
            # 5-field format: number top lifespan reset_mode wilderness
            zone.top = int(parts[1])
            zone.lifespan = int(parts[2])
            zone.reset_mode = int(parts[3])
            zone.wilderness = int(parts[4])
        else:
            raise ValueError(
                f"Format error in {filepath}: constants line has {n} fields"
            )

        # If miniwild, read the 4 exit vnums
        if zone.wilderness == ZONE_MINIWILD:
            line = get_line(fp)
            if line is not None:
                parts = line.split()
                if len(parts) >= 4:
                    zone.miniwild_exit = [int(x) for x in parts[:4]]

        # Parse reset commands
        for line in fp:
            line = line.strip()
            if not line:
                continue
            if line.startswith("*"):
                continue  # Comment

            cmd_char = line[0]
            if cmd_char in ("S", "$"):
                # Terminal command
                zone.cmd.append(ResetCommand(command="S"))
                break

            # Parse: command if_flag arg1 arg2 [arg3]
            parts = line[1:].split()
            if len(parts) < 3:
                continue

            rc = ResetCommand()
            rc.command = cmd_char
            rc.if_flag = bool(int(parts[0]))

            if cmd_char in ("M", "O", "E", "P", "D"):
                # 4-arg commands
                if len(parts) >= 4:
                    rc.arg1 = int(parts[1])
                    rc.arg2 = int(parts[2])
                    rc.arg3 = int(parts[3])
                else:
                    rc.arg1 = int(parts[1])
                    rc.arg2 = int(parts[2])
            else:
                # 3-arg commands (G, R, etc.)
                rc.arg1 = int(parts[1])
                rc.arg2 = int(parts[2])
                if len(parts) >= 4:
                    rc.arg3 = int(parts[3])

            zone.cmd.append(rc)

        # Ensure terminator exists
        if not zone.cmd or zone.cmd[-1].command != "S":
            zone.cmd.append(ResetCommand(command="S"))

    return zone


def load_zones(lib_path: Path) -> list[ZoneData]:
    """Load all .zon files via the index file.

    Mirrors index_boot(DB_BOOT_ZON) from db.c.
    """
    prefix = lib_path / "world" / "zon"
    filenames = read_index_file(prefix)
    all_zones: list[ZoneData] = []

    for fname in filenames:
        fpath = prefix / fname
        if not fpath.exists():
            log.warning("Zone file not found: %s", fpath)
            continue
        try:
            zone = load_zone_file(fpath)
            all_zones.append(zone)
        except Exception as e:
            log.error("Error parsing %s: %s", fpath, e)

    return all_zones
