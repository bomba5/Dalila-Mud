"""Trigger (DG Scripts) data structures.

Ported from struct trig_data, struct script_data in dg_scripts.h.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TrigData:
    """A trigger definition (prototype).

    Ported from struct trig_data in dg_scripts.h.
    """
    nr: int = -1                     # Trigger rnum
    vnum: int = -1                   # Virtual number (from index)
    attach_type: int = 0             # mob/obj/wld (MOB_TRIGGER, etc.)
    data_type: int = 0               # Type of game_data for trig
    name: str = ""                   # Name of trigger
    trigger_type: int = 0            # Trigger type bitvector
    cmdlist: list[str] = field(default_factory=list)  # Script lines
    narg: int = 0                    # Numerical argument
    arglist: str = ""                # Argument list (string)
