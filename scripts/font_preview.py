"""One-off script: render a font preview sheet for timer digit selection."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

SAMPLE = "02:46"
TEXT_COLOR = QColor("#E6D5D2")
LABEL_COLOR = QColor("#C89595")
BG_COLOR = QColor("#8F3030")

CANDIDATES: list[tuple[str, str, str, QFont.Weight]] = [
    ("A", "Segoe UI Light", "Segoe UI Light", QFont.Weight.Light),
    ("B", "Segoe UI Semilight", "Segoe UI Semilight", QFont.Weight.Normal),
    ("C", "Bahnschrift Light", "Bahnschrift", QFont.Weight.Light),
    ("D", "Corbel Light", "Corbel Light", QFont.Weight.Normal),
    ("E", "Calibri Light", "Calibri Light", QFont.Weight.Normal),
    ("F", "Candara Light", "Candara Light", QFont.Weight.Normal),
    ("G", "Consolas", "Consolas", QFont.Weight.Normal),
    ("H", "Cascadia Mono Light", "Cascadia Mono", QFont.Weight.Light),
    ("I", "Franklin Gothic Medium", "Franklin Gothic Medium", QFont.Weight.Normal),
    ("J", "Inter Light (current)", "Inter", QFont.Weight.Light),
]

LABEL_PT = 10
SAMPLE_PT = 20
ROW_H = 36
PAD_X = 16
LABEL_W = 200
SAMPLE_X = PAD_X + LABEL_W + 12


def main() -> None:
    app = QApplication(sys.argv)

    card_path = Path(__file__).resolve().parent.parent / "images" / "red-card.png"
    card_pixmap = QPixmap(str(card_path)) if card_path.is_file() else QPixmap()

    width = 420
    height = PAD_X * 2 + ROW_H * len(CANDIDATES)
    pixmap = QPixmap(width, height)
    pixmap.fill(BG_COLOR)

    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

    if not card_pixmap.isNull():
        p.drawPixmap(0, 0, card_pixmap.scaled(width, height, Qt.AspectRatioMode.IgnoreAspectRatio))

    for i, (letter, label, family, weight) in enumerate(CANDIDATES):
        y = PAD_X + i * ROW_H
        baseline = y + ROW_H // 2 + SAMPLE_PT // 3

        label_font = QFont("Segoe UI", LABEL_PT)
        label_font.setWeight(QFont.Weight.Normal)
        p.setFont(label_font)
        p.setPen(LABEL_COLOR)
        p.drawText(PAD_X, baseline, f"{letter}. {label}")

        sample_font = QFont(family, SAMPLE_PT)
        sample_font.setWeight(weight)
        p.setFont(sample_font)
        p.setPen(TEXT_COLOR)
        p.drawText(SAMPLE_X, baseline, SAMPLE)

    p.end()

    out = Path(__file__).resolve().parent.parent / "font-preview.png"
    pixmap.save(str(out))
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
