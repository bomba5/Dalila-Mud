"""Entry point for Dalila-MUD."""

import sys


def main() -> None:
    """Boot and run Dalila-MUD."""
    print(f"Dalila-MUD Python port v{__import__('dalila').__version__}")
    print("Use 'python -m dalila --help' for options.")
    sys.exit(0)


if __name__ == "__main__":
    main()
