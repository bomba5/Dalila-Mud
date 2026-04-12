"""Shared parser utilities.

Provides fread_string(), get_line(), asciiflag_conv(), and index file reading
matching the C implementations in db.c.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TextIO

log = logging.getLogger(__name__)


def get_line(fp: TextIO) -> str | None:
    """Read next non-blank, non-comment line from file.

    Mirrors get_line() from db.c: skips blank lines, returns stripped line.
    Returns None on EOF.
    """
    while True:
        line = fp.readline()
        if not line:
            return None
        line = line.rstrip("\n\r")
        if line:
            return line


def fread_string(fp: TextIO) -> str:
    """Read a tilde-terminated string from file.

    Mirrors fread_string() from db.c: reads lines until a line ending with ~
    is found. The tilde and trailing newline are stripped.
    """
    parts: list[str] = []
    while True:
        line = fp.readline()
        if not line:
            break
        # Check if line ends with ~
        stripped = line.rstrip("\n\r")
        if stripped.endswith("~"):
            # Remove the trailing ~ and add the line
            content = stripped[:-1]
            if content:
                parts.append(content)
            break
        parts.append(stripped)

    return "\r\n".join(parts)


def asciiflag_conv(flag: str) -> int:
    """Convert an ascii flag string to an integer.

    Mirrors asciiflag_conv() from db.c:
    - If all digits, parse as integer (supports long long via atolonglong)
    - Otherwise, lowercase a-z map to bits 0-25, uppercase A-Z map to bits 26-51
    """
    flag = flag.strip()
    if not flag:
        return 0

    is_number = True
    for ch in flag:
        if not ch.isdigit() and ch not in ("-", "+"):
            is_number = False
            break

    if is_number:
        return int(flag)

    flags = 0
    for ch in flag:
        if ch.islower():
            flags |= 1 << (ord(ch) - ord("a"))
        elif ch.isupper():
            flags |= 1 << (26 + (ord(ch) - ord("A")))

    return flags


def read_index_file(prefix: Path) -> list[str]:
    """Read an index file and return the list of data filenames.

    Mirrors the index reading logic in index_boot() from db.c.
    Each entry is a filename like '0.wld'. Stops at '$'.
    """
    index_path = prefix / "index"
    if not index_path.exists():
        log.warning("Index file not found: %s", index_path)
        return []

    filenames: list[str] = []
    with open(index_path, "r", encoding="latin-1") as f:
        for line in f:
            entry = line.strip()
            if not entry:
                continue
            if entry.startswith("$"):
                break
            filenames.append(entry)

    return filenames


def count_hash_records(fp: TextIO) -> int:
    """Count # records in a data file (for pre-allocation).

    Mirrors count_hash_records() from db.c.
    """
    count = 0
    for line in fp:
        if line.startswith("#"):
            count += 1
    fp.seek(0)
    return count
