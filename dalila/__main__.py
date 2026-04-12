"""Entry point for Dalila-MUD Python port.

Boots the game world, loads all data files, starts the network server.
Usage: python3 -m dalila [--port PORT] [--lib LIB_PATH]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path


def main() -> None:
    """Boot and run Dalila-MUD."""
    parser = argparse.ArgumentParser(description="Dalila-MUD Python port")
    parser.add_argument(
        "--port", type=int, default=4001,
        help="Port to listen on (default: 4001)",
    )
    parser.add_argument(
        "--lib", type=str, default=None,
        help="Path to lib/ directory (default: auto-detect)",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    log = logging.getLogger("dalila")

    # Find lib/ directory
    if args.lib:
        lib_path = Path(args.lib)
    else:
        # Try relative to the project root
        candidates = [
            Path(__file__).parent.parent / "lib",
            Path.cwd() / "lib",
        ]
        lib_path = None
        for candidate in candidates:
            if candidate.is_dir():
                lib_path = candidate
                break
        if lib_path is None:
            print("ERROR: Cannot find lib/ directory. Use --lib to specify.")
            sys.exit(1)

    version = __import__("dalila").__version__
    print(f"\r\nDalila-MUD Python port v{version}")
    print(f"{'=' * 50}")

    # Boot the game world
    from dalila.engine.game_loop import GameWorld
    from dalila.net.server import GameServer

    boot_start = time.time()

    world = GameWorld()
    print(f"\r\nBooting world from {lib_path}...")

    try:
        world.load_world_data(lib_path)
    except Exception as e:
        log.exception("Failed to load world data")
        print(f"ERROR: {e}")
        sys.exit(1)

    boot_time = time.time() - boot_start

    # Boot summary
    print(f"\r\n{'=' * 50}")
    print(f"  Rooms:    {len(world.rooms):>6}")
    print(f"  Zones:    {len(world.zones):>6}")
    print(f"  Mobs:     {len(world.mob_protos):>6}")
    print(f"  Objects:  {len(world.obj_protos):>6}")
    print(f"  Shops:    {len(world.shops):>6}")
    print(f"  Triggers: {len(world.triggers):>6}")
    print(f"  Boot time: {boot_time:.2f}s")
    print(f"{'=' * 50}")
    print(f"\r\n  Start room: {world.mortal_start_room}")

    # Start the server
    server = GameServer(world, port=args.port)
    print(f"\r\n  Starting server on port {args.port}...")
    print(f"  Use: telnet localhost {args.port}")
    print(f"{'=' * 50}\r\n")

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("\r\nShutting down...")


if __name__ == "__main__":
    main()
