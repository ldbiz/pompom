"""Application constants and asset paths."""

import sys
from pathlib import Path

# Layout / geometry constants
_DEFAULT_W = 161
_DEFAULT_H = 96
_MAX_W = 560
_MAX_H = 328
_BODY_MARGIN = 0
_SHADOW_OFFSET = 3
_RESIZE_MARGIN = 16

_TITLE_H_FRAC = 0.13
_TIMER_H_FRAC = 0.22
_PLAY_H_FRAC = 0.20
_CYCLE_H_FRAC = 0.13
_N_GAPS = 5

# Timer display font
_TIMER_FONT_FAMILY = "Calibri Light"

_APP_VERSION = "1.0.0"

# Settings constants
_SETTINGS_ORG = "pompom"
_SETTINGS_APP = "pompom"
_DEFAULT_POMODORO_MINS = 25
_DEFAULT_BREAK_MINS = 5
_DEFAULT_LONG_BREAK_MINS = 30

_PACKAGE_DIR = Path(__file__).resolve().parent
_BASE_DIR = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else _PACKAGE_DIR.parent
_CARD_ASSET_PATH = _BASE_DIR / "images" / "red-card.png"
_CHECKBOX_UNCHECKED_PATH = _BASE_DIR / "images" / "checkbox_unchecked.png"
_CHECKBOX_CHECKED_PATH = _BASE_DIR / "images" / "checkbox_checked.png"
_CHECKBOX_UNCHECKED_DISABLED_PATH = _BASE_DIR / "images" / "checkbox_unchecked_disabled.png"
_CHECKBOX_CHECKED_DISABLED_PATH = _BASE_DIR / "images" / "checkbox_checked_disabled.png"
_TICKTOCK_PATH = _BASE_DIR / "sounds" / "ticktock.wav"
_DING_PATH = _BASE_DIR / "sounds" / "ding.wav"

# Feature constants
_BREAK_SUGGESTIONS: list[str] = [
    "Stretch",
    "Hydrate",
    "Rest your eyes",
    "Take a short walk",
    "Breathe deeply",
    "Look away",
    "Roll your shoulders",
    "Check your posture",
    "Stand up",
    "Relax your jaw",
    "Do some wrist circles",
    "Step outside",
    "Open a window",
    "Tidy your workspace"
]

_MOMENTUM_OFFER_SECS = 12
_MOMENTUM_EXTEND_MINS = 5
