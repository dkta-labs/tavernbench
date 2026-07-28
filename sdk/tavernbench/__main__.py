"""
tavernbench CLI dispatcher.

  tavernbench doctor [options]
"""
from __future__ import annotations

import sys


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print("usage: tavernbench <command> [options]")
        print()
        print("commands:")
        print("  doctor    Check server, API key, and MCP registration")
        print()
        print("Run 'tavernbench <command> --help' for command-specific options.")
        sys.exit(0)

    cmd, *rest = args
    if cmd == "doctor":
        from .doctor import main as doctor_main
        sys.exit(doctor_main(rest))
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print("Run 'tavernbench --help' for usage.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
