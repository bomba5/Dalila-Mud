"""Network server -- asyncio replacement for the C select() loop.

Ported from init_game(), game_loop(), new_descriptor(), process_input(),
process_output(), close_socket() in comm.c.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from dalila.constants import ConnState
from dalila.net.descriptor import Descriptor

if TYPE_CHECKING:
    from dalila.engine.game_loop import GameWorld

log = logging.getLogger(__name__)


class GameServer:
    """Asyncio TCP server for the MUD.

    Replaces the C select()-based game_loop() from comm.c.
    Manages all descriptors (connections) and coordinates with the
    GameWorld for the pulse-based heartbeat system.
    """

    def __init__(self, world: GameWorld, port: int = 4001) -> None:
        self.world = world
        self.port = port
        self.descriptors: list[Descriptor] = []
        self._desc_counter: int = 0
        self._server: asyncio.Server | None = None
        self._shutdown: bool = False

    @property
    def player_count(self) -> int:
        """Number of descriptors currently connected."""
        return len(self.descriptors)

    async def start(self) -> None:
        """Start listening for connections and run the game loop.

        Mirrors init_game() + game_loop() from comm.c.
        """
        self._server = await asyncio.start_server(
            self._handle_new_connection,
            host="0.0.0.0",
            port=self.port,
        )
        addrs = ", ".join(str(s.getsockname()) for s in self._server.sockets)
        log.info("Dalila-MUD listening on %s", addrs)
        print(f"  Listening on port {self.port}")

        # Run the game heartbeat alongside the server
        async with self._server:
            heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            try:
                await self._server.serve_forever()
            except asyncio.CancelledError:
                pass
            finally:
                self._shutdown = True
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

    async def shutdown(self) -> None:
        """Gracefully shut down the server."""
        self._shutdown = True
        # Close all descriptors
        for desc in list(self.descriptors):
            await desc.send("\r\nServer shutting down. Goodbye!\r\n")
            await desc.close()
        self.descriptors.clear()
        if self._server:
            self._server.close()

    async def _handle_new_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle a new incoming connection.

        Mirrors new_descriptor() from comm.c.
        """
        self._desc_counter += 1
        desc = Descriptor(
            reader=reader,
            writer=writer,
            desc_num=self._desc_counter,
            state=ConnState.CON_GET_NAME,
        )
        self.descriptors.append(desc)

        peername = writer.get_extra_info("peername")
        log.info("New connection #%d from %s", desc.desc_num, peername)

        try:
            # Send the greeting text
            greeting = self.world.greeting_text
            if greeting:
                await desc.send(greeting)

            # Enter the nanny loop for this connection
            await self._connection_loop(desc)
        except Exception:
            log.exception("Error in connection #%d", desc.desc_num)
        finally:
            await self._remove_descriptor(desc)

    async def _connection_loop(self, desc: Descriptor) -> None:
        """Main loop for a single connection.

        Reads input, routes to nanny or command interpreter.
        Mirrors the per-descriptor processing in game_loop() from comm.c.
        """
        from dalila.commands.interpreter import command_interpreter
        from dalila.net.nanny import nanny

        while not desc.closing and not self._shutdown:
            line = await desc.read_line()
            if line is None:
                # Disconnect
                break

            # Reset idle timer
            desc.idle_tics = 0

            if desc.state != ConnState.CON_PLAYING:
                # In menus/login -- route to nanny
                await nanny(desc, line, self.world)
            else:
                # Playing -- route to command interpreter
                if desc.character:
                    command_interpreter(desc.character, line, desc, self.world)

            # Check if nanny closed the connection
            if desc.state == ConnState.CON_CLOSE:
                break

    async def _remove_descriptor(self, desc: Descriptor) -> None:
        """Remove a descriptor from the list and clean up.

        Mirrors close_socket() from comm.c.
        """
        if desc in self.descriptors:
            self.descriptors.remove(desc)

        # Remove character from world if playing
        if desc.character and desc.character in self.world.players:
            ch = desc.character
            room_vnum = ch.in_room
            if room_vnum in self.world.rooms:
                room = self.world.rooms[room_vnum]
                if ch in room._characters:
                    room._characters.remove(ch)
                    # Notify room
                    for other in room._characters:
                        if other.desc and other is not ch:
                            await other.desc.send(
                                f"\r\n{ch.player.name} ha lasciato il gioco.\r\n"
                            )
            self.world.players.remove(ch)
            log.info(
                "Player %s disconnected (#%d)",
                ch.player.name, desc.desc_num,
            )

        await desc.close()
        log.info("Connection #%d closed", desc.desc_num)

    async def _heartbeat_loop(self) -> None:
        """Run the pulse-based heartbeat system.

        Mirrors the missed_pulses/heartbeat() logic at the bottom
        of game_loop() in comm.c. One pulse = 0.1 seconds (OPT_USEC).
        """
        pulse_interval = 0.1  # OPT_USEC = 100000 usec = 0.1 sec

        while not self._shutdown:
            await asyncio.sleep(pulse_interval)
            self.world.pulse += 1
            self.world.heartbeat()

    def send_to_all(self, text: str) -> None:
        """Queue text to all playing connections.

        Used for global announcements (weather, time).
        Non-async version that schedules sends.
        """
        for desc in self.descriptors:
            if desc.state == ConnState.CON_PLAYING and not desc.closing:
                asyncio.ensure_future(desc.send(text))
