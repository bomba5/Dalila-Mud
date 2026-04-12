"""Object data structures.

Ported from struct obj_data, struct obj_flag_data, struct obj_file_elem,
struct obj_affected_type, struct rent_info in structs.h.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dalila.constants import (
    MAX_OBJ_AFFECT,
    NOWHERE,
    NUM_OBJ_VAL_POSITIONS,
)
from dalila.models.common import Bitvector, ExtraDescr, TrigProto


@dataclass
class ObjAffectedType:
    """Object affect modifier.

    Ported from struct obj_affected_type in structs.h.
    """
    location: int = 0       # Which ability to change (APPLY_XXX)
    modifier: int = 0       # How much it changes by


@dataclass
class ObjFlagData:
    """Object flags and numeric properties.

    Ported from struct obj_flag_data in structs.h.
    """
    value: list[int] = field(
        default_factory=lambda: [0] * NUM_OBJ_VAL_POSITIONS
    )
    type_flag: int = 0              # Item type (ITEM_LIGHT, etc.)
    wear_flags: int = 0             # Where you can wear it
    extra_flags: int = 0            # ITEM_GLOW, ITEM_HUM, etc. (long long int)
    weight: int = 0
    cost: int = 0                   # Value when sold (gp)
    cost_per_day: int = 0           # Cost to keep per real day
    timer: int = 0                  # Timer for object
    bitvector: Bitvector = field(default_factory=Bitvector)  # 4-bank bitvector
    curr_slots: int = 0             # Current amount of slots obj has
    total_slots: int = 0            # Total amount of slots
    min_level: int = -1             # Minimum level to equip
    tipo_materiale: int = 0         # Material type (Dalila crafting)
    num_materiale: int = 0          # Material number (Dalila crafting)


@dataclass
class ObjData:
    """An object in the game world.

    Ported from struct obj_data in structs.h.
    """
    item_number: int = -1           # Index in prototype array (rnum)
    vnum: int = -1                  # Virtual number (for lookup)
    in_room: int = NOWHERE          # In what room (-1 when carried/in container)
    obj_flags: ObjFlagData = field(default_factory=ObjFlagData)
    affected: list[ObjAffectedType] = field(
        default_factory=lambda: [ObjAffectedType() for _ in range(MAX_OBJ_AFFECT)]
    )

    name: str = ""                  # Keywords for get/look
    description: str = ""           # When in room
    short_description: str = ""     # When worn/carried/in container
    action_description: str = ""    # When used
    ex_description: list[ExtraDescr] = field(default_factory=list)

    # DG triggers
    id: int = 0
    proto_script: list[TrigProto] = field(default_factory=list)


@dataclass
class ObjFileElem:
    """Binary file element for rent/crash files.

    Ported from struct obj_file_elem in structs.h.
    BEWARE: Changing it will ruin rent files.
    """
    item_number: int = 0            # obj_vnum
    locate: int = 0                 # (1+)wear-location or (20+)index in container
    value: list[int] = field(
        default_factory=lambda: [0] * NUM_OBJ_VAL_POSITIONS
    )
    type_flag: int = 0
    extra_flags: int = 0
    wear_flags: int = 0
    weight: int = 0
    cost: int = 0
    cost_per_day: int = 0
    timer: int = 0
    bitvector: Bitvector = field(default_factory=Bitvector)
    affected: list[ObjAffectedType] = field(
        default_factory=lambda: [ObjAffectedType() for _ in range(MAX_OBJ_AFFECT)]
    )
    curr_slots: int = 0
    total_slots: int = 0
    min_level: int = 0
    tipo_materiale: int = 0
    num_materiale: int = 0


@dataclass
class RentInfo:
    """Header block for rent files.

    Ported from struct rent_info in structs.h.
    BEWARE: Changing it will ruin rent files.
    """
    time: int = 0
    rentcode: int = 0
    net_cost_per_diem: int = 0
    gold: int = 0
    account: int = 0
    nitems: int = 0
    spare0: int = 0
    spare1: int = 0
    spare2: int = 0
    spare3: int = 0
    spare4: int = 0
    spare5: int = 0
    spare6: int = 0
    spare7: int = 0
