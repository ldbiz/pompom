"""Shared Qt stylesheet and panel chrome for pompom floating panels."""

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

from ..constants import (
    _CHECKBOX_CHECKED_DISABLED_PATH,
    _CHECKBOX_CHECKED_PATH,
    _CHECKBOX_UNCHECKED_DISABLED_PATH,
    _CHECKBOX_UNCHECKED_PATH,
)


def _qss_url(path) -> str:
    return path.resolve().as_posix()


PANEL_STYLE = f"""
QWidget#TaskPanel, QWidget#OptionsPanel, QWidget#SoundsPanel {{
    background: #1E1010;
    border-radius: 10px;
}}
QWidget {{
    background: transparent;
    color: #D0C0C0;
    font-family: Inter, sans-serif;
    font-size: 11px;
}}
QListWidget {{
    background: #180E0E;
    border: 1px solid #3A2020;
    border-radius: 6px;
    outline: none;
}}
QListWidget::item {{
    border-bottom: 1px solid #2A1818;
    padding: 2px 0;
}}
QListWidget::item:selected {{
    background: #3A2020;
}}
QScrollBar:vertical {{
    width: 5px;
    background: transparent;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #5A3030;
    border-radius: 2px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QPushButton {{
    background: #2E1818;
    color: #C0A0A0;
    border: 1px solid #4A2828;
    border-radius: 5px;
    padding: 3px 8px;
    font-size: 11px;
}}
QPushButton:hover  {{ background: #3C2020; }}
QPushButton:pressed {{ background: #4A2828; }}
QPushButton:disabled {{ color: #6A4848; background: #241414; border-color: #3A2020; }}
QPushButton:checked {{ background: #3A2828; color: #E0C0A0; border-color: #7A5040; }}
QCheckBox {{
    color: #C0A0A0;
    spacing: 6px;
}}
QCheckBox:disabled {{
    color: #6A4848;
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
}}
QCheckBox::indicator:unchecked {{
    image: url({_qss_url(_CHECKBOX_UNCHECKED_PATH)});
}}
QCheckBox::indicator:checked {{
    image: url({_qss_url(_CHECKBOX_CHECKED_PATH)});
}}
QCheckBox::indicator:unchecked:disabled {{
    image: url({_qss_url(_CHECKBOX_UNCHECKED_DISABLED_PATH)});
}}
QCheckBox::indicator:checked:disabled {{
    image: url({_qss_url(_CHECKBOX_CHECKED_DISABLED_PATH)});
}}
QLineEdit, QSpinBox {{
    background: #180E0E;
    color: #D0C0C0;
    border: 1px solid #4A2828;
    border-radius: 4px;
    padding: 3px 6px;
    selection-background-color: #5A3030;
}}
QSpinBox::up-button, QSpinBox::down-button {{
    background: #2E1818;
    border: none;
    border-left: 1px solid #4A2828;
    width: 16px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background: #3C2020;
}}
QLabel {{ color: #A07070; }}
QLabel#header {{ color: #9A7070; font-size: 12px; font-weight: 500; }}
QLabel#hint {{ color: #7A5A5A; font-size: 10px; }}
"""


def paint_floating_panel(painter: QPainter, rect: QRectF) -> None:
    """Draw layered shadow, fill, and border for a rounded floating panel."""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    body = rect.adjusted(4, 4, -4, -4)
    for i, alpha in enumerate([35, 20, 10]):
        shadow_rect = body.adjusted(0, i, 0, i)
        path = QPainterPath()
        path.addRoundedRect(shadow_rect, 10, 10)
        painter.fillPath(path, QColor(0, 0, 0, alpha))
    path = QPainterPath()
    path.addRoundedRect(body, 10, 10)
    painter.fillPath(path, QColor(30, 16, 16, 245))
    painter.setPen(QPen(QColor(80, 40, 40, 80), 1.0))
    painter.drawRoundedRect(body, 10, 10)
