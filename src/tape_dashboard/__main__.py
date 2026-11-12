"""
Runs the dashboard:

    python -m tape_dashboard [--port 8050] [--debug]

It only listens on 127.0.0.1: the dashboard has no authentication and it
edits data, so it is not exposed to other devices (decision 0023). Variables
in a .env file at the repository root are loaded first (see .env.example).
"""

import argparse
import sys

from .config import load_env_file

HOST = "127.0.0.1"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Tape Reading Dashboard (local only)")
    parser.add_argument("--port", type=int, default=8050, help="port on 127.0.0.1 (default 8050)")
    parser.add_argument("--debug", action="store_true", help="Dash debug mode with hot reload")
    args = parser.parse_args(argv)

    from .app import create_app  # imported here so --help works without loading the data

    load_env_file()
    app = create_app()
    print(f"Tape Reading Dashboard: http://{HOST}:{args.port}")
    app.run(host=HOST, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    sys.exit(main())
