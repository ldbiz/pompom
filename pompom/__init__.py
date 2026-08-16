"""PomPom Pomodoro timer package."""

__all__ = ["main"]


def main() -> int:
    """Start the pomPom desktop application."""
    from .app import main as app_main

    return app_main()
