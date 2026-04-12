"""Descriptor class -- represents a single client connection.

Ported from struct descriptor_data in structs.h and comm.c.
Replaces the C linked list of descriptors with Python objects
managed by the GameServer.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from dalila.constants import ConnState, MAX_INPUT_LENGTH
from dalila.net.telnet import ECHO_OFF, ECHO_ON, GA_SEQUENCE, strip_telnet

if TYPE_CHECKING:
    from dalila.models.character import CharData

log = logging.getLogger(__name__)


@dataclass
class Descriptor:
    """A single network connection to the MUD.

    Ported from struct descriptor_data in structs.h.
    Each connected socket gets one Descriptor that tracks its state,
    buffers, and associated character.
    """

    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    desc_num: int                       # Unique descriptor number

    # Connection state (nanny state machine)
    state: ConnState = ConnState.CON_GET_NAME

    # Associated character (None until login)
    character: CharData | None = None

    # Host information
    host: str = ""

    # Input/output buffers
    input_queue: list[str] = field(default_factory=list)
    output_buffer: str = ""

    # Timing
    idle_tics: int = 0
    login_time: float = field(default_factory=time.time)
    bad_pws: int = 0

    # Wait state (command throttle, in pulses)
    wait: int = 0

    # Prompt control
    prompt_mode: int = 1

    # Is connection closing?
    closing: bool = False

    # Temp storage for new character name during creation
    _pending_name: str = ""

    def __post_init__(self) -> None:
        peername = self.writer.get_extra_info("peername")
        if peername:
            self.host = peername[0]

    async def send(self, text: str) -> None:
        """Queue text to be sent to the client.

        Mirrors SEND_TO_Q() from comm.c.
        """
        if self.closing:
            return
        try:
            self.writer.write(text.encode("latin-1", errors="replace"))
            await self.writer.drain()
        except (ConnectionResetError, BrokenPipeError, OSError):
            self.closing = True

    def send_raw(self, data: bytes) -> None:
        """Send raw bytes (for telnet protocol sequences).

        Non-async fire-and-forget for protocol bytes.
        """
        if self.closing:
            return
        try:
            self.writer.write(data)
        except (ConnectionResetError, BrokenPipeError, OSError):
            self.closing = True

    async def echo_off(self) -> None:
        """Tell client to stop echoing (for password entry).

        Mirrors echo_off() from comm.c.
        """
        self.send_raw(ECHO_OFF)

    async def echo_on(self) -> None:
        """Tell client to resume echoing.

        Mirrors echo_on() from comm.c.
        """
        self.send_raw(ECHO_ON)

    async def close(self) -> None:
        """Close this connection.

        Mirrors close_socket() from comm.c.
        """
        self.closing = True
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except (ConnectionResetError, BrokenPipeError, OSError):
            pass

    async def read_line(self) -> str | None:
        """Read a single line of input from the client.

        Handles telnet IAC stripping and line buffering.
        Returns None on disconnect.
        """
        try:
            raw = await asyncio.wait_for(
                self.reader.readline(),
                timeout=300.0,  # 5-minute idle timeout
            )
        except asyncio.TimeoutError:
            return None
        except (ConnectionResetError, BrokenPipeError, OSError):
            return None

        if not raw:
            return None  # EOF / disconnect

        # Strip telnet IAC sequences
        cleaned = strip_telnet(raw)

        # Decode, strip CR/LF, enforce max length
        try:
            line = cleaned.decode("latin-1", errors="replace")
        except UnicodeDecodeError:
            line = cleaned.decode("ascii", errors="replace")

        line = line.rstrip("\r\n")

        if len(line) > MAX_INPUT_LENGTH:
            line = line[:MAX_INPUT_LENGTH]

        return line
