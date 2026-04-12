"""Shop data structures.

Ported from struct shop_data, struct shop_buy_data in shop.h.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dalila.constants import NOWHERE


@dataclass
class ShopBuyData:
    """What item types a shop will buy.

    Ported from struct shop_buy_data in shop.h.
    """
    type: int = 0
    keywords: str = ""


@dataclass
class ShopData:
    """A shop definition.

    Ported from struct shop_data in shop.h.
    """
    virtual: int = 0                  # Virtual number of this shop
    producing: list[int] = field(default_factory=list)  # Item vnums to produce
    profit_buy: float = 1.0           # Multiply cost when selling to player
    profit_sell: float = 1.0          # Multiply cost when buying from player
    type: list[ShopBuyData] = field(default_factory=list)  # What items to trade

    # Messages (Italian text, preserve exactly)
    no_such_item1: str = ""           # Keeper hasn't got item
    no_such_item2: str = ""           # Player hasn't got item
    missing_cash1: str = ""           # Keeper hasn't got cash
    missing_cash2: str = ""           # Player hasn't got cash
    do_not_buy: str = ""              # Keeper doesn't buy such things
    message_buy: str = ""             # When player buys
    message_sell: str = ""            # When player sells

    temper1: int = 0                  # Reaction if no money
    bitvector: int = 0                # Can attack? Use bank? Cast?
    keeper: int = -1                  # Mob vnum who owns shop
    with_who: int = 0                 # Trade restrictions
    in_room: list[int] = field(default_factory=list)  # Room vnums
    open1: int = 0
    close1: int = 0
    open2: int = 0
    close2: int = 0
    bank_account: int = 0
    lastsort: int = 0

    # Dalila extensions (Adriano)
    proprietario: int = 0
    clan: int = -1
    valore: int = 0
    valore1: int = 0
    valore2: int = 0
    valore3: int = 0
    valore4: int = 0
    valore5: int = 0
