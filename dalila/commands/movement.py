"""Movement commands: enhanced movement, doors, positions, follow/group.

Ported from act.movement.c: do_simple_move, perform_move, do_move,
do_gen_door, do_stand, do_sit, do_rest, do_sleep, do_wake, do_follow.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from dalila.constants import (
    LVL_AVATAR,
    LVL_GOD,
    NOWHERE,
    NUM_OF_DIRS,
    AffectedBy,
    Direction,
    ExitInfo,
    ItemType,
    MobFlag,
    Position,
    RoomFlag,
    SectorType,
)
from dalila.engine.handler import (
    char_from_room,
    char_to_room,
    get_char_room_vis,
    isname,
)

if TYPE_CHECKING:
    from dalila.engine.game_loop import GameWorld, LiveRoom
    from dalila.models.character import CharData
    from dalila.net.descriptor import Descriptor

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Movement cost by sector type (from constants.c)
MOVEMENT_LOSS: list[int] = [
    1,  # SECT_INSIDE
    1,  # SECT_CITY
    2,  # SECT_FIELD
    3,  # SECT_FOREST
    4,  # SECT_HILLS
    6,  # SECT_MOUNTAIN
    4,  # SECT_WATER_SWIM
    1,  # SECT_WATER_NOSWIM
    1,  # SECT_FLYING
    5,  # SECT_UNDERWATER
    1,  # SECT_ROAD
]

# Reverse direction mapping (from constants.c)
REV_DIR: list[int] = [2, 3, 0, 1, 5, 4]  # N->S, E->W, S->N, W->E, U->D, D->U

DIR_NAMES: list[str] = ["north", "east", "south", "west", "up", "down"]
DIR_NAMES_IT: list[str] = ["nord", "est", "sud", "ovest", "alto", "basso"]

# Door sub-command indices
SCMD_OPEN = 0
SCMD_CLOSE = 1
SCMD_UNLOCK = 2
SCMD_LOCK = 3

# Door need flags
NEED_OPEN = 1
NEED_CLOSED = 2
NEED_UNLOCKED = 4
NEED_LOCKED = 8

FLAGS_DOOR: list[int] = [
    NEED_CLOSED | NEED_UNLOCKED,   # open
    NEED_OPEN,                      # close
    NEED_CLOSED | NEED_LOCKED,      # unlock
    NEED_CLOSED | NEED_UNLOCKED,    # lock
]

CMD_DOOR: list[str] = ["apri", "chiudi", "sblocca", "blocca"]
CMD_DOOR_EN: list[str] = ["open", "close", "unlock", "lock"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _send(desc: Descriptor, text: str) -> None:
    """Fire-and-forget send to a descriptor."""
    asyncio.ensure_future(desc.send(text))


def _send_to_room(
    room: LiveRoom, text: str, exclude: CharData | None = None,
) -> None:
    """Send text to everyone in a room except excluded character."""
    for other in room._characters:
        if other is not exclude and other.desc:
            asyncio.ensure_future(other.desc.send(text))


def _get_position(ch: CharData) -> int:
    """Get character position. Uses char_specials if available, else POS_STANDING."""
    return getattr(ch, "position", Position.POS_STANDING)


def _set_position(ch: CharData, pos: int) -> None:
    """Set character position."""
    ch.position = pos  # type: ignore[attr-defined]


def _is_affected(ch: CharData, flag: int) -> bool:
    """Check if character has an affect flag (bank 0)."""
    if hasattr(ch, "char_specials_saved"):
        return bool(ch.char_specials_saved.affected_by[0] & flag)
    return False


# ---------------------------------------------------------------------------
# Core movement
# ---------------------------------------------------------------------------

def do_simple_move(
    ch: CharData, direction: int, world: GameWorld,
    need_specials_check: bool = False,
) -> bool:
    """Execute a simple movement in a direction.

    Ported from do_simple_move() in act.movement.c.
    Returns True if the move succeeded.
    """
    desc = ch.desc
    if desc is None:
        return False

    if ch.in_room == NOWHERE or ch.in_room not in world.rooms:
        return False

    room = world.rooms[ch.in_room]
    exit_data = room.data.dir_option[direction]

    if exit_data is None or exit_data.to_room == NOWHERE:
        return False

    dest_vnum = exit_data.to_room
    if dest_vnum not in world.rooms:
        return False

    dest_room = world.rooms[dest_vnum]

    # Check for closed door
    if exit_data.exit_info & ExitInfo.EX_ISDOOR:
        if exit_data.exit_info & ExitInfo.EX_CLOSED:
            _send(desc, "La porta e' chiusa.\r\n")
            return False

    # Charmed characters can't leave their master
    if (_is_affected(ch, AffectedBy.AFF_CHARM)
            and hasattr(ch, "master") and ch.master is not None
            and ch.master.in_room == ch.in_room):
        _send(desc, "Il pensiero di lasciare il tuo maestro "
              "ti fa scoppiare a piangere.\r\n")
        _send_to_room(room, f"{ch.player.name} scoppia in lacrime.\r\n", ch)
        return False

    # Check immobilized
    if _is_affected(ch, AffectedBy.AFF_IMMOBIL):
        _send(desc, "Sei legato!!\r\n")
        return False

    # Check sector requirements (simplified for Phase 2)
    dest_sector = dest_room.data.sector_type
    ch_level = ch.player.level

    if dest_sector == SectorType.SECT_WATER_NOSWIM and ch_level < LVL_AVATAR:
        _send(desc, "Hai bisogno di una barca per andare la'.\r\n")
        return False

    if dest_sector == SectorType.SECT_FLYING and ch_level < LVL_AVATAR:
        if not _is_affected(ch, AffectedBy.AFF_FLYING):
            _send(desc, "Devi volare per andare la'.\r\n")
            return False

    if dest_sector == SectorType.SECT_UNDERWATER and ch_level < LVL_AVATAR:
        if not _is_affected(ch, AffectedBy.AFF_WATERBREATH):
            _send(desc, "Affogheresti dopo pochi minuti se entri, "
                  "dovresti respirare in qualche modo....\r\n")
            return False

    # Calculate movement cost
    src_sect = room.data.sector_type
    if src_sect < len(MOVEMENT_LOSS):
        need_movement = MOVEMENT_LOSS[src_sect]
    else:
        need_movement = 1
    if dest_sector < len(MOVEMENT_LOSS):
        need_movement += MOVEMENT_LOSS[dest_sector]
    else:
        need_movement += 1
    need_movement = max(1, need_movement // 2)

    # Check movement points
    if ch.points.move < need_movement and ch_level < LVL_AVATAR:
        _send(desc, "Sei troppo esausto!\r\n")
        return False

    # Deduct movement points
    if ch_level < LVL_AVATAR:
        ch.points.move -= need_movement

    # Notify departure
    dir_name = DIR_NAMES_IT[direction] if direction < len(DIR_NAMES_IT) else "?"
    _send_to_room(
        room,
        f"\r\n{ch.player.name} se ne va verso {dir_name}.\r\n",
        exclude=ch,
    )

    # Move the character
    char_from_room(ch, world)
    char_to_room(ch, dest_vnum, world)

    # Notify arrival
    _send_to_room(
        dest_room,
        f"\r\n{ch.player.name} e' arrivato.\r\n",
        exclude=ch,
    )

    # Show the new room (import here to avoid circular)
    from dalila.commands.informative import look_at_room
    look_at_room(ch, desc, world)

    # Check death room
    if dest_room.data.room_flags & RoomFlag.ROOM_DEATH:
        if ch_level < LVL_AVATAR:
            _send(desc, "Una strana forza ti risucchia nel nulla!\r\n")
            # In full version: log_death_trap, extract_char
            # Phase 2: just log it
            log.warning(
                "Player %s entered death room %d",
                ch.player.name, dest_vnum,
            )

    return True


def perform_move(
    ch: CharData, direction: int, world: GameWorld,
    need_specials_check: bool = False,
) -> bool:
    """Perform a move, checking for doors.

    Ported from perform_move() in act.movement.c.
    """
    if ch.in_room == NOWHERE or ch.in_room not in world.rooms:
        return False

    room = world.rooms[ch.in_room]
    exit_data = room.data.dir_option[direction]

    if exit_data is None:
        if ch.desc:
            _send(ch.desc, "Non puoi andare in quella direzione.\r\n")
        return False

    if exit_data.to_room == NOWHERE:
        if ch.desc:
            _send(ch.desc, "Non puoi andare in quella direzione.\r\n")
        return False

    return do_simple_move(ch, direction, world, need_specials_check)


def do_move(
    ch: CharData, argument: str, desc: Descriptor,
    world: GameWorld, *, direction: int = 0,
) -> None:
    """Movement command handler.

    Ported from ACMD(do_move) in act.movement.c.
    Supports speedwalking: 'north 5' moves 5 times.
    """
    # Check position
    pos = _get_position(ch)
    if pos < Position.POS_STANDING:
        if pos == Position.POS_SLEEPING:
            _send(desc, "Sogni di muoverti.\r\n")
        elif pos == Position.POS_RESTING:
            _send(desc, "Devi prima alzarti.\r\n")
        elif pos == Position.POS_SITTING:
            _send(desc, "Devi prima alzarti.\r\n")
        else:
            _send(desc, "Non puoi muoverti!\r\n")
        return

    nr_times = 1
    arg = argument.strip()
    if arg:
        try:
            nr_times = int(arg)
            if nr_times <= 0:
                nr_times = 1
        except ValueError:
            nr_times = 1

    if nr_times > 15:
        _send(desc, "Please limit your speedwalking to 15 "
              "moves per direction.\r\n")
        return

    for _ in range(nr_times):
        if not perform_move(ch, direction, world):
            break


# ---------------------------------------------------------------------------
# Door commands: open, close, lock, unlock
# ---------------------------------------------------------------------------

def _find_door(
    ch: CharData, type_arg: str, dir_arg: str,
    cmdname: str, world: GameWorld,
) -> int:
    """Find a door by keyword and/or direction.

    Ported from find_door() in act.movement.c.
    Returns direction index or -1.
    """
    desc = ch.desc
    if ch.in_room == NOWHERE or ch.in_room not in world.rooms:
        return -1

    room = world.rooms[ch.in_room]

    if dir_arg:
        # Direction was specified
        door = _parse_direction(dir_arg)
        if door == -1:
            if desc:
                _send(desc, "Quella non e' una direzione.\r\n")
            return -1

        exit_data = room.data.dir_option[door]
        if exit_data is not None and not (exit_data.exit_info & ExitInfo.EX_HIDDEN):
            if exit_data.keyword and type_arg:
                if isname(type_arg, exit_data.keyword):
                    return door
                else:
                    if desc:
                        _send(desc, f"Non vedo {type_arg} la'.\r\n")
                    return -1
            else:
                return door
        else:
            if desc:
                _send(desc, "Non sembra esserci niente qui.\r\n")
            return -1
    else:
        # Try to locate by keyword
        if not type_arg:
            if desc:
                _send(desc, f"Cosa vuoi {cmdname}?\r\n")
            return -1

        for door in range(NUM_OF_DIRS):
            exit_data = room.data.dir_option[door]
            if (exit_data is not None
                    and not (exit_data.exit_info & ExitInfo.EX_HIDDEN)
                    and exit_data.keyword
                    and isname(type_arg, exit_data.keyword)):
                return door

        if desc:
            _send(desc, f"Non sembra esserci {type_arg} qui.\r\n")
        return -1


def _parse_direction(arg: str) -> int:
    """Parse a direction string to an index."""
    arg_lower = arg.lower()
    for i, name in enumerate(DIR_NAMES):
        if name.startswith(arg_lower):
            return i
    for i, name in enumerate(DIR_NAMES_IT):
        if name.startswith(arg_lower):
            return i
    return -1


def _has_key(ch: CharData, key_vnum: int) -> bool:
    """Check if character has a key object.

    Ported from has_key() in act.movement.c.
    """
    carrying = getattr(ch, "carrying", [])
    for obj in carrying:
        if obj.vnum == key_vnum:
            return True
    # Check held item
    from dalila.constants import WearPosition
    held = ch.equipment[WearPosition.WEAR_HOLD]
    if held is not None and hasattr(held, "vnum") and held.vnum == key_vnum:
        return True
    return False


def _do_doorcmd(
    ch: CharData, door: int, scmd: int, world: GameWorld,
) -> None:
    """Execute a door open/close/lock/unlock command.

    Ported from do_doorcmd() in act.movement.c.
    """
    if ch.in_room == NOWHERE or ch.in_room not in world.rooms:
        return

    room = world.rooms[ch.in_room]
    exit_data = room.data.dir_option[door]
    if exit_data is None:
        return

    # Find the reverse exit on the other side
    other_room_vnum = exit_data.to_room
    back = None
    if other_room_vnum != NOWHERE and other_room_vnum in world.rooms:
        other_room = world.rooms[other_room_vnum]
        rev = REV_DIR[door]
        if rev < len(other_room.data.dir_option):
            back_exit = other_room.data.dir_option[rev]
            if back_exit is not None and back_exit.to_room == ch.in_room:
                back = back_exit

    desc = ch.desc

    if scmd == SCMD_OPEN or scmd == SCMD_CLOSE:
        # Toggle closed flag
        exit_data.exit_info ^= ExitInfo.EX_CLOSED
        if back:
            back.exit_info ^= ExitInfo.EX_CLOSED
        if desc:
            _send(desc, "Ok.\r\n")
    elif scmd == SCMD_UNLOCK or scmd == SCMD_LOCK:
        # Toggle locked flag
        exit_data.exit_info ^= ExitInfo.EX_LOCKED
        if back:
            back.exit_info ^= ExitInfo.EX_LOCKED
        if desc:
            _send(desc, "*Click*\r\n")

    # Notify room
    door_word = exit_data.keyword if exit_data.keyword else "porta"
    action = CMD_DOOR_EN[scmd]
    _send_to_room(
        room,
        f"\r\n{ch.player.name} {action}s la {door_word}.\r\n",
        exclude=ch,
    )


def do_gen_door(
    ch: CharData, argument: str, desc: Descriptor,
    world: GameWorld, *, scmd: int = 0,
) -> None:
    """Generic door command: open, close, lock, unlock.

    Ported from ACMD(do_gen_door) in act.movement.c.
    """
    if _is_affected(ch, AffectedBy.AFF_IMMOBIL):
        _send(desc, "Sei legato!!\r\n")
        return

    argument = argument.strip()
    if not argument:
        _send(desc, f"{CMD_DOOR[scmd].capitalize()} cosa?\r\n")
        return

    parts = argument.split(None, 1)
    type_arg = parts[0] if parts else ""
    dir_arg = parts[1] if len(parts) > 1 else ""

    door = _find_door(ch, type_arg, dir_arg, CMD_DOOR[scmd], world)
    if door < 0:
        return

    room = world.rooms[ch.in_room]
    exit_data = room.data.dir_option[door]
    if exit_data is None:
        return

    # Check door is openable
    if not (exit_data.exit_info & ExitInfo.EX_ISDOOR):
        _send(desc, "Non puoi farlo!\r\n")
        return

    is_open = not (exit_data.exit_info & ExitInfo.EX_CLOSED)
    is_locked = bool(exit_data.exit_info & ExitInfo.EX_LOCKED)

    if not is_open and (FLAGS_DOOR[scmd] & NEED_OPEN):
        _send(desc, "Ma e' gia' chiusa!\r\n")
        return

    if is_open and (FLAGS_DOOR[scmd] & NEED_CLOSED):
        _send(desc, "Ma e' gia' aperta!\r\n")
        return

    if not is_locked and (FLAGS_DOOR[scmd] & NEED_LOCKED):
        _send(desc, "Oh...dopo tutto non era chiusa...bene!\r\n")
        return

    if is_locked and (FLAGS_DOOR[scmd] & NEED_UNLOCKED):
        _send(desc, "Sembra chiusa a chiave.\r\n")
        return

    # Check for key (lock/unlock only)
    if scmd in (SCMD_LOCK, SCMD_UNLOCK):
        key_vnum = exit_data.key
        if key_vnum >= 0 and not _has_key(ch, key_vnum):
            if ch.player.level < LVL_GOD:
                _send(desc, "Non sembra tu abbia la chiave giusta.\r\n")
                return

    _do_doorcmd(ch, door, scmd, world)


# ---------------------------------------------------------------------------
# Position commands: stand, sit, rest, sleep, wake
# ---------------------------------------------------------------------------

def do_stand(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Stand up.

    Ported from ACMD(do_stand) in act.movement.c.
    """
    if _is_affected(ch, AffectedBy.AFF_IMMOBIL):
        _send(desc, "Sei legato!!\r\n")
        return

    pos = _get_position(ch)

    match pos:
        case Position.POS_STANDING:
            _send(desc, "Sei gia' in piedi.\r\n")
        case Position.POS_SITTING:
            _send(desc, "Ti alzi.\r\n")
            if ch.in_room in world.rooms:
                _send_to_room(
                    world.rooms[ch.in_room],
                    f"\r\n{ch.player.name} si alza.\r\n",
                    exclude=ch,
                )
            _set_position(ch, Position.POS_STANDING)
        case Position.POS_RESTING:
            _send(desc, "Smetti di riposarti e ti alzi.\r\n")
            if ch.in_room in world.rooms:
                _send_to_room(
                    world.rooms[ch.in_room],
                    f"\r\n{ch.player.name} smette di riposarsi, e si alza.\r\n",
                    exclude=ch,
                )
            _set_position(ch, Position.POS_STANDING)
        case Position.POS_SLEEPING:
            _send(desc, "Devi prima svegliarti.\r\n")
        case Position.POS_FIGHTING:
            _send(desc, "Do you not consider fighting as standing?\r\n")
        case _:
            _send(desc, "Smetti di galleggiare e posi i piedi sul terreno.\r\n")
            if ch.in_room in world.rooms:
                _send_to_room(
                    world.rooms[ch.in_room],
                    f"\r\n{ch.player.name} smette di galleggiare e "
                    "posa i piedi sul terreno.\r\n",
                    exclude=ch,
                )
            _set_position(ch, Position.POS_STANDING)


