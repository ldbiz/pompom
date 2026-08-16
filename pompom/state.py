"""Transient UI/timer state."""

from dataclasses import dataclass


@dataclass
class UIState:
    running: bool      = False
    hovered_play: bool = False
    pressed_play: bool = False
    cycle_index: int   = 1
    cycle_total: int   = 4
    remaining_seconds: int = 0   # set from pomodoro duration at startup
    mode: str          = "pomodoro"  # "pomodoro" | "short_break" | "long_break"
    # Momentum mode
    momentum_offer: bool = False
    momentum_remaining: int = 0
    momentum_zone_hover: str = ""   # "accept" | "skip" | ""
    momentum_zone_press: str = ""   # "accept" | "skip" | ""
    # Selected once when a break starts and kept for that break's duration.
    break_suggestion: str = ""

