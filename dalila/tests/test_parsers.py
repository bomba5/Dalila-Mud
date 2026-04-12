"""Parser tests: load all world files and verify counts.

Expected file counts (from index files, -1 for $ terminator):
- .wld: ~136 files
- .mob: ~139 files
- .obj: ~130 files
- .zon: ~172 files
- .shp: ~65 files
- .trg: ~56 files

These verify that every file parses without error and entities are loaded.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Auto-detect the lib/ directory relative to project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LIB_PATH = PROJECT_ROOT / "lib"


@pytest.fixture
def lib_path() -> Path:
    """Return path to lib/ directory."""
    if not LIB_PATH.exists():
        pytest.skip("lib/ directory not found")
    return LIB_PATH


class TestWorldParser:
    """Test .wld file parsing."""

    def test_load_all_rooms(self, lib_path: Path) -> None:
        from dalila.parsers.world import load_world

        rooms = load_world(lib_path)
        assert len(rooms) > 0, "No rooms loaded"
        print(f"\nLoaded {len(rooms)} rooms from .wld files")

        # Verify basic properties of first room
        for room in rooms:
            assert room.number >= 0, f"Invalid room vnum: {room.number}"
            assert room.name, f"Room #{room.number} has no name"

    def test_room_has_directions(self, lib_path: Path) -> None:
        from dalila.parsers.world import load_world

        rooms = load_world(lib_path)
        rooms_with_exits = sum(
            1 for r in rooms if any(d is not None for d in r.dir_option)
        )
        assert rooms_with_exits > 0, "No rooms have exits"
        print(f"\n{rooms_with_exits}/{len(rooms)} rooms have exits")


class TestMobileParser:
    """Test .mob file parsing."""

    def test_load_all_mobs(self, lib_path: Path) -> None:
        from dalila.parsers.mobile import load_mobiles

        mobs = load_mobiles(lib_path)
        assert len(mobs) > 0, "No mobs loaded"
        print(f"\nLoaded {len(mobs)} mobs from .mob files")

        for mob in mobs:
            assert mob.nr >= 0, f"Invalid mob vnum: {mob.nr}"
            assert mob.player.name, f"Mob #{mob.nr} has no name"


class TestObjectParser:
    """Test .obj file parsing."""

    def test_load_all_objects(self, lib_path: Path) -> None:
        from dalila.parsers.object import load_objects

        objects = load_objects(lib_path)
        assert len(objects) > 0, "No objects loaded"
        print(f"\nLoaded {len(objects)} objects from .obj files")

        for obj in objects:
            assert obj.vnum >= 0, f"Invalid obj vnum: {obj.vnum}"
            assert obj.name, f"Object #{obj.vnum} has no name"


class TestZoneParser:
    """Test .zon file parsing."""

    def test_load_all_zones(self, lib_path: Path) -> None:
        from dalila.parsers.zone import load_zones

        zones = load_zones(lib_path)
        assert len(zones) > 0, "No zones loaded"
        print(f"\nLoaded {len(zones)} zones from .zon files")

        for zone in zones:
            assert zone.number >= 0, f"Invalid zone number: {zone.number}"
            assert zone.name, f"Zone #{zone.number} has no name"


class TestShopParser:
    """Test .shp file parsing."""

    def test_load_all_shops(self, lib_path: Path) -> None:
        from dalila.parsers.shop import load_shops

        shops = load_shops(lib_path)
        assert len(shops) > 0, "No shops loaded"
        print(f"\nLoaded {len(shops)} shops from .shp files")


class TestTriggerParser:
    """Test .trg file parsing."""

    def test_load_all_triggers(self, lib_path: Path) -> None:
        from dalila.parsers.trigger import load_triggers

        triggers = load_triggers(lib_path)
        assert len(triggers) > 0, "No triggers loaded"
        print(f"\nLoaded {len(triggers)} triggers from .trg files")

        for trig in triggers:
            assert trig.vnum >= 0, f"Invalid trigger vnum: {trig.vnum}"
            assert trig.name, f"Trigger #{trig.vnum} has no name"


class TestFullLoad:
    """Integration test: load everything and print summary."""

    def test_load_all(self, lib_path: Path) -> None:
        from dalila.parsers.world import load_world
        from dalila.parsers.mobile import load_mobiles
        from dalila.parsers.object import load_objects
        from dalila.parsers.zone import load_zones
        from dalila.parsers.shop import load_shops
        from dalila.parsers.trigger import load_triggers

        rooms = load_world(lib_path)
        mobs = load_mobiles(lib_path)
        objects = load_objects(lib_path)
        zones = load_zones(lib_path)
        shops = load_shops(lib_path)
        triggers = load_triggers(lib_path)

        print(f"\n{'=' * 60}")
        print(f"Dalila-MUD World Data Summary")
        print(f"{'=' * 60}")
        print(f"Rooms:    {len(rooms):>6}")
        print(f"Mobs:     {len(mobs):>6}")
        print(f"Objects:  {len(objects):>6}")
        print(f"Zones:    {len(zones):>6}")
        print(f"Shops:    {len(shops):>6}")
        print(f"Triggers: {len(triggers):>6}")
        print(f"{'=' * 60}")

        assert len(rooms) > 100, f"Expected 100+ rooms, got {len(rooms)}"
        assert len(mobs) > 100, f"Expected 100+ mobs, got {len(mobs)}"
        assert len(objects) > 100, f"Expected 100+ objects, got {len(objects)}"
        assert len(zones) > 50, f"Expected 50+ zones, got {len(zones)}"
        assert len(shops) > 20, f"Expected 20+ shops, got {len(shops)}"
        assert len(triggers) > 20, f"Expected 20+ triggers, got {len(triggers)}"
