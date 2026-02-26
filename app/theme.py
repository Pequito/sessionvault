"""Qt Style Sheet (QSS) for the Catppuccin Mocha dark theme."""

from __future__ import annotations

from app.constants import C


def stylesheet() -> str:
    """Return the full application QSS stylesheet string."""
    return f"""
/* ==========================================================================
   Global
   ========================================================================== */
* {{
    outline: none;
}}

QMainWindow, QWidget {{
    background-color: {C["base"]};
    color: {C["text"]};
    font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif;
    font-size: 10pt;
}}

/* ==========================================================================
   Menu bar
   ========================================================================== */
QMenuBar {{
    background-color: {C["mantle"]};
    color: {C["text"]};
    padding: 2px 4px;
    border-bottom: 1px solid {C["surface0"]};
}}

QMenuBar::item {{
    padding: 4px 10px;
    border-radius: 4px;
}}

QMenuBar::item:selected {{
    background-color: {C["surface1"]};
}}

QMenu {{
    background-color: {C["surface0"]};
    color: {C["text"]};
    border: 1px solid {C["surface1"]};
    padding: 4px 0;
    border-radius: 6px;
}}

QMenu::item {{
    padding: 5px 28px 5px 16px;
}}

QMenu::item:selected {{
    background-color: {C["blue"]};
    color: {C["base"]};
    border-radius: 3px;
}}

QMenu::separator {{
    height: 1px;
    background: {C["surface1"]};
    margin: 4px 8px;
}}

/* ==========================================================================
   Status bar
   ========================================================================== */
QStatusBar {{
    background-color: {C["mantle"]};
    color: {C["subtext0"]};
    font-size: 9pt;
    border-top: 1px solid {C["surface0"]};
    padding: 2px 8px;
}}

/* ==========================================================================
   Splitter
   ========================================================================== */
QSplitter::handle {{
    background-color: {C["surface0"]};
}}

QSplitter::handle:horizontal {{
    width: 1px;
}}

QSplitter::handle:vertical {{
    height: 1px;
}}

/* ==========================================================================
   Scroll bars
   ========================================================================== */
QScrollBar:vertical {{
    background: {C["mantle"]};
    width: 8px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {C["surface2"]};
    border-radius: 4px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background: {C["overlay0"]};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: {C["mantle"]};
    height: 8px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background: {C["surface2"]};
    border-radius: 4px;
    min-width: 20px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {C["overlay0"]};
}}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ==========================================================================
   Tab widget
   ========================================================================== */
QTabWidget::pane {{
    border: none;
    background-color: {C["base"]};
}}

QTabBar {{
    background-color: {C["crust"]};
}}

QTabBar::tab {{
    background-color: {C["surface0"]};
    color: {C["subtext0"]};
    padding: 6px 16px;
    border: none;
    border-right: 1px solid {C["surface1"]};
    min-width: 80px;
}}

QTabBar::tab:selected {{
    background-color: {C["base"]};
    color: {C["text"]};
    border-bottom: 2px solid {C["blue"]};
}}

QTabBar::tab:hover:!selected {{
    background-color: {C["surface1"]};
    color: {C["text"]};
}}

QTabBar::close-button {{
    subcontrol-position: right;
    padding: 2px;
}}

/* ==========================================================================
   Tree widget
   ========================================================================== */
QTreeWidget {{
    background-color: {C["mantle"]};
    color: {C["text"]};
    border: none;
    font-family: "Monospace", monospace;
    font-size: 10pt;
}}

QTreeWidget::item {{
    padding: 3px 4px;
    border-radius: 3px;
}}

QTreeWidget::item:selected {{
    background-color: {C["blue"]};
    color: {C["base"]};
}}

QTreeWidget::item:hover:!selected {{
    background-color: {C["surface0"]};
}}

QTreeWidget::branch {{
    background: {C["mantle"]};
}}

/* ==========================================================================
   List widget
   ========================================================================== */
QListWidget {{
    background-color: {C["mantle"]};
    color: {C["text"]};
    border: none;
    font-family: "Monospace", monospace;
    font-size: 9pt;
}}

QListWidget::item {{
    padding: 2px 8px;
}}

QListWidget::item:selected {{
    background-color: {C["mauve"]};
    color: {C["base"]};
    border-radius: 3px;
}}

QListWidget::item:hover:!selected {{
    background-color: {C["surface0"]};
}}

/* ==========================================================================
   Buttons
   ========================================================================== */
QPushButton {{
    background-color: {C["surface1"]};
    color: {C["text"]};
    border: none;
    padding: 5px 14px;
    border-radius: 5px;
    font-size: 10pt;
}}

QPushButton:hover {{
    background-color: {C["surface2"]};
}}

QPushButton:pressed {{
    background-color: {C["surface0"]};
}}

QPushButton#primary {{
    background-color: {C["blue"]};
    color: {C["base"]};
    font-weight: bold;
}}

QPushButton#primary:hover {{
    background-color: {C["lavender"]};
}}

QPushButton#success {{
    background-color: {C["green"]};
    color: {C["base"]};
    font-weight: bold;
}}

QPushButton#success:hover {{
    background-color: {C["teal"]};
}}

QPushButton#danger {{
    background-color: {C["red"]};
    color: {C["base"]};
}}

QPushButton#danger:hover {{
    background-color: {C["maroon"]};
}}

/* ==========================================================================
   Line edits
   ========================================================================== */
QLineEdit {{
    background-color: {C["surface0"]};
    color: {C["text"]};
    border: 1px solid {C["surface1"]};
    border-radius: 5px;
    padding: 4px 8px;
    selection-background-color: {C["blue"]};
    selection-color: {C["base"]};
}}

QLineEdit:focus {{
    border-color: {C["blue"]};
}}

QLineEdit:disabled {{
    color: {C["overlay0"]};
}}

/* ==========================================================================
   Labels
   ========================================================================== */
QLabel {{
    color: {C["subtext0"]};
}}

QLabel#kp-entry {{
    background-color: {C["surface0"]};
    color: {C["text"]};
    border: 1px solid {C["surface1"]};
    border-radius: 5px;
    padding: 4px 8px;
    font-family: monospace;
}}

QLabel#status-connected {{
    color: {C["green"]};
    font-size: 9pt;
    padding: 2px 8px;
    background-color: {C["surface0"]};
}}

QLabel#status-error {{
    color: {C["red"]};
    font-size: 9pt;
    padding: 2px 8px;
    background-color: {C["surface0"]};
}}

QLabel#status-connecting {{
    color: {C["yellow"]};
    font-size: 9pt;
    padding: 2px 8px;
    background-color: {C["surface0"]};
}}

/* ==========================================================================
   Terminal text area
   ========================================================================== */
QTextEdit#terminal {{
    background-color: {C["base"]};
    color: {C["text"]};
    border: none;
    font-family: "Cascadia Code", "JetBrains Mono", "Fira Code", "Courier New", monospace;
    font-size: 11pt;
    selection-background-color: {C["surface1"]};
}}

/* ==========================================================================
   Dialogs
   ========================================================================== */
QDialog {{
    background-color: {C["base"]};
}}

/* ==========================================================================
   Group boxes
   ========================================================================== */
QGroupBox {{
    border: 1px solid {C["surface1"]};
    border-radius: 6px;
    margin-top: 8px;
    padding: 10px 8px 8px 8px;
    color: {C["subtext0"]};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {C["overlay2"]};
}}

/* ==========================================================================
   Dialog button box
   ========================================================================== */
QDialogButtonBox QPushButton {{
    min-width: 80px;
}}
"""
