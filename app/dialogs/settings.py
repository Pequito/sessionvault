"""Application Settings dialog.

Covers:
  • Appearance  – theme picker + custom application icon
  • Terminal    – font size
  • Auto-Type   – keystroke delay
  • KeePass     – clipboard auto-clear timeout
  • Plugins     – loaded plugin list + reload

The dialog has three buttons:
  OK     – save all settings and close
  Apply  – save all settings immediately without closing
  Cancel – discard and close
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
from app.managers.logger import get_logger
from app.plugins.loader import plugin_loader

log = get_logger(__name__)


class SettingsDialog(QDialog):
    """Application-wide settings with OK / Apply / Cancel."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(520, 460)
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
        tabs.addTab(self._tab_terminal(),   "Terminal")
        tabs.addTab(self._tab_autotype(),   "Auto-Type")
        tabs.addTab(self._tab_keepass(),    "KeePass")
        tabs.addTab(self._tab_plugins(),    "Plugins")
        root.addWidget(tabs)

        # ── Button row: OK | Apply | Cancel ───────────────────────────
        self._btns = QDialogButtonBox()
        ok_btn     = self._btns.addButton(QDialogButtonBox.StandardButton.Ok)
        apply_btn  = self._btns.addButton(QDialogButtonBox.StandardButton.Apply)
        _cancel    = self._btns.addButton(QDialogButtonBox.StandardButton.Cancel)

        ok_btn.setObjectName("primary")
        apply_btn.setObjectName("apply")

        self._btns.clicked.connect(self._on_button_clicked)
        self._btns.rejected.connect(self.reject)
        root.addWidget(self._btns)

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

        note = QLabel("Theme changes take effect immediately on Apply / OK.")
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

    # ── KeePass tab ────────────────────────────────────────────────────

    def _tab_keepass(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)
        form.setContentsMargins(16, 16, 16, 16)

        self._clip_timeout_spin = QSpinBox()
        self._clip_timeout_spin.setRange(0, 120)
        self._clip_timeout_spin.setSuffix("  s")
        self._clip_timeout_spin.setSpecialValueText("Disabled (0)")
        form.addRow("Clipboard auto-clear", self._clip_timeout_spin)

        shortcuts_info = QLabel(
            "In the KeePass panel:\n"
            "  Ctrl+U  – copy username of selected entry\n"
            "  Ctrl+P  – copy password of selected entry\n\n"
            "After copying, the clipboard is automatically cleared after the\n"
            "timeout above.  Set to 0 to disable auto-clear."
        )
        shortcuts_info.setWordWrap(True)
        form.addRow("", shortcuts_info)
        return w

    # ── Plugins tab ────────────────────────────────────────────────────

    def _tab_plugins(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Plugin directory: ~/.sessionvault/plugins/"))

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
        self._clip_timeout_spin.setValue(
            settings_manager.get("clipboard_clear_timeout_s", 15)
        )

    def _save_settings(self) -> None:
        """Persist current UI values to settings_manager and apply immediately."""
        theme_name  = self._theme_combo.currentText()
        icon_path   = self._icon_edit.text().strip()
        font_size   = self._font_spin.value()
        delay       = self._delay_spin.value()
        clip_timeout = self._clip_timeout_spin.value()

        settings_manager.set("theme",                    theme_name)
        settings_manager.set("app_icon",                 icon_path)
        settings_manager.set("font_size_terminal",       font_size)
        settings_manager.set("autotype_delay_ms",        delay)
        settings_manager.set("clipboard_clear_timeout_s", clip_timeout)

        from app.theme import apply_theme  # noqa: PLC0415
        apply_theme(theme_name)

        if icon_path:
            app = QApplication.instance()
            if app:
                app.setWindowIcon(QIcon(icon_path))

        log.info(
            "Settings saved: theme=%s  font=%dpt  autotype_delay=%dms  "
            "clip_timeout=%ds",
            theme_name, font_size, delay, clip_timeout,
        )

    def _on_button_clicked(self, btn) -> None:
        role = self._btns.buttonRole(btn)
        if role == QDialogButtonBox.ButtonRole.AcceptRole:   # OK
            self._save_settings()
            self.accept()
        elif role == QDialogButtonBox.ButtonRole.ApplyRole:  # Apply
            self._save_settings()
        # Cancel is handled by the rejected signal → self.reject()

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