def do_sit(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Sit down.

    Ported from ACMD(do_sit) in act.movement.c.
    """
    pos = _get_position(ch)

    match pos:
        case Position.POS_STANDING:
            _send(desc, "Ti siedi.\r\n")
            if ch.in_room in world.rooms:
                _send_to_room(
                    world.rooms[ch.in_room],
                    f"\r\n{ch.player.name} si siede.\r\n",
                    exclude=ch,
                )
            _set_position(ch, Position.POS_SITTING)
        case Position.POS_SITTING:
            _send(desc, "Sei gia' seduto.\r\n")
        case Position.POS_RESTING:
            _send(desc, "Smetti di riposare e ti alzi.\r\n")
            if ch.in_room in world.rooms:
                _send_to_room(
                    world.rooms[ch.in_room],
                    f"\r\n{ch.player.name} smette di riposare.\r\n",
                    exclude=ch,
                )
            _set_position(ch, Position.POS_SITTING)
        case Position.POS_SLEEPING:
            _send(desc, "Ti devi prima svegliare.\r\n")
        case Position.POS_FIGHTING:
            _send(desc, "Sedersi mentre stai combattendo? Sei matto?\r\n")
        case _:
            _send(desc, "Smetti di galleggiare e ti siedi.\r\n")
            if ch.in_room in world.rooms:
                _send_to_room(
                    world.rooms[ch.in_room],
                    f"\r\n{ch.player.name} smette di galleggiare "
                    "e si siede.\r\n",
                    exclude=ch,
                )
            _set_position(ch, Position.POS_SITTING)


def do_rest(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Rest.

    Ported from ACMD(do_rest) in act.movement.c.
    """
    pos = _get_position(ch)

    match pos:
        case Position.POS_STANDING:
            _send(desc, "Ti siedi a riposare le stanche ossa.\r\n")
            if ch.in_room in world.rooms:
                _send_to_room(
                    world.rooms[ch.in_room],
                    f"\r\n{ch.player.name} si siede e riposa.\r\n",
                    exclude=ch,
                )
            _set_position(ch, Position.POS_RESTING)
        case Position.POS_SITTING:
            _send(desc, "Riposi le stanche ossa.\r\n")
            if ch.in_room in world.rooms:
                _send_to_room(
                    world.rooms[ch.in_room],
                    f"\r\n{ch.player.name} riposa.\r\n",
                    exclude=ch,
                )
            _set_position(ch, Position.POS_RESTING)
        case Position.POS_RESTING:
            _send(desc, "Stai gia' riposando.\r\n")
        case Position.POS_SLEEPING:
            _send(desc, "Ti devi prima svegliare.\r\n")
        case Position.POS_FIGHTING:
            _send(desc, "Riposare mentre combatti?  Sei pazzo?\r\n")
        case _:
            _send(desc, "Smetti di galleggiare e ti siedi a riposare.\r\n")
            if ch.in_room in world.rooms:
                _send_to_room(
                    world.rooms[ch.in_room],
                    f"\r\n{ch.player.name} smette di riposare "
                    "e si siede a riposare.\r\n",
                    exclude=ch,
                )
            _set_position(ch, Position.POS_RESTING)


def do_sleep(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Go to sleep.

    Ported from ACMD(do_sleep) in act.movement.c.
    """
    pos = _get_position(ch)

    match pos:
        case Position.POS_STANDING | Position.POS_SITTING | Position.POS_RESTING:
            _send(desc, "Dormi.\r\n")
            if ch.in_room in world.rooms:
                _send_to_room(
                    world.rooms[ch.in_room],
                    f"\r\n{ch.player.name} si sdraia e dorme.\r\n",
                    exclude=ch,
                )
            _set_position(ch, Position.POS_SLEEPING)
        case Position.POS_SLEEPING:
            _send(desc, "Stai gia' dormendo.\r\n")
        case Position.POS_FIGHTING:
            _send(desc, "Dormire mentre combatti? Sei pazzo?\r\n")
        case _:
            _send(desc, "Smetti di galleggiare e ti metti a dormire.\r\n")
            if ch.in_room in world.rooms:
                _send_to_room(
                    world.rooms[ch.in_room],
                    f"\r\n{ch.player.name} smette di galleggiare "
                    "e si addormenta.\r\n",
                    exclude=ch,
                )
            _set_position(ch, Position.POS_SLEEPING)


def do_wake(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Wake up (self or another).

    Ported from ACMD(do_wake) in act.movement.c.
    """
    arg = argument.strip()

    if arg:
        # Try to wake another character
        pos = _get_position(ch)
        if pos == Position.POS_SLEEPING:
            _send(desc, "Forse ti devi svegliare prima.\r\n")
            return

        vict = get_char_room_vis(ch, arg, world)
        if vict is None:
            _send(desc, "Non c'e' nessuno qui con quel nome.\r\n")
            return
        if vict is ch:
            pass  # Fall through to self-wake below
        else:
            vict_pos = _get_position(vict)
            if vict_pos > Position.POS_SLEEPING:
                _send(desc, f"{vict.player.name} e' gia sveglio.\r\n")
                return
            if _is_affected(vict, AffectedBy.AFF_SLEEP):
                _send(desc, f"Non puoi svegliare {vict.player.name}!\r\n")
                return
            if vict_pos < Position.POS_SLEEPING:
                _send(desc, f"{vict.player.name} non sta bene!\r\n")
                return

            _send(desc, f"Svegli {vict.player.name}.\r\n")
            if vict.desc:
                _send(vict.desc, f"Sei svegliato {ch.player.name}.\r\n")
            _set_position(vict, Position.POS_SITTING)
            return

    # Wake self
    if _is_affected(ch, AffectedBy.AFF_SLEEP):
        _send(desc, "Non puoi svegliarti!\r\n")
        return

    pos = _get_position(ch)
    if pos > Position.POS_SLEEPING:
        _send(desc, "Sei gia' sveglio...\r\n")
        return

    _send(desc, "Ti svegli e ti siedi.\r\n")
    if ch.in_room in world.rooms:
        _send_to_room(
            world.rooms[ch.in_room],
            f"\r\n{ch.player.name} si sveglia.\r\n",
            exclude=ch,
        )
    _set_position(ch, Position.POS_SITTING)


# ---------------------------------------------------------------------------
# Follow/group commands
# ---------------------------------------------------------------------------

def do_follow(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Follow another character.

    Ported from ACMD(do_follow) in act.movement.c.
    Simplified for Phase 2: basic follow/unfollow.
    """
    if _is_affected(ch, AffectedBy.AFF_IMMOBIL):
        _send(desc, "Sei legato!!\r\n")
        return

    arg = argument.strip()
    if not arg:
        _send(desc, "Chi vuoi seguire?\r\n")
        return

    leader = get_char_room_vis(ch, arg, world)
    if leader is None:
        _send(desc, "Non c'e' nessuno qui con quel nome.\r\n")
        return

    if leader is ch:
        # Stop following
        if hasattr(ch, "master") and ch.master is not None:
            master = ch.master
            _send(desc, "Smetti di seguire.\r\n")
            ch.master = None  # type: ignore[attr-defined]
            # Remove from master's followers
            if hasattr(master, "followers"):
                if ch in master.followers:
                    master.followers.remove(ch)
        else:
            _send(desc, "Non stai seguendo nessuno.\r\n")
        return

    # Can't follow if already following someone else
    if hasattr(ch, "master") and ch.master is not None:
        _send(desc, f"Stai gia' seguendo {ch.master.player.name}.\r\n")
        return

    # Start following
    ch.master = leader  # type: ignore[attr-defined]
    if not hasattr(leader, "followers"):
        leader.followers = []  # type: ignore[attr-defined]
    leader.followers.append(ch)  # type: ignore[attr-defined]

    _send(desc, f"Ora segui {leader.player.name}.\r\n")
    if leader.desc:
        _send(leader.desc,
              f"\r\n{ch.player.name} ora ti segue.\r\n")


def do_group(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Group management command.

    Ported from ACMD(do_group) in act.other.c.
    Simplified for Phase 2.
    """
    arg = argument.strip()

    if not arg:
        # Show group info
        if not _is_affected(ch, AffectedBy.AFF_GROUP):
            _send(desc, "Non sei membro di nessun gruppo!\r\n")
            return

        _send(desc, f"Il gruppo di {ch.player.name}:\r\n")
        _send(desc, f"  {ch.player.name} [HP:{ch.points.hit}/{ch.points.max_hit}"
              f" MN:{ch.points.mana}/{ch.points.max_mana}"
              f" MV:{ch.points.move}/{ch.points.max_move}]\r\n")

        followers = getattr(ch, "followers", [])
        for f in followers:
            if _is_affected(f, AffectedBy.AFF_GROUP):
                _send(desc, f"  {f.player.name} "
                      f"[HP:{f.points.hit}/{f.points.max_hit}"
                      f" MN:{f.points.mana}/{f.points.max_mana}"
                      f" MV:{f.points.move}/{f.points.max_move}]\r\n")
        return

    # Group/ungroup a target
    vict = get_char_room_vis(ch, arg, world)
    if vict is None:
        _send(desc, "Non c'e' nessuno qui con quel nome.\r\n")
        return

    if vict is ch:
        # Toggle own group flag
        if _is_affected(ch, AffectedBy.AFF_GROUP):
            ch.char_specials_saved.affected_by[0] &= ~AffectedBy.AFF_GROUP
            _send(desc, "Sciogli il gruppo.\r\n")
        else:
            ch.char_specials_saved.affected_by[0] |= AffectedBy.AFF_GROUP
            _send(desc, "Formi un gruppo.\r\n")
        return

    # Check if vict follows ch
    master = getattr(vict, "master", None)
    if master is not ch:
        _send(desc, f"{vict.player.name} non ti segue.\r\n")
        return

    if _is_affected(vict, AffectedBy.AFF_GROUP):
        vict.char_specials_saved.affected_by[0] &= ~AffectedBy.AFF_GROUP
        _send(desc, f"{vict.player.name} non e' piu' nel gruppo.\r\n")
        if vict.desc:
            _send(vict.desc, "Non sei piu' nel gruppo.\r\n")
    else:
        if not _is_affected(ch, AffectedBy.AFF_GROUP):
            ch.char_specials_saved.affected_by[0] |= AffectedBy.AFF_GROUP

        vict.char_specials_saved.affected_by[0] |= AffectedBy.AFF_GROUP
        _send(desc, f"{vict.player.name} e' ora nel gruppo.\r\n")
        if vict.desc:
            _send(vict.desc,
                  f"Sei stato accettato nel gruppo di {ch.player.name}.\r\n")
