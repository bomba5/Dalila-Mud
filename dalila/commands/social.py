"""Social command framework.

Ported from act.social.c: boot_social_messages, do_action, find_action.
Socials are emote-like commands (hug, slap, wave, etc.) that display
pre-formatted messages to the actor, target, and room.

The original C version loads social messages from lib/misc/socials.
Since Dalila's social file may not be present, this module provides
a built-in table of common Italian socials and a loader for the
CircleMUD format file.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from dalila.constants import Position
from dalila.engine.handler import get_char_room_vis

if TYPE_CHECKING:
    from dalila.engine.game_loop import GameWorld
    from dalila.models.character import CharData
    from dalila.net.descriptor import Descriptor

log = logging.getLogger(__name__)


@dataclass
class SocialMessage:
    """A social action message set.

    Ported from struct social_messg in act.social.c.
    """
    command: str = ""
    hide: bool = False
    min_victim_position: int = Position.POS_DEAD

    # No argument supplied
    char_no_arg: str = ""
    others_no_arg: str = ""

    # Argument found, victim found
    char_found: str = ""       # If empty, no victim messages
    others_found: str = ""
    vict_found: str = ""

    # Argument supplied but no victim
    not_found: str = ""

    # Victim is self
    char_auto: str = ""
    others_auto: str = ""


# Module-level social registry
_SOCIALS: dict[str, SocialMessage] = {}


def _replace_name(text: str, actor_name: str, vict_name: str = "") -> str:
    """Replace CircleMUD act-style $n/$N with actual names."""
    result = text
    result = result.replace("$n", actor_name)
    result = result.replace("$N", vict_name)
    return result


# ---------------------------------------------------------------------------
# Built-in socials (Italian Dalila socials)
# ---------------------------------------------------------------------------

_BUILTIN_SOCIALS: list[SocialMessage] = [
    SocialMessage(
        command="abbraccia",
        char_no_arg="Chi vuoi abbracciare?",
        others_no_arg="",
        char_found="Abbracci $N.",
        others_found="$n abbraccia $N.",
        vict_found="$n ti abbraccia.",
        not_found="Non c'e' nessuno con quel nome!",
        char_auto="Ti abbracci... ti senti meglio?",
        others_auto="$n si abbraccia.",
    ),
    SocialMessage(
        command="accarezza",
        char_no_arg="Chi vuoi accarezzare?",
        others_no_arg="",
        char_found="Accarezzi $N.",
        others_found="$n accarezza $N.",
        vict_found="$n ti accarezza.",
        not_found="Non c'e' nessuno con quel nome!",
        char_auto="Ti accarezzi.",
        others_auto="$n si accarezza.",
    ),
    SocialMessage(
        command="applaudire",
        char_no_arg="Applaudi.",
        others_no_arg="$n applaude.",
        char_found="Applaudi $N.",
        others_found="$n applaude $N.",
        vict_found="$n ti applaude.",
        not_found="Non c'e' nessuno con quel nome!",
        char_auto="Ti applaudi da solo.",
        others_auto="$n si applaude da solo.",
    ),
    SocialMessage(
        command="arrossisci",
        char_no_arg="Arrossisci.",
        others_no_arg="$n arrossisce.",
    ),
    SocialMessage(
        command="bacia",
        char_no_arg="Chi vuoi baciare?",
        others_no_arg="",
        char_found="Baci $N.",
        others_found="$n bacia $N.",
        vict_found="$n ti bacia.",
        not_found="Non c'e' nessuno con quel nome!",
        char_auto="Ti baci la mano.",
        others_auto="$n si bacia la mano.",
    ),
    SocialMessage(
        command="ciao",
        char_no_arg="Saluti tutti.",
        others_no_arg="$n saluta tutti.",
        char_found="Saluti $N.",
        others_found="$n saluta $N.",
        vict_found="$n ti saluta.",
        not_found="Non c'e' nessuno con quel nome!",
        char_auto="Ti saluti da solo.",
        others_auto="$n si saluta da solo.",
    ),
    SocialMessage(
        command="conforta",
        char_no_arg="Chi vuoi confortare?",
        others_no_arg="",
        char_found="Conforti $N.",
        others_found="$n conforta $N.",
        vict_found="$n ti conforta.",
        not_found="Non c'e' nessuno con quel nome!",
        char_auto="Ti conforti da solo.",
        others_auto="$n si conforta da solo.",
    ),
    SocialMessage(
        command="danza",
        char_no_arg="Danzi allegramente.",
        others_no_arg="$n danza allegramente.",
        char_found="Danzi con $N.",
        others_found="$n danza con $N.",
        vict_found="$n ti invita a danzare.",
        not_found="Non c'e' nessuno con quel nome!",
        char_auto="Danzi da solo.",
        others_auto="$n danza da solo.",
    ),
    SocialMessage(
        command="ghigna",
        char_no_arg="Ghigni malvagiamente.",
        others_no_arg="$n ghigna malvagiamente.",
        char_found="Ghigni a $N.",
        others_found="$n ghigna a $N.",
        vict_found="$n ti ghigna malvagiamente.",
        not_found="Non c'e' nessuno con quel nome!",
        char_auto="Ghigni a te stesso.",
        others_auto="$n ghigna a se stesso.",
    ),
    SocialMessage(
        command="inchino",
        char_no_arg="Ti inchini.",
        others_no_arg="$n si inchina.",
        char_found="Ti inchini davanti a $N.",
        others_found="$n si inchina davanti a $N.",
        vict_found="$n si inchina davanti a te.",
        not_found="Non c'e' nessuno con quel nome!",
        char_auto="Ti inchini a te stesso.",
        others_auto="$n si inchina a se stesso. Strano.",
    ),
    SocialMessage(
        command="piange",
        char_no_arg="Piangi.",
        others_no_arg="$n piange.",
        char_found="Piangi sulla spalla di $N.",
        others_found="$n piange sulla spalla di $N.",
        vict_found="$n piange sulla tua spalla.",
        not_found="Non c'e' nessuno con quel nome!",
        char_auto="Piangi.",
        others_auto="$n piange.",
    ),
    SocialMessage(
        command="ride",
        char_no_arg="Ridi.",
        others_no_arg="$n ride.",
        char_found="Ridi di $N.",
        others_found="$n ride di $N.",
        vict_found="$n ride di te.",
        not_found="Non c'e' nessuno con quel nome!",
        char_auto="Ridi di te stesso.",
        others_auto="$n ride di se stesso.",
    ),
    SocialMessage(
        command="ringrazia",
        char_no_arg="Ringrazi tutti.",
        others_no_arg="$n ringrazia tutti.",
        char_found="Ringrazi $N.",
        others_found="$n ringrazia $N.",
        vict_found="$n ti ringrazia.",
        not_found="Non c'e' nessuno con quel nome!",
        char_auto="Ringrazi te stesso.",
        others_auto="$n ringrazia se stesso.",
    ),
    SocialMessage(
        command="saluta",
        char_no_arg="Saluti.",
        others_no_arg="$n saluta.",
        char_found="Saluti $N.",
        others_found="$n saluta $N.",
        vict_found="$n ti saluta.",
        not_found="Non c'e' nessuno con quel nome!",
        char_auto="Saluti te stesso.",
        others_auto="$n saluta se stesso.",
    ),
    SocialMessage(
        command="schiaffeggia",
        char_no_arg="Chi vuoi schiaffeggiare?",
        others_no_arg="",
        char_found="Schiaffeggi $N!",
        others_found="$n schiaffeggia $N!",
        vict_found="$n ti schiaffeggia!",
        not_found="Non c'e' nessuno con quel nome!",
        char_auto="Ti schiaffeggi.",
        others_auto="$n si schiaffeggia.",
    ),
    SocialMessage(
        command="sorridi",
        char_no_arg="Sorridi.",
        others_no_arg="$n sorride.",
        char_found="Sorridi a $N.",
        others_found="$n sorride a $N.",
        vict_found="$n ti sorride.",
        not_found="Non c'e' nessuno con quel nome!",
        char_auto="Sorridi a te stesso.",
        others_auto="$n sorride a se stesso.",
    ),
    SocialMessage(
        command="strizza",
        char_no_arg="Strizzi l'occhio.",
        others_no_arg="$n strizza l'occhio.",
        char_found="Strizzi l'occhio a $N.",
        others_found="$n strizza l'occhio a $N.",
        vict_found="$n ti strizza l'occhio.",
        not_found="Non c'e' nessuno con quel nome!",
        char_auto="Strizzi l'occhio a te stesso.",
        others_auto="$n strizza l'occhio a se stesso.",
    ),
    # English aliases for common socials
    SocialMessage(
        command="hug",
        char_no_arg="Chi vuoi abbracciare?",
        others_no_arg="",
        char_found="Abbracci $N.",
        others_found="$n abbraccia $N.",
        vict_found="$n ti abbraccia.",
        not_found="Non c'e' nessuno con quel nome!",
        char_auto="Ti abbracci.",
        others_auto="$n si abbraccia.",
    ),
    SocialMessage(
        command="wave",
        char_no_arg="Saluti con la mano.",
        others_no_arg="$n saluta con la mano.",
        char_found="Saluti $N con la mano.",
        others_found="$n saluta $N con la mano.",
        vict_found="$n ti saluta con la mano.",
        not_found="Non c'e' nessuno con quel nome!",
        char_auto="Saluti te stesso con la mano.",
        others_auto="$n saluta se stesso con la mano.",
    ),
    SocialMessage(
        command="smile",
        char_no_arg="Sorridi.",
        others_no_arg="$n sorride.",
        char_found="Sorridi a $N.",
        others_found="$n sorride a $N.",
        vict_found="$n ti sorride.",
        not_found="Non c'e' nessuno con quel nome!",
        char_auto="Sorridi a te stesso.",
        others_auto="$n sorride a se stesso.",
    ),
    SocialMessage(
        command="laugh",
        char_no_arg="Ridi.",
        others_no_arg="$n ride.",
        char_found="Ridi di $N.",
        others_found="$n ride di $N.",
        vict_found="$n ride di te.",
        not_found="Non c'e' nessuno con quel nome!",
        char_auto="Ridi di te stesso.",
        others_auto="$n ride di se stesso.",
    ),
    SocialMessage(
        command="bow",
        char_no_arg="Ti inchini.",
        others_no_arg="$n si inchina.",
        char_found="Ti inchini davanti a $N.",
        others_found="$n si inchina davanti a $N.",
        vict_found="$n si inchina davanti a te.",
        not_found="Non c'e' nessuno con quel nome!",
        char_auto="Ti inchini a te stesso.",
        others_auto="$n si inchina a se stesso.",
    ),
    SocialMessage(
        command="nod",
        char_no_arg="Annuisci.",
        others_no_arg="$n annuisce.",
        char_found="Annuisci a $N.",
        others_found="$n annuisce a $N.",
        vict_found="$n ti annuisce.",
        not_found="Non c'e' nessuno con quel nome!",
        char_auto="Annuisci a te stesso.",
        others_auto="$n annuisce a se stesso.",
    ),
    SocialMessage(
        command="annuisci",
        char_no_arg="Annuisci.",
        others_no_arg="$n annuisce.",
        char_found="Annuisci a $N.",
        others_found="$n annuisce a $N.",
        vict_found="$n ti annuisce.",
        not_found="Non c'e' nessuno con quel nome!",
        char_auto="Annuisci a te stesso.",
        others_auto="$n annuisce a se stesso.",
    ),
    SocialMessage(
        command="pensa",
        char_no_arg="Pensi intensamente.",
        others_no_arg="$n sembra pensare intensamente.",
    ),
    SocialMessage(
        command="think",
        char_no_arg="Pensi intensamente.",
        others_no_arg="$n sembra pensare intensamente.",
    ),
    SocialMessage(
        command="sigh",
        char_no_arg="Sospiri.",
        others_no_arg="$n sospira.",
    ),
    SocialMessage(
        command="sospira",
        char_no_arg="Sospiri.",
        others_no_arg="$n sospira.",
    ),
    SocialMessage(
        command="sbadiglia",
        char_no_arg="Sbadigli.",
        others_no_arg="$n sbadiglia.",
    ),
    SocialMessage(
        command="yawn",
        char_no_arg="Sbadigli.",
        others_no_arg="$n sbadiglia.",
    ),
]


def _init_builtins() -> None:
    """Register all built-in socials."""
    for soc in _BUILTIN_SOCIALS:
        _SOCIALS[soc.command.lower()] = soc


# Initialize on module load
_init_builtins()


# ---------------------------------------------------------------------------
# Social loader (CircleMUD format)
# ---------------------------------------------------------------------------

def boot_social_messages(lib_path: Path) -> None:
    """Load social messages from lib/misc/socials if present.

    Ported from boot_social_messages() in act.social.c.
    Falls back to built-in socials if file doesn't exist.
    """
    socials_path = lib_path / "misc" / "socials"
    if not socials_path.exists():
        log.info("  Social file not found; using %d built-in socials",
                 len(_SOCIALS))
        return

    try:
        _load_socials_file(socials_path)
    except Exception as e:
        log.warning("Error loading socials file: %s; using built-ins", e)


def _load_socials_file(path: Path) -> None:
    """Parse a CircleMUD-format socials file."""
    count = 0
    with open(path, encoding="latin-1") as f:
        while True:
            line = f.readline()
            if not line:
                break
            cmd = line.strip()
            if cmd == "$":
                break
            if not cmd:
                continue

            # Read hide and min_pos
            meta_line = f.readline().strip()
            if not meta_line:
                break
            parts = meta_line.split()
            hide = int(parts[0]) if len(parts) > 0 else 0
            min_pos = int(parts[1]) if len(parts) > 1 else 0

            soc = SocialMessage(
                command=cmd.lower(),
                hide=bool(hide),
                min_victim_position=min_pos,
            )

            # Read char_no_arg
            soc.char_no_arg = _read_social_line(f)
            soc.others_no_arg = _read_social_line(f)

            char_found = _read_social_line(f)
            if char_found is None:
                # '#' means no victim processing
                _SOCIALS[soc.command] = soc
                count += 1
                continue

            soc.char_found = char_found or ""
            soc.others_found = _read_social_line(f) or ""
            soc.vict_found = _read_social_line(f) or ""
            soc.not_found = _read_social_line(f) or ""
            soc.char_auto = _read_social_line(f) or ""
            soc.others_auto = _read_social_line(f) or ""

            _SOCIALS[soc.command] = soc
            count += 1

    log.info("  %d socials loaded from file", count)


def _read_social_line(f) -> str | None:
    """Read one line from a socials file. '#' means None."""
    line = f.readline()
    if not line:
        return None
    line = line.rstrip("\n\r")
    if line.startswith("#"):
        return None
    return line


# ---------------------------------------------------------------------------
# Social dispatch
# ---------------------------------------------------------------------------

def find_social(cmd_word: str) -> SocialMessage | None:
    """Look up a social command by prefix match."""
    cmd_lower = cmd_word.lower()
    # Exact match first
    if cmd_lower in _SOCIALS:
        return _SOCIALS[cmd_lower]
    # Prefix match
    for key, soc in _SOCIALS.items():
        if key.startswith(cmd_lower):
            return soc
    return None


def do_social(
    ch: CharData, argument: str, desc: Descriptor,
    world: GameWorld, social: SocialMessage,
) -> None:
    """Execute a social command.

    Ported from ACMD(do_action) in act.social.c.
    """
    import asyncio

    arg = argument.strip().split(None, 1)
    target_name = arg[0] if arg else ""

    room = None
    if ch.in_room in world.rooms:
        room = world.rooms[ch.in_room]

    if not target_name or not social.char_found:
        # No argument: show no-arg messages
        if social.char_no_arg:
            text = _replace_name(social.char_no_arg, ch.player.name)
            asyncio.ensure_future(desc.send(f"{text}\r\n"))
        if social.others_no_arg and room:
            text = _replace_name(social.others_no_arg, ch.player.name)
            for other in room._characters:
                if other is not ch and other.desc:
                    asyncio.ensure_future(
                        other.desc.send(f"\r\n{text}\r\n")
                    )
        return

    # Try to find the target
    vict = get_char_room_vis(ch, target_name, world)

    if vict is None:
        if social.not_found:
            text = _replace_name(social.not_found, ch.player.name)
            asyncio.ensure_future(desc.send(f"{text}\r\n"))
        return

    if vict is ch:
        # Self-target
        if social.char_auto:
            text = _replace_name(social.char_auto, ch.player.name)
            asyncio.ensure_future(desc.send(f"{text}\r\n"))
        if social.others_auto and room:
            text = _replace_name(social.others_auto, ch.player.name)
            for other in room._characters:
                if other is not ch and other.desc:
                    asyncio.ensure_future(
                        other.desc.send(f"\r\n{text}\r\n")
                    )
        return

    # Target found
    if social.char_found:
        text = _replace_name(social.char_found, ch.player.name, vict.player.name)
        asyncio.ensure_future(desc.send(f"{text}\r\n"))
    if social.vict_found and vict.desc:
        text = _replace_name(social.vict_found, ch.player.name, vict.player.name)
        asyncio.ensure_future(vict.desc.send(f"\r\n{text}\r\n"))
    if social.others_found and room:
        text = _replace_name(
            social.others_found, ch.player.name, vict.player.name,
        )
        for other in room._characters:
            if other is not ch and other is not vict and other.desc:
                asyncio.ensure_future(
                    other.desc.send(f"\r\n{text}\r\n")
                )


def get_all_social_names() -> list[str]:
    """Return all registered social command names."""
    return sorted(_SOCIALS.keys())
