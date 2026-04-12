"""Communication commands: say, tell, whisper, shout, gossip, emote.

Ported from act.comm.c: do_say, do_tell, do_spec_comm (whisper/ask),
do_gen_comm (shout/holler/gossip/auction/gratz/OOC), do_gsay, do_emote.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from dalila.constants import (
    NOWHERE,
    AffectedBy,
    PlayerFlag,
    Position,
    PreferenceFlag,
    RoomFlag,
)
from dalila.engine.handler import get_char_room_vis, get_char_vis

if TYPE_CHECKING:
    from dalila.engine.game_loop import GameWorld, LiveRoom
    from dalila.models.character import CharData
    from dalila.net.descriptor import Descriptor

log = logging.getLogger(__name__)


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


def _is_affected(ch: CharData, flag: int) -> bool:
    """Check if character has an affect flag (bank 0)."""
    if hasattr(ch, "char_specials_saved"):
        return bool(ch.char_specials_saved.affected_by[0] & flag)
    return False


def _is_soundproof(ch: CharData, world: GameWorld) -> bool:
    """Check if the character's room is soundproof."""
    if ch.in_room != NOWHERE and ch.in_room in world.rooms:
        return bool(world.rooms[ch.in_room].data.room_flags & RoomFlag.ROOM_SOUNDPROOF)
    return False


# ---------------------------------------------------------------------------
# SAY (dici)
# ---------------------------------------------------------------------------

