"""Shop (.shp) file parser.

Ported from boot_the_shops() in shop.c.
Handles CircleMUD shop format with Dalila extensions (proprietario, clan, etc.).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TextIO

from dalila.constants import NOWHERE
from dalila.models.shop import ShopBuyData, ShopData
from dalila.parsers.utils import fread_string, get_line, read_index_file

log = logging.getLogger(__name__)


def _read_list(fp: TextIO) -> list[int]:
    """Read a list of integers terminated by -1.

    Used for producing[] and in_room[] lists.
    """
    items: list[int] = []
    while True:
        line = get_line(fp)
        if line is None:
            break
        val = int(line.split()[0])
        if val < 0:
            break
        items.append(val)
    return items


def _read_type_list(fp: TextIO) -> list[ShopBuyData]:
    """Read a type list (item types the shop buys) terminated by -1.

    Each line is: type [keywords]
    """
    items: list[ShopBuyData] = []
    while True:
        line = get_line(fp)
        if line is None:
            break
        parts = line.split(None, 1)
        val = int(parts[0])
        if val < 0:
            break
        keywords = parts[1] if len(parts) > 1 else ""
        items.append(ShopBuyData(type=val, keywords=keywords))
    return items


def _read_int_line(fp: TextIO) -> int:
    """Read a single integer from a line."""
    line = get_line(fp)
    if line is None:
        return 0
    return int(line.split()[0])


def _read_float_line(fp: TextIO) -> float:
    """Read a single float from a line."""
    line = get_line(fp)
    if line is None:
        return 0.0
    return float(line.split()[0])


def parse_shp_file(filepath: Path) -> list[ShopData]:
    """Parse all shops from a single .shp file.

    Mirrors boot_the_shops() from shop.c.
    """
    shops: list[ShopData] = []

    with open(filepath, "r", encoding="latin-1") as fp:
        while True:
            buf = fread_string(fp)
            if not buf:
                break

            if buf.startswith("#"):
                # New shop
                shop = ShopData()
                shop.virtual = int(buf[1:].strip())

                # Producing list (item vnums, -1 terminated)
                shop.producing = _read_list(fp)

                # Profit margins
                shop.profit_buy = _read_float_line(fp)
                shop.profit_sell = _read_float_line(fp)

                # Buy types
                shop.type = _read_type_list(fp)

                # Messages
                shop.no_such_item1 = fread_string(fp)
                shop.no_such_item2 = fread_string(fp)
                shop.do_not_buy = fread_string(fp)
                shop.missing_cash1 = fread_string(fp)
                shop.missing_cash2 = fread_string(fp)
                shop.message_buy = fread_string(fp)
                shop.message_sell = fread_string(fp)

                # Integer fields
                shop.temper1 = _read_int_line(fp)
                shop.bitvector = _read_int_line(fp)
                shop.keeper = _read_int_line(fp)

                with_who = _read_int_line(fp)
                shop.with_who = with_who

                # Room list
                shop.in_room = _read_list(fp)

                shop.open1 = _read_int_line(fp)
                shop.close1 = _read_int_line(fp)
                shop.open2 = _read_int_line(fp)
                shop.close2 = _read_int_line(fp)

                # Dalila extensions
                shop.proprietario = _read_int_line(fp)
                shop.clan = _read_int_line(fp)
                shop.valore = _read_int_line(fp)
                shop.bank_account = _read_int_line(fp)
                shop.valore1 = _read_int_line(fp)
                shop.valore2 = _read_int_line(fp)
                shop.valore3 = _read_int_line(fp)
                shop.valore4 = _read_int_line(fp)
                shop.valore5 = _read_int_line(fp)

                shops.append(shop)

            elif buf.startswith("$"):
                break
            # else: could be version tag or whitespace, skip

    return shops


def load_shops(lib_path: Path) -> list[ShopData]:
    """Load all .shp files via the index file.

    Mirrors index_boot(DB_BOOT_SHP) from db.c (delegates to boot_the_shops).
    """
    prefix = lib_path / "world" / "shp"
    filenames = read_index_file(prefix)
    all_shops: list[ShopData] = []

    for fname in filenames:
        fpath = prefix / fname
        if not fpath.exists():
            log.warning("Shop file not found: %s", fpath)
            continue
        try:
            shops = parse_shp_file(fpath)
            all_shops.extend(shops)
        except Exception as e:
            log.error("Error parsing %s: %s", fpath, e)

    return all_shops
