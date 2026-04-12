"""Game world singleton and pulse-based heartbeat system.

Ported from game_loop() heartbeat() in comm.c, weather_and_time()
in weather.c, zone_update() in db.c.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dalila.constants import (
    NOWHERE,
    SECS_PER_MUD_HOUR,
    Direction,
    SkyCondition,
    SunState,
)
from dalila.models.character import CharData, CharPlayerData, TimeInfoData
from dalila.models.object import ObjData
from dalila.models.room import RoomData
from dalila.models.zone import ZoneData

log = logging.getLogger(__name__)

# Pulse constants from structs.h
# OPT_USEC = 100000 -> 10 passes per second
PASSES_PER_SEC: int = 10
PULSE_ZONE: int = 10 * PASSES_PER_SEC      # 10 seconds
PULSE_MOBILE: int = 10 * PASSES_PER_SEC    # 10 seconds
PULSE_VIOLENCE: int = 3 * PASSES_PER_SEC   # 3 seconds (unused in Phase 1)
DELAY: int = 2  # Blizzard's delay factor for weather ticks

# MUD time: one MUD hour = DELAY * SECS_PER_MUD_HOUR real seconds
# = 2 * 75 = 150 real seconds
PULSE_TIMECOUNT: int = DELAY * SECS_PER_MUD_HOUR * PASSES_PER_SEC


class LiveRoom:
    """A room instance in the running game world.

    Wraps the static RoomData from parsers with runtime state
    (characters present, objects on the ground, light level).
    """

    __slots__ = ("data", "_characters", "_objects")

    def __init__(self, data: RoomData) -> None:
        self.data = data
        self._characters: list[CharData] = []
        self._objects: list[ObjData] = []

    @property
    def vnum(self) -> int:
        return self.data.number

    @property
    def name(self) -> str:
        return self.data.name

    @property
    def description(self) -> str:
        return self.data.description


class GameWorld:
    """Singleton holding all game state.

    Combines the roles of world[], zone_table[], mob_proto[],
    obj_proto[], time_info, and weather_data from the C global state.
    """

    def __init__(self) -> None:
        # World data (keyed by vnum)
        self.rooms: dict[int, LiveRoom] = {}
        self.mob_protos: dict[int, CharData] = {}  # mob vnum -> prototype
        self.obj_protos: dict[int, ObjData] = {}    # obj vnum -> prototype
        self.zones: list[ZoneData] = []
        self.shops: list[Any] = []
        self.triggers: list[Any] = []

        # Runtime state
        self.players: list[CharData] = []  # Online player characters
        self.pulse: int = 0

        # MUD time (from time_info in db.c)
        self.time_info: TimeInfoData = TimeInfoData(
            hours=0, day=0, month=0, year=1000,
        )

        # Sunlight state
        self.sunlight: int = SunState.SUN_DARK

        # Text files (loaded from lib/text/)
        self.greeting_text: str = ""
        self.motd_text: str = ""
        self.imotd_text: str = ""
        self.menu_text: str = ""
        self.background_text: str = ""

        # Known players (in-memory store for Phase 1, no persistence)
        self.known_players: dict[str, CharData] = {}  # name -> char

        # Mortal start room vnum (fallback)
        self.mortal_start_room: int = NOWHERE

    def load_world_data(self, lib_path: Path) -> None:
        """Load all world data using Phase 0 parsers.

        Mirrors boot_db() / boot_world() from db.c.
        """
        from dalila.parsers.mobile import load_mobiles
        from dalila.parsers.object import load_objects
        from dalila.parsers.shop import load_shops
        from dalila.parsers.trigger import load_triggers
        from dalila.parsers.world import load_world
        from dalila.parsers.zone import load_zones

        # Load rooms
        room_list = load_world(lib_path)
        for room in room_list:
            self.rooms[room.number] = LiveRoom(room)
        log.info("  %d rooms loaded", len(self.rooms))

        # Load zones
        self.zones = load_zones(lib_path)
        log.info("  %d zones loaded", len(self.zones))

        # Assign rooms to zones
        self._assign_rooms_to_zones()

        # Load mob prototypes
        mob_list = load_mobiles(lib_path)
        for mob in mob_list:
            self.mob_protos[mob.nr] = mob
        log.info("  %d mob prototypes loaded", len(self.mob_protos))

        # Load object prototypes
        obj_list = load_objects(lib_path)
        for obj in obj_list:
            self.obj_protos[obj.vnum] = obj
        log.info("  %d object prototypes loaded", len(self.obj_protos))

        # Load shops
        shop_list = load_shops(lib_path)
        self.shops = shop_list
        log.info("  %d shops loaded", len(self.shops))

        # Load triggers
        trig_list = load_triggers(lib_path)
        self.triggers = trig_list
        log.info("  %d triggers loaded", len(self.triggers))

        # Load text files
        self._load_text_files(lib_path)

        # Find a sensible mortal start room
        self._find_start_room()

        # Initialize MUD time from real time
        self._init_mud_time()

        # Initialize weather
        self._init_weather()

    def _assign_rooms_to_zones(self) -> None:
        """Assign each room to its zone based on vnum ranges.

        Mirrors renum_zone_table() from db.c.
        """
        for room in self.rooms.values():
            for i, zone in enumerate(self.zones):
                if room.data.number <= zone.top:
                    room.data.zone = i
                    break

    def _load_text_files(self, lib_path: Path) -> None:
        """Load text files from lib/text/.

        Mirrors file_to_string_alloc() calls in boot_db().
        """
        text_dir = lib_path / "text"

        for filename, attr in [
            ("greetings", "greeting_text"),
            ("motd", "motd_text"),
            ("imotd", "imotd_text"),
            ("menu", "menu_text"),
            ("background", "background_text"),
        ]:
            fpath = text_dir / filename
            if fpath.exists():
                try:
                    content = fpath.read_text(encoding="latin-1")
                    # The C version uses \r\n line endings
                    content = content.replace("\n", "\r\n")
                    setattr(self, attr, content)
                except Exception as e:
                    log.warning("Could not load %s: %s", fpath, e)

    def _find_start_room(self) -> None:
        """Find the mortal start room.

        The C version has r_mortal_start_room[] indexed by hometown.
        For Phase 1, just find room 3001 (classic CircleMUD start) or
        the first room available.
        """
        for candidate in [3001, 100, 0]:
            if candidate in self.rooms:
                self.mortal_start_room = candidate
                return
        # Fallback: first room
        if self.rooms:
            self.mortal_start_room = next(iter(self.rooms))

    def _init_mud_time(self) -> None:
        """Initialize MUD time based on real time.

        Mirrors mud_time_passed() from utils.c as used in boot_db().
        """
        now = int(time.time())
        beginning_of_time = 650336715  # From db.c: beginning_of_time

        secs = now - beginning_of_time
        if secs < 0:
            secs = 0

        hours = secs // (SECS_PER_MUD_HOUR * DELAY)
        secs %= (SECS_PER_MUD_HOUR * DELAY)

        self.time_info.hours = hours % 24
        hours //= 24
        self.time_info.day = hours % 35
        hours //= 35
        self.time_info.month = hours % 17
        hours //= 17
        self.time_info.year = hours + 1000

        # Set sunlight based on hour
        if self.time_info.hours < 5:
            self.sunlight = SunState.SUN_DARK
        elif self.time_info.hours < 7:
            self.sunlight = SunState.SUN_RISE
        elif self.time_info.hours < 20:
            self.sunlight = SunState.SUN_LIGHT
        elif self.time_info.hours < 22:
            self.sunlight = SunState.SUN_SET
        else:
            self.sunlight = SunState.SUN_DARK

        log.info(
            "  MUD time: %d:%02d, Day %d of Month %d, Year %d",
            self.time_info.hours, 0,
            self.time_info.day + 1,
            self.time_info.month + 1,
            self.time_info.year,
        )

    def _init_weather(self) -> None:
        """Initialize weather for all zones.

        Mirrors the weather initialization in boot_db() from db.c.
        """
        for zone in self.zones:
            zone.pressure = 960 + random.randint(0, 80)
            zone.change = 0
            if zone.pressure <= 980:
                zone.sky = SkyCondition.SKY_LIGHTNING
            elif zone.pressure <= 1000:
                zone.sky = SkyCondition.SKY_RAINING
            elif zone.pressure <= 1020:
                zone.sky = SkyCondition.SKY_CLOUDY
            else:
                zone.sky = SkyCondition.SKY_CLOUDLESS

    def heartbeat(self) -> None:
        """Execute periodic game tasks based on the current pulse.

        Mirrors heartbeat() from comm.c.
        - zone_update (PULSE_ZONE = 10 seconds)
        - weather_and_time (PULSE_TIMECOUNT = 150 seconds)
        - perform_violence (PULSE_VIOLENCE = 3 seconds) -- Phase 3
        """
        pulse = self.pulse

        if pulse % PULSE_VIOLENCE == 0:
            from dalila.combat.fight import perform_violence
            perform_violence(self)

        if pulse % PULSE_ZONE == 0:
            self._zone_update()

        if pulse % PULSE_TIMECOUNT == 0:
            self._weather_and_time()

    def _zone_update(self) -> None:
        """Process zone resets (repopulation).

        Mirrors zone_update() from db.c. Phase 1 stub: ages zones
        and logs resets, but doesn't actually place mobs/objects
        (that requires handler.c porting from Phase 2+).
        """
        for zone in self.zones:
            zone.age += 1
            if zone.age >= zone.lifespan:
                # In the full version this would execute reset commands
                # For Phase 1, just reset the age
                if zone.reset_mode == 2:
                    # Mode 2: always reset
                    zone.age = 0
                elif zone.reset_mode == 1:
                    # Mode 1: reset if no players in zone
                    # TODO: Check for players when we have zone->room mapping
                    zone.age = 0
                else:
                    # Mode 0: don't reset
                    pass

    def _weather_and_time(self) -> None:
        """Advance MUD time by one hour and update weather.

        Mirrors weather_and_time() from weather.c.
        """
        self._another_hour()
        self._weather_change()

    def _another_hour(self) -> None:
        """Advance the MUD clock by one hour.

        Mirrors another_hour() from weather.c.
        """
        self.time_info.hours += 1

        # Sunlight transitions
        match self.time_info.hours:
            case 5:
                self.sunlight = SunState.SUN_RISE
            case 7:
                self.sunlight = SunState.SUN_LIGHT
            case 20:
                self.sunlight = SunState.SUN_SET
            case 22:
                self.sunlight = SunState.SUN_DARK

        # Day rollover
        if self.time_info.hours > 23:
            self.time_info.hours -= 24
            self.time_info.day += 1

            if self.time_info.day > 34:
                self.time_info.day = 0
                self.time_info.month += 1

                if self.time_info.month > 16:
                    self.time_info.month = 0
                    self.time_info.year += 1

    def _weather_change(self) -> None:
        """Update weather for all zones.

        Mirrors weather_change() from weather.c.
        Simplified for Phase 1: no send_to_outdoor yet.
        """
        for zone in self.zones:
            # Seasonal pressure bias
            if 9 <= self.time_info.month <= 16:
                diff = -2 if zone.pressure > 985 else 2
            else:
                diff = -2 if zone.pressure > 1015 else 2

            # Random weather fluctuation
            zone.change += (
                random.randint(1, 4) * diff
                + random.randint(2, 12) - random.randint(2, 12)
            )
            zone.change = max(-12, min(12, zone.change))

            zone.pressure += zone.change
            zone.pressure = max(960, min(1040, zone.pressure))

            # Sky state transitions
            change = 0
            match zone.sky:
                case SkyCondition.SKY_CLOUDLESS:
                    if zone.pressure < 990:
                        change = 1
                    elif zone.pressure < 1010 and random.randint(1, 4) == 1:
                        change = 1
                case SkyCondition.SKY_CLOUDY:
                    if zone.pressure < 970:
                        change = 2
                    elif zone.pressure < 990:
                        if random.randint(1, 4) == 1:
                            change = 2
                    elif zone.pressure > 1030:
                        if random.randint(1, 4) == 1:
                            change = 3
                case SkyCondition.SKY_RAINING:
                    if zone.pressure < 970:
                        if random.randint(1, 4) == 1:
                            change = 4
                    elif zone.pressure > 1030:
                        change = 5
                    elif zone.pressure > 1010:
                        if random.randint(1, 4) == 1:
                            change = 5
                case SkyCondition.SKY_LIGHTNING:
                    if zone.pressure > 1010:
                        change = 6
                    elif zone.pressure > 990:
                        if random.randint(1, 4) == 1:
                            change = 6

            match change:
                case 1:
                    zone.sky = SkyCondition.SKY_CLOUDY
                case 2:
                    zone.sky = SkyCondition.SKY_RAINING
                case 3:
                    zone.sky = SkyCondition.SKY_CLOUDLESS
                case 4:
                    zone.sky = SkyCondition.SKY_LIGHTNING
                case 5:
                    zone.sky = SkyCondition.SKY_CLOUDY
                case 6:
                    zone.sky = SkyCondition.SKY_RAINING
