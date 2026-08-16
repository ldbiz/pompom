"""Backward-compatible launcher for the pompom package."""

from pompom.app import main


if __name__ == "__main__":
    raise SystemExit(main())
