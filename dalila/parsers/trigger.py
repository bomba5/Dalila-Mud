"""Trigger (.trg) file parser.

Ported from parse_trigger() in dg_db_scripts.c.
Reads DG Script trigger files: name, attach type, trigger type, arglist, script body.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TextIO

from dalila.models.trigger import TrigData
from dalila.parsers.utils import (
    asciiflag_conv,
    fread_string,
    get_line,
    read_index_file,
)

log = logging.getLogger(__name__)


def parse_trigger_record(fp: TextIO, vnum: int) -> TrigData:
    """Parse a single trigger record from a .trg file.

    Mirrors parse_trigger() from dg_db_scripts.c.
    """
    trig = TrigData()
    trig.vnum = vnum
    trig.name = fread_string(fp)

    # Line: attach_type flags [narg]
    line = get_line(fp)
    if line is None:
        raise ValueError(f"Unexpected EOF in trigger #{vnum}")

    parts = line.split()
    trig.attach_type = int(parts[0])
    trig.trigger_type = asciiflag_conv(parts[1]) if len(parts) > 1 else 0
    trig.narg = int(parts[2]) if len(parts) > 2 else 0

    # Argument list
    trig.arglist = fread_string(fp)

    # Script body: read lines until ~ terminator
    # Mirrors the Lance-Shade modified parser that reads line-by-line
    cmdlist: list[str] = []
    while True:
        line = get_line(fp)
        if line is None:
            break
        if line.strip() == "~":
            break
        cmdlist.append(line)

    trig.cmdlist = cmdlist
    return trig


def parse_trg_file(filepath: Path) -> list[TrigData]:
    """Parse all triggers from a single .trg file.

    Mirrors discrete_load(fl, DB_BOOT_TRG) from db.c.
    """
    triggers: list[TrigData] = []

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
                trig = parse_trigger_record(fp, vnum)
                triggers.append(trig)

    return triggers


def load_triggers(lib_path: Path) -> list[TrigData]:
    """Load all .trg files via the index file.

    Mirrors index_boot(DB_BOOT_TRG) from db.c.
    """
    prefix = lib_path / "world" / "trg"
    filenames = read_index_file(prefix)
    all_triggers: list[TrigData] = []

    for fname in filenames:
        fpath = prefix / fname
        if not fpath.exists():
            log.warning("Trigger file not found: %s", fpath)
            continue
        try:
            triggers = parse_trg_file(fpath)
            all_triggers.extend(triggers)
        except Exception as e:
            log.error("Error parsing %s: %s", fpath, e)

    return all_triggers
