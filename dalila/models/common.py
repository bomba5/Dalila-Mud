"""Shared types: Bitvector, ExtraDescr, AffectedType.

Ported from structs.h shared data structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field


NUM_BITVECTOR_BANKS: int = 4


class Bitvector:
    """4-bank bitvector system for 256-bit flag fields.

    The Dalila codebase uses 4 x 64-bit integers (long long int[4]) to
    store affect flags, object bitvectors, etc. Each bank is indexed 0-3.
    Provides IS_SET, SET_BIT, REMOVE_BIT operations matching the C macros.
    """

    __slots__ = ("banks",)

    def __init__(
        self,
        banks: list[int] | None = None,
    ) -> None:
        if banks is not None:
            self.banks: list[int] = list(banks)
            while len(self.banks) < NUM_BITVECTOR_BANKS:
                self.banks.append(0)
        else:
            self.banks = [0] * NUM_BITVECTOR_BANKS

    def is_set(self, flag: int, bank: int = 0) -> bool:
        """Check if flag bits are set in the given bank."""
        return bool(self.banks[bank] & flag)

    def set_bit(self, flag: int, bank: int = 0) -> None:
        """Set flag bits in the given bank."""
        self.banks[bank] |= flag

    def remove_bit(self, flag: int, bank: int = 0) -> None:
        """Remove flag bits from the given bank."""
        self.banks[bank] &= ~flag

    def toggle_bit(self, flag: int, bank: int = 0) -> None:
        """Toggle flag bits in the given bank."""
        self.banks[bank] ^= flag

    def __repr__(self) -> str:
        return (
            f"Bitvector([{', '.join(hex(b) for b in self.banks)}])"
        )

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Bitvector):
            return self.banks == other.banks
        return NotImplemented

    def any_set(self) -> bool:
        """Return True if any bit in any bank is set."""
        return any(b != 0 for b in self.banks)

    @classmethod
    def from_values(cls, *values: int) -> Bitvector:
        """Create from up to 4 integer bank values."""
        return cls(banks=list(values))


@dataclass
class ExtraDescr:
    """Extra description data: used in objects, mobiles, and rooms.

    Ported from struct extra_descr_data in structs.h.
    """
    keyword: str = ""
    description: str = ""


@dataclass
class AffectedType:
    """An affect structure. Used in char_file_u.

    Ported from struct affected_type in structs.h.
    DO NOT CHANGE field order -- matches binary playerfile layout.
    """
    natura: int = 0       # 0=sk/sp, 1=proficienza, 2=abilita
    type: int = 0         # The type of spell that caused this
    duration: int = 0     # How long its effects will last
    modifier: int = 0     # Added to appropriate ability
    location: int = 0     # Which ability to change (APPLY_XXX)
    bitvector: Bitvector = field(default_factory=Bitvector)


@dataclass
class TrigProto:
    """Trigger prototype list entry.

    Ported from struct trig_proto_list in structs.h.
    """
    vnum: int = 0
