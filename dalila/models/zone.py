"""Zone data structures.

Ported from struct zone_data, struct reset_com in db.h.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dalila.constants import ZONE_NORMAL_AREA


@dataclass
class ResetCommand:
    """Zone reset command.

    Ported from struct reset_com in db.h.
    Commands: M(ob), O(bject), G(ive), P(ut), E(quip), D(oor), R(emove).
    """
    command: str = "S"      # Command character
    if_flag: bool = False   # Execute only if preceding executed
    arg1: int = 0
    arg2: int = 0
    arg3: int = 0
    line: int = 0           # Line number in zone file


@dataclass
class ZoneData:
    """Zone definition.

    Ported from struct zone_data in db.h.
    """
    name: str = ""
    number: int = 0              # Virtual number of this zone
    lifespan: int = 0            # Minutes between resets
    age: int = 0                 # Current age in minutes
    top: int = 0                 # Upper limit for rooms in this zone
    reset_mode: int = 0          # 0=don't reset, 1=reset if no PCs, 2=always
    cmd: list[ResetCommand] = field(default_factory=list)

    # Weather per zone
    pressure: int = 960
    change: int = 0
    sky: int = 0

    # Wilderness
    wilderness: int = ZONE_NORMAL_AREA
    miniwild_exit: list[int] = field(
        default_factory=lambda: [-1, -1, -1, -1]
    )
