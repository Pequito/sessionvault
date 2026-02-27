"""Application Settings dialog.

Covers:
  • Appearance – theme picker + custom application icon
  • Terminal    – font size
  • Auto-Type   – keystroke delay
  • Plugins     – loaded plugin list
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.constants import THEMES
from app.managers.settings import settings_manager
from app.plugins.loader import plugin_loader


class SettingsDialog(QDialog):
    """Application-wide settings."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(520, 420)
        self._build_ui()
        self._load()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        tabs = QTabWidget()
        tabs.setObjectName("settings-tabs")
        tabs.addTab(self._tab_appearance(), "Appearance")
        tabs.addTab(self._tab_terminal(), "Terminal")
        tabs.addTab(self._tab_autotype(), "Auto-Type")
        tabs.addTab(self._tab_plugins(), "Plugins")
        root.addWidget(tabs)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primary")
        btns.accepted.connect(self._apply)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    # ── Appearance tab ─────────────────────────────────────────────────

    def _tab_appearance(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)
        form.setContentsMargins(16, 16, 16, 16)

        self._theme_combo = QComboBox()
        for name in THEMES:
            self._theme_combo.addItem(name)
        form.addRow("Color theme", self._theme_combo)

        icon_row = QHBoxLayout()
        self._icon_edit = QLineEdit()
        self._icon_edit.setPlaceholderText("Leave blank for default icon")
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_icon)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(lambda: self._icon_edit.clear())
        icon_row.addWidget(self._icon_edit, 1)
        icon_row.addWidget(browse_btn)
        icon_row.addWidget(clear_btn)
        form.addRow("Application icon (.png/.ico)", icon_row)

        note = QLabel("Theme changes take effect immediately on OK.")
        note.setWordWrap(True)
        form.addRow("", note)
        return w

    # ── Terminal tab ───────────────────────────────────────────────────

    def _tab_terminal(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)
        form.setContentsMargins(16, 16, 16, 16)

        self._font_spin = QSpinBox()
        self._font_spin.setRange(8, 28)
        self._font_spin.setSuffix("  pt")
        form.addRow("Terminal font size", self._font_spin)

        note = QLabel("Font size changes apply to new tabs only.")
        note.setWordWrap(True)
        form.addRow("", note)
        return w

    # ── Auto-Type tab ──────────────────────────────────────────────────

    def _tab_autotype(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)
        form.setContentsMargins(16, 16, 16, 16)

        self._delay_spin = QSpinBox()
        self._delay_spin.setRange(0, 1000)
        self._delay_spin.setSuffix("  ms")
        form.addRow("Keystroke delay", self._delay_spin)

        info = QLabel(
            "Global Auto-Type simulates keystrokes in the currently focused window.\n\n"
            "Requirements:\n"
            "  • Linux/X11:  pip install pynput python3-xlib\n"
            "  • macOS:      pip install pynput  (grant Accessibility permission)\n"
            "  • Windows:    pip install pynput"
        )
        info.setWordWrap(True)
        form.addRow("", info)
        return w

    # ── Plugins tab ────────────────────────────────────────────────────

    def _tab_plugins(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        layout.addWidget(QLabel(f"Plugin directory: ~/.sessionvault/plugins/"))

        self._plugin_list = QListWidget()
        layout.addWidget(self._plugin_list, 1)

        reload_btn = QPushButton("Reload plugins")
        reload_btn.clicked.connect(self._reload_plugins)
        layout.addWidget(reload_btn)

        self._reload_plugins()
        return w

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        theme = settings_manager.get("theme", "Catppuccin Mocha")
        idx = self._theme_combo.findText(theme)
        if idx >= 0:
            self._theme_combo.setCurrentIndex(idx)
        self._icon_edit.setText(settings_manager.get("app_icon", ""))
        self._font_spin.setValue(settings_manager.get("font_size_terminal", 11))
        self._delay_spin.setValue(settings_manager.get("autotype_delay_ms", 50))

    def _apply(self) -> None:
        theme_name = self._theme_combo.currentText()
        icon_path = self._icon_edit.text().strip()
        font_size = self._font_spin.value()
        delay = self._delay_spin.value()

        settings_manager.set("theme", theme_name)
        settings_manager.set("app_icon", icon_path)
        settings_manager.set("font_size_terminal", font_size)
        settings_manager.set("autotype_delay_ms", delay)

        # Apply theme immediately
        from app.theme import apply_theme
        apply_theme(theme_name)

        # Apply icon immediately
        if icon_path:
            app = QApplication.instance()
            if app:
                app.setWindowIcon(QIcon(icon_path))

        self.accept()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _browse_icon(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Application Icon",
            "",
            "Images (*.png *.ico *.jpg *.svg);;All files (*)",
        )
        if path:
            self._icon_edit.setText(path)

    def _reload_plugins(self) -> None:
        loaded = plugin_loader.load_all()
        errors = plugin_loader.errors
        self._plugin_list.clear()
        if not loaded and not errors:
            self._plugin_list.addItem("  (no plugins found)")
            return
        for name in loaded:
            self._plugin_list.addItem(f"  ✓  {name}")
        for name, err in errors.items():
            self._plugin_list.addItem(f"  ✗  {name}  — {err}")
