"""Telnet protocol helpers.

Handles IAC sequences and provides echo on/off for password entry.
Ported from comm.c telnet handling and arpa/telnet.h defines.
"""

from __future__ import annotations

# Telnet protocol bytes
IAC: int = 255   # Interpret As Command
DONT: int = 254
DO: int = 253
WONT: int = 252
WILL: int = 251
SB: int = 250    # Sub-negotiation Begin
SE: int = 240    # Sub-negotiation End
GA: int = 249    # Go Ahead
NOP: int = 241

# Telnet option codes
TELOPT_ECHO: int = 1
TELOPT_SGA: int = 3     # Suppress Go Ahead
TELOPT_TTYPE: int = 24  # Terminal type
TELOPT_NAWS: int = 31   # Window size

# Pre-built sequences
ECHO_OFF: bytes = bytes([IAC, WILL, TELOPT_ECHO])
ECHO_ON: bytes = bytes([IAC, WONT, TELOPT_ECHO])
GA_SEQUENCE: bytes = bytes([IAC, GA])


def strip_telnet(data: bytes) -> bytes:
    """Strip IAC sequences from raw input data.

    Mirrors the IAC-stripping logic in process_input() from comm.c.
    Returns the cleaned data with all telnet commands removed.
    """
    result = bytearray()
    i = 0
    length = len(data)

    while i < length:
        if data[i] == IAC:
            if i + 1 >= length:
                break  # Incomplete IAC, discard
            cmd = data[i + 1]
            if cmd == IAC:
                # Escaped IAC -> literal 0xFF
                result.append(IAC)
                i += 2
            elif cmd in (DO, DONT, WILL, WONT):
                # 3-byte command: IAC + cmd + option
                i += 3 if i + 2 < length else length
            elif cmd == SB:
                # Sub-negotiation: skip until IAC SE
                i += 2
                while i < length:
                    if data[i] == IAC and i + 1 < length and data[i + 1] == SE:
                        i += 2
                        break
                    i += 1
            else:
                # 2-byte command (NOP, GA, etc.)
                i += 2
        else:
            result.append(data[i])
            i += 1

    return bytes(result)