def do_say(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Speak to the room.

    Ported from ACMD(do_say) in act.comm.c.
    Enhanced for Phase 2: handles silence, soundproof rooms,
    punctuation-based verb variation.
    """
    message = argument.strip()
    if not message:
        _send(desc, "Si, ma COSA vuoi dire?\r\n")
        return

    if _is_affected(ch, AffectedBy.AFF_SILENCE):
        _send(desc, "Non riesci a parlare, una strana forza "
              "ti impedisce di emettere suoni?\r\n")
        return

    if _is_soundproof(ch, world):
        _send(desc, "Cerchi di parlare ma non riesci a proferire dei suoni.\r\n")
        if ch.in_room in world.rooms:
            _send_to_room(
                world.rooms[ch.in_room],
                f"\r\n&5{ch.player.name} cerca di dire qualcosa "
                "ma non riesci a sentire niente.&0\r\n",
                exclude=ch,
            )
        return

    # Determine verb based on punctuation
    last_char = message[-1] if message else "."
    match last_char:
        case "?":
            verb_self = "Chiedi"
            verb_other = "chiede"
        case "!":
            verb_self = "Esclami"
            verb_other = "esclama"
        case _:
            verb_self = "Dici"
            verb_other = "dice"

    _send(desc, f"&5{verb_self}, '{message}'&0\r\n")

    if ch.in_room in world.rooms:
        _send_to_room(
            world.rooms[ch.in_room],
            f"\r\n&5{ch.player.name} {verb_other}, '{message}'&0\r\n",
            exclude=ch,
        )


# ---------------------------------------------------------------------------
# TELL (parla a)
# ---------------------------------------------------------------------------

def do_tell(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Tell a message to a specific player.

    Ported from ACMD(do_tell) in act.comm.c.
    """
    if _is_affected(ch, AffectedBy.AFF_SILENCE):
        _send(desc, "Non riesci a parlare, una strana forza "
              "ti impedisce di emettere suoni?\r\n")
        return

    parts = argument.strip().split(None, 1)
    if len(parts) < 2:
        _send(desc, "A chi vuoi dire cosa??\r\n")
        return

    target_name = parts[0]
    message = parts[1]

    vict = get_char_vis(ch, target_name, world)
    if vict is None:
        _send(desc, "Non c'e' nessuno con quel nome.\r\n")
        return

    if vict is ch:
        _send(desc, "Tenti di dirti qualche cosa.\r\n")
        return

    if _is_soundproof(ch, world):
        _send(desc, "Le pareti sembrano assorbire le tue parole.\r\n")
        return

    # Send the tell
    _send(desc, f"&1Dici a {vict.player.name}, '{message}'&0\r\n")

    if vict.desc:
        _send(vict.desc,
              f"\r\n&1{ch.player.name} ti dice, '{message}'&0\r\n")


# ---------------------------------------------------------------------------
# WHISPER (sussurra)
# ---------------------------------------------------------------------------

def do_whisper(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Whisper to a character in the same room.

    Ported from ACMD(do_spec_comm) with SCMD_WHISPER in act.comm.c.
    """
    if _is_affected(ch, AffectedBy.AFF_SILENCE):
        _send(desc, "Non riesci a parlare, una strana forza "
              "ti impedisce di emettere suoni?\r\n")
        return

    parts = argument.strip().split(None, 1)
    if len(parts) < 2:
        _send(desc, "A chi vuoi sussurrare.. e cosa??\r\n")
        return

    target_name = parts[0]
    message = parts[1]

    vict = get_char_room_vis(ch, target_name, world)
    if vict is None:
        _send(desc, "Non c'e' nessuno qui con quel nome.\r\n")
        return
    if vict is ch:
        _send(desc, "Non puoi avvicinare la tua bocca abbastanza "
              "al tuo orecchio...\r\n")
        return

    _send(desc, f"Sussurri a {vict.player.name}, '{message}'\r\n")
    if vict.desc:
        _send(vict.desc,
              f"\r\n{ch.player.name} ti sussurra, '{message}'\r\n")

    # Others see the whisper happening
    if ch.in_room in world.rooms:
        room = world.rooms[ch.in_room]
        for other in room._characters:
            if other is not ch and other is not vict and other.desc:
                asyncio.ensure_future(other.desc.send(
                    f"\r\n{ch.player.name} sussurra qualche cosa "
                    f"a {vict.player.name}.\r\n"
                ))


# ---------------------------------------------------------------------------
# SHOUT (urla) — zone-wide communication
# ---------------------------------------------------------------------------

def do_shout(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Shout a message to everyone in the same zone.

    Ported from ACMD(do_gen_comm) with SCMD_SHOUT in act.comm.c.
    """
    if _is_affected(ch, AffectedBy.AFF_SILENCE):
        _send(desc, "Non riesci a parlare, una strana forza "
              "ti impedisce di emettere suoni?\r\n")
        return

    if _is_soundproof(ch, world):
        _send(desc, "Le pareti sembrano assorbire le tue parole.\r\n")
        return

    message = argument.strip()
    if not message:
        _send(desc, "Si, urla, bene, urla dobbiamo, ma COSA???\r\n")
        return

    _send(desc, f"&3Urli, '{message}'&0\r\n")

    # Send to all players in the same zone
    if ch.in_room not in world.rooms:
        return

    ch_zone = world.rooms[ch.in_room].data.zone

    for player in world.players:
        if player is ch:
            continue
        if player.desc is None:
            continue
        if player.in_room not in world.rooms:
            continue
        if world.rooms[player.in_room].data.room_flags & RoomFlag.ROOM_SOUNDPROOF:
            continue
        if world.rooms[player.in_room].data.zone != ch_zone:
            continue

        _send(player.desc,
              f"\r\n&3{ch.player.name} urla, '{message}'&0\r\n")


# ---------------------------------------------------------------------------
# GOSSIP (gossip) — global communication channel
# ---------------------------------------------------------------------------

def do_gossip(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Global gossip channel.

    Ported from ACMD(do_gen_comm) with SCMD_GOSSIP in act.comm.c.
    """
    if _is_affected(ch, AffectedBy.AFF_SILENCE):
        _send(desc, "Non riesci a parlare, una strana forza "
              "ti impedisce di emettere suoni?\r\n")
        return

    if _is_soundproof(ch, world):
        _send(desc, "Le pareti sembrano assorbire le tue parole.\r\n")
        return

    message = argument.strip()
    if not message:
        _send(desc, "Si, dice, bene, dice dobbiamo, ma COSA???\r\n")
        return

    _send(desc, f"&3Dici, '{message}'&0\r\n")

    # Send to all connected players
    for player in world.players:
        if player is ch:
            continue
        if player.desc is None:
            continue
        if player.in_room in world.rooms:
            if world.rooms[player.in_room].data.room_flags & RoomFlag.ROOM_SOUNDPROOF:
                continue

        _send(player.desc,
              f"\r\n&3{ch.player.name} dice, '{message}'&0\r\n")


# ---------------------------------------------------------------------------
# EMOTE (:) — custom emote
# ---------------------------------------------------------------------------

def do_emote(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Custom emote action.

    Usage: emote dances wildly. -> 'Yourname dances wildly.'
    Also triggered by ':'
    """
    message = argument.strip()
    if not message:
        _send(desc, "Si??\r\n")
        return

    if ch.in_room in world.rooms:
        room = world.rooms[ch.in_room]
        for person in room._characters:
            if person.desc:
                _send(person.desc,
                      f"\r\n{ch.player.name} {message}\r\n")


# ---------------------------------------------------------------------------
# GROUP SAY (dici al gruppo)
# ---------------------------------------------------------------------------

def do_gsay(
    ch: CharData, argument: str, desc: Descriptor, world: GameWorld,
) -> None:
    """Say something to your group.

    Ported from ACMD(do_gsay) in act.comm.c.
    """
    if not _is_affected(ch, AffectedBy.AFF_GROUP):
        _send(desc, "Non sei membro di nessun gruppo!\r\n")
        return

    if _is_affected(ch, AffectedBy.AFF_SILENCE):
        _send(desc, "Non riesci a parlare, una strana forza "
              "ti impedisce di emettere suoni?\r\n")
        return

    message = argument.strip()
    if not message:
        _send(desc, "SI, ma cosa vuoi dire al gruppo?\r\n")
        return

    _send(desc, f"&2Dici al gruppo, '{message}'&0\r\n")

    # Find group leader
    master = getattr(ch, "master", None)
    leader = master if master is not None else ch

    # Send to leader (if not self)
    if leader is not ch and _is_affected(leader, AffectedBy.AFF_GROUP):
        if leader.desc:
            _send(leader.desc,
                  f"\r\n&2{ch.player.name} dice al gruppo, "
                  f"'{message}'&0\r\n")

    # Send to followers
    followers = getattr(leader, "followers", [])
    for f in followers:
        if f is not ch and _is_affected(f, AffectedBy.AFF_GROUP):
            if f.desc:
                _send(f.desc,
                      f"\r\n&2{ch.player.name} dice al gruppo, "
                      f"'{message}'&0\r\n")
