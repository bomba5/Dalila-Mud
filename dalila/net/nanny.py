"""Login state machine -- the nanny() function.

Ported from nanny() in interpreter.c (~500 lines).
Handles: name entry, password, new character creation (sex, class),
MOTD display, menu selection, password change.

Phase 1 simplifications:
- No binary playerfile persistence (in-memory only)
- Password hashing uses hashlib.sha256 (not C crypt())
- No mestieri/citta/iniziazione sub-menus (simplified new char flow)
- No ban checking, no multiplayer IP detection
"""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING

from dalila.constants import (
    ConnState,
    LVL_IMMORT,
    MAX_NAME_LENGTH,
    MAX_PWD_LENGTH,
    NOWHERE,
    CharClass,
    Position,
    Sex,
)
from dalila.models.character import (
    CharAbilityData,
    CharData,
    CharPlayerData,
    CharPointData,
    PlayerSpecialSaved,
)

if TYPE_CHECKING:
    from dalila.engine.game_loop import GameWorld
    from dalila.net.descriptor import Descriptor

log = logging.getLogger(__name__)


def _hash_password(password: str) -> str:
    """Hash a password using SHA-256.

    The C version uses crypt(3). We use SHA-256 from hashlib since
    bcrypt is an external dependency and CLAUDE.md says stdlib only.
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _check_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    return _hash_password(password) == hashed


def _valid_name(name: str) -> bool:
    """Check if a player name is valid.

    Mirrors Valid_Name() and _parse_name() from interpreter.c.
    """
    if len(name) < 2 or len(name) > MAX_NAME_LENGTH:
        return False
    if not name.isalpha():
        return False
    # Reserved words
    reserved = {
        "me", "self", "all", "room", "someone", "something",
        "il", "lo", "la", "un", "una",
    }
    if name.lower() in reserved:
        return False
    return True


def _capitalize_name(name: str) -> str:
    """Capitalize first letter only, like CAP() in the C code."""
    if not name:
        return name
    return name[0].upper() + name[1:].lower()


def _init_new_character(ch: CharData) -> None:
    """Initialize a new character with starting values.

    Mirrors init_char() + do_start() from interpreter.c/class.c.
    Simplified for Phase 1.
    """
    ch.player.level = 1
    ch.player.class_ = CharClass.CLASS_WARRIOR  # Default to Genidian

    # Starting abilities
    ch.real_abils = CharAbilityData(
        str=13, intel=13, wis=13, dex=13, con=13, cha=13,
    )
    ch.aff_abils = CharAbilityData(
        str=13, intel=13, wis=13, dex=13, con=13, cha=13,
    )

    # Starting points
    ch.points.max_hit = 20
    ch.points.hit = 20
    ch.points.max_mana = 100
    ch.points.mana = 100
    ch.points.max_move = 82
    ch.points.move = 82
    ch.points.armor = 100  # AC 10

    # Player specials
    if ch.player_specials is None:
        ch.player_specials = PlayerSpecialSaved()
    ch.player_specials.conditions = [0, 24, 24]  # sober, full, hydrated


def _enter_game(ch: CharData, desc: Descriptor, world: GameWorld) -> None:
    """Place the character into the game world.

    Mirrors the case '1' in CON_MENU from interpreter.c.
    """
    import asyncio

    # Find start room
    start = world.mortal_start_room
    if ch.player_specials and ch.player_specials.load_room != NOWHERE:
        if ch.player_specials.load_room in world.rooms:
            start = ch.player_specials.load_room

    ch.in_room = start

    # Add to world
    if ch not in world.players:
        world.players.append(ch)

    # Add to room
    if start in world.rooms:
        room = world.rooms[start]
        if ch not in room._characters:
            room._characters.append(ch)

    # Link descriptor and character
    ch.desc = desc

    log.info("Player %s entered game in room %d", ch.player.name, start)


async def nanny(desc: Descriptor, arg: str, world: GameWorld) -> None:
    """Login state machine.

    Ported from nanny() in interpreter.c.
    Routes input based on descriptor connection state.
    """
    arg = arg.strip()

    match desc.state:

        case ConnState.CON_GET_NAME:
            await _handle_get_name(desc, arg, world)

        case ConnState.CON_NAME_CNFRM:
            await _handle_name_confirm(desc, arg, world)

        case ConnState.CON_PASSWORD:
            await _handle_password(desc, arg, world)

        case ConnState.CON_NEWPASSWD:
            await _handle_new_password(desc, arg, world)

        case ConnState.CON_CNFPASSWD:
            await _handle_confirm_password(desc, arg, world)

        case ConnState.CON_QSEX:
            await _handle_sex(desc, arg, world)

        case ConnState.CON_QCLASS:
            await _handle_class(desc, arg, world)

        case ConnState.CON_RMOTD:
            await _handle_rmotd(desc, arg, world)

        case ConnState.CON_MENU:
            await _handle_menu(desc, arg, world)

        case ConnState.CON_CHPWD_GETOLD:
            await _handle_chpwd_old(desc, arg, world)

        case ConnState.CON_CHPWD_GETNEW:
            await _handle_chpwd_new(desc, arg, world)

        case ConnState.CON_CHPWD_VRFY:
            await _handle_chpwd_verify(desc, arg, world)

        case ConnState.CON_CLOSE:
            await desc.close()

        case _:
            log.warning(
                "Nanny: unknown state %s for desc #%d",
                desc.state, desc.desc_num,
            )
            await desc.close()


async def _handle_get_name(
    desc: Descriptor, arg: str, world: GameWorld,
) -> None:
    """CON_GET_NAME: player enters their name.

    Mirrors the CON_GET_NAME case in nanny() from interpreter.c.
    """
    if not arg:
        await desc.close()
        return

    name = _capitalize_name(arg)

    if not _valid_name(name):
        await desc.send("Nome invalido, prova un altro.\r\nNome: ")
        return

    # Check if player exists in memory
    if name.lower() in {k.lower() for k in world.known_players}:
        # Existing player
        # Find the actual key (case-insensitive lookup)
        actual_name = next(
            k for k in world.known_players if k.lower() == name.lower()
        )
        existing = world.known_players[actual_name]

        # Create a character reference on the descriptor
        desc.character = CharData()
        desc.character.player = CharPlayerData(
            name=existing.player.name,
            passwd=existing.player.passwd,
            sex=existing.player.sex,
            class_=existing.player.class_,
            level=existing.player.level,
        )
        desc.character.points = CharPointData(
            hit=existing.points.hit,
            max_hit=existing.points.max_hit,
            mana=existing.points.mana,
            max_mana=existing.points.max_mana,
            move=existing.points.move,
            max_move=existing.points.max_move,
            armor=existing.points.armor,
            exp=existing.points.exp,
        )
        desc.character.real_abils = CharAbilityData(
            str=existing.real_abils.str,
            intel=existing.real_abils.intel,
            wis=existing.real_abils.wis,
            dex=existing.real_abils.dex,
            con=existing.real_abils.con,
            cha=existing.real_abils.cha,
        )
        desc.character.aff_abils = CharAbilityData(
            str=existing.aff_abils.str,
            intel=existing.aff_abils.intel,
            wis=existing.aff_abils.wis,
            dex=existing.aff_abils.dex,
            con=existing.aff_abils.con,
            cha=existing.aff_abils.cha,
        )
        desc.character.player_specials = existing.player_specials
        desc.character.desc = desc

        await desc.send("Password: ")
        await desc.echo_off()
        desc.idle_tics = 0
        desc.state = ConnState.CON_PASSWORD
    else:
        # New player
        desc.character = CharData()
        desc.character.player.name = name
        desc.character.desc = desc
        desc._pending_name = name

        await desc.send(f"Vuoi essere veramente, {name} (Y/N)? ")
        desc.state = ConnState.CON_NAME_CNFRM


async def _handle_name_confirm(
    desc: Descriptor, arg: str, world: GameWorld,
) -> None:
    """CON_NAME_CNFRM: confirm new character name."""
    if not arg:
        await desc.send("Prego rispondere Yes o No: ")
        return

    first = arg[0].upper()
    if first == "Y":
        await desc.send("Nuovo personaggio.\r\n")
        await desc.send(
            f"Introduci la password per {desc.character.player.name}: "
        )
        await desc.echo_off()
        desc.state = ConnState.CON_NEWPASSWD
    elif first == "N":
        await desc.send("Ok, quale' allora? ")
        desc.character.player.name = ""
        desc.state = ConnState.CON_GET_NAME
    else:
        await desc.send("Prego rispondere Yes o No: ")


async def _handle_password(
    desc: Descriptor, arg: str, world: GameWorld,
) -> None:
    """CON_PASSWORD: verify password for existing player."""
    await desc.echo_on()

    if not arg:
        await desc.close()
        return

    if not _check_password(arg, desc.character.player.passwd):
        desc.bad_pws += 1
        if desc.bad_pws >= 3:
            await desc.send("Password sbagliata... disconessione.\r\n")
            desc.state = ConnState.CON_CLOSE
        else:
            await desc.send("Password sbagliata.\r\nPassword: ")
            await desc.echo_off()
        return

    # Password correct
    log.info(
        "%s [%s] has connected.",
        desc.character.player.name, desc.host,
    )

    # Show MOTD
    if desc.character.player.level >= LVL_IMMORT:
        await desc.send(world.imotd_text)
    else:
        await desc.send(world.motd_text)

    await desc.send("\r\n\n*** PRESS RETURN: ")
    desc.state = ConnState.CON_RMOTD


async def _handle_new_password(
    desc: Descriptor, arg: str, world: GameWorld,
) -> None:
    """CON_NEWPASSWD: set password for new character."""
    if (
        not arg
        or len(arg) > MAX_PWD_LENGTH
        or len(arg) < 3
        or arg.lower() == desc.character.player.name.lower()
    ):
        await desc.send("\r\nPassword non ammessa.\r\nPassword: ")
        return

    desc.character.player.passwd = _hash_password(arg)
    await desc.send("\r\nRidigita la password: ")
    desc.state = ConnState.CON_CNFPASSWD


async def _handle_confirm_password(
    desc: Descriptor, arg: str, world: GameWorld,
) -> None:
    """CON_CNFPASSWD: confirm new password."""
    if not _check_password(arg, desc.character.player.passwd):
        await desc.send(
            "\r\n Le Passwords non coincidono... ricomincia.\r\n"
            "Password: "
        )
        desc.state = ConnState.CON_NEWPASSWD
        return

    await desc.echo_on()
    await desc.send("Quale' il tuo sesso (M/F)? ")
    desc.state = ConnState.CON_QSEX


async def _handle_sex(
    desc: Descriptor, arg: str, world: GameWorld,
) -> None:
    """CON_QSEX: choose character sex."""
    if not arg:
        await desc.send("That is not a sex..\r\nWhat IS your sex? ")
        return

    first = arg[0].upper()
    if first == "M":
        desc.character.player.sex = Sex.SEX_MALE
    elif first == "F":
        desc.character.player.sex = Sex.SEX_FEMALE
    else:
        await desc.send("That is not a sex..\r\nWhat IS your sex? ")
        return

    # Simplified class selection for Phase 1
    class_menu = (
        "\r\n"
        "Scegli la tua classe:\r\n"
        "  [P]andion  (Mago)          [C]yrinic  (Chierico)\r\n"
        "  [A]lcione  (Ladro)         [G]enidian (Guerriero)\r\n"
        "  [L]Peloi                   [D]aresiano\r\n"
        "\r\nClasse: "
    )
    await desc.send(class_menu)
    desc.state = ConnState.CON_QCLASS


async def _handle_class(
    desc: Descriptor, arg: str, world: GameWorld,
) -> None:
    """CON_QCLASS: choose character class.

    Simplified from the C version which has roll stats and mestieri.
    """
    if not arg:
        await desc.send("Scelta non valida. Classe: ")
        return

    first = arg[0].upper()
    class_map = {
        "P": CharClass.CLASS_MAGIC_USER,
        "C": CharClass.CLASS_CLERIC,
        "A": CharClass.CLASS_THIEF,
        "G": CharClass.CLASS_WARRIOR,
        "L": CharClass.CLASS_PELOI,
        "D": CharClass.CLASS_DARESIANO,
    }

    chosen = class_map.get(first)
    if chosen is None:
        await desc.send("Scelta non valida. Classe: ")
        return

    desc.character.player.class_ = chosen

    # Initialize the new character
    _init_new_character(desc.character)

    # Store in known_players
    world.known_players[desc.character.player.name] = desc.character

    log.info(
        "%s [%s] new player.",
        desc.character.player.name, desc.host,
    )

    # Show MOTD
    await desc.send(world.motd_text)
    await desc.send("\r\n\n*** PRESS RETURN: ")
    desc.state = ConnState.CON_RMOTD


async def _handle_rmotd(
    desc: Descriptor, arg: str, world: GameWorld,
) -> None:
    """CON_RMOTD: press return after MOTD."""
    await desc.send(world.menu_text)
    desc.state = ConnState.CON_MENU


async def _handle_menu(
    desc: Descriptor, arg: str, world: GameWorld,
) -> None:
    """CON_MENU: main menu selection.

    Mirrors the CON_MENU case in nanny() from interpreter.c.
    Menu options:
        0 - Exit
        1 - Enter game
        2 - Description (simplified)
        3 - Read background
        4 - Change password
        5 - Delete character (simplified)
    """
    if not arg:
        await desc.send("\r\nThat's not a menu choice!\r\n")
        await desc.send(world.menu_text)
        return

    match arg[0]:
        case "0":
            await desc.send("\r\nArrivederci!\r\n")
            desc.state = ConnState.CON_CLOSE
            return

        case "1":
            # Enter the game
            _enter_game(desc.character, desc, world)

            await desc.send(
                "\r\nBenvenuto nel Fantastico mondo di Dalila!\r\n\r\n"
            )
            desc.state = ConnState.CON_PLAYING

            # Show the room
            from dalila.commands.interpreter import do_look
            do_look(desc.character, "", desc, world)

        case "2":
            await desc.send(
                "\r\nDescrizione del personaggio non ancora "
                "disponibile nel port Python.\r\n"
            )
            await desc.send(world.menu_text)

        case "3":
            await desc.send(world.background_text)
            await desc.send("\r\n\n*** PRESS RETURN: ")
            desc.state = ConnState.CON_RMOTD

        case "4":
            await desc.send("\r\nEnter your old password: ")
            await desc.echo_off()
            desc.state = ConnState.CON_CHPWD_GETOLD

        case "5":
            await desc.send(
                "\r\nCancellazione non ancora disponibile "
                "nel port Python.\r\n"
            )
            await desc.send(world.menu_text)

        case _:
            await desc.send("\r\nThat's not a menu choice!\r\n")
            await desc.send(world.menu_text)


async def _handle_chpwd_old(
    desc: Descriptor, arg: str, world: GameWorld,
) -> None:
    """CON_CHPWD_GETOLD: verify old password before change."""
    await desc.echo_on()

    if not _check_password(arg, desc.character.player.passwd):
        await desc.send("\r\nIncorrect password.\r\n")
        await desc.send(world.menu_text)
        desc.state = ConnState.CON_MENU
    else:
        await desc.send("\r\nEnter a new password: ")
        await desc.echo_off()
        desc.state = ConnState.CON_CHPWD_GETNEW


async def _handle_chpwd_new(
    desc: Descriptor, arg: str, world: GameWorld,
) -> None:
    """CON_CHPWD_GETNEW: enter new password."""
    if (
        not arg
        or len(arg) > MAX_PWD_LENGTH
        or len(arg) < 3
        or arg.lower() == desc.character.player.name.lower()
    ):
        await desc.send("\r\nPassword non ammessa.\r\nPassword: ")
        return

    desc.character.player.passwd = _hash_password(arg)
    await desc.send("\r\nRidigita la password: ")
    desc.state = ConnState.CON_CHPWD_VRFY


async def _handle_chpwd_verify(
    desc: Descriptor, arg: str, world: GameWorld,
) -> None:
    """CON_CHPWD_VRFY: verify new password."""
    if not _check_password(arg, desc.character.player.passwd):
        await desc.send(
            "\r\n Le Passwords non coincidono... ricomincia.\r\n"
            "Password: "
        )
        await desc.echo_off()
        desc.state = ConnState.CON_CHPWD_GETNEW
        return

    await desc.echo_on()

    # Update the stored player
    name = desc.character.player.name
    if name in world.known_players:
        world.known_players[name].player.passwd = desc.character.player.passwd

    await desc.send("\r\nFatto.\r\n")
    await desc.send(world.menu_text)
    desc.state = ConnState.CON_MENU
