"""Entry point; no subcommand still runs the daemon for backward compatibility."""

from sentinelx_agent.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
