"""Room data structures.

Ported from struct room_data, struct room_direction_data in structs.h.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dalila.constants import NOWHERE, NUM_OF_DIRS
from dalila.models.common import ExtraDescr, TrigProto


@dataclass
class RoomDirection:
    """Exit/direction data for a room.

    Ported from struct room_direction_data in structs.h.
    """
    general_description: str = ""   # When look DIR
    keyword: str = ""               # For open/close
    exit_info: int = 0              # Exit flags (EX_ISDOOR, etc.)
    key: int = -1                   # Key vnum (-1 for no key)
    to_room: int = NOWHERE          # Where direction leads (vnum in file, rnum after boot)


@dataclass
class RoomData:
    """A room in the world.

    Ported from struct room_data in structs.h.
    """
    number: int = 0                 # Room vnum
    zone: int = 0                   # Zone index (for resetting)
    sector_type: int = 0            # Sector type (move/hide)
    name: str = ""                  # Room name
    description: str = ""           # Shown when entered
    ex_description: list[ExtraDescr] = field(default_factory=list)
    dir_option: list[RoomDirection | None] = field(
        default_factory=lambda: [None] * NUM_OF_DIRS
    )
    room_flags: int = 0             # ROOM_DARK, ROOM_DEATH, etc. (long long int)

    # Dalila wilderness extensions
    wild_modif: bool = False        # Modified from standard wilderness
    wild_rnum: int = -1             # Wilderness type from wild_table

    light: int = 0                  # Number of light sources
    proto_script: list[TrigProto] = field(default_factory=list)
