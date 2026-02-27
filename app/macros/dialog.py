"""Macro Manager dialog – view, record, play, and delete macros."""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.macros.manager import macro_manager


class MacroManagerDialog(QDialog):
    """Browse saved macros and optionally play one into a terminal."""

    def __init__(
        self,
        parent=None,
        on_play: Optional[Callable[[list[str]], None]] = None,
    ) -> None:
        super().__init__(parent)
        self._on_play = on_play
        self.setWindowTitle("Macro Manager")
        self.setMinimumSize(480, 360)
        self._build_ui()
        self._refresh()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 16, 16, 16)

        root.addWidget(QLabel("Saved macros  (double-click to play):"))

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._play)
        root.addWidget(self._list, 1)

        btn_row = QHBoxLayout()

        play_btn = QPushButton("▶  Play")
        play_btn.setObjectName("primary")
        play_btn.clicked.connect(self._play)
        btn_row.addWidget(play_btn)

        rename_btn = QPushButton("Rename…")
        rename_btn.clicked.connect(self._rename)
        btn_row.addWidget(rename_btn)

        btn_row.addStretch()

        del_btn = QPushButton("Delete")
        del_btn.setObjectName("danger")
        del_btn.clicked.connect(self._delete)
        btn_row.addWidget(del_btn)

        root.addLayout(btn_row)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        self._list.clear()
        for name, cmds in macro_manager.all().items():
            item = QListWidgetItem(f"{name}  ({len(cmds)} step(s))")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self._list.addItem(item)

    def _current_name(self) -> Optional[str]:
        item = self._list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _play(self, *_) -> None:
        name = self._current_name()
        if not name:
            return
        cmds = macro_manager.get(name)
        if self._on_play:
            self._on_play(cmds)
        self.accept()

    def _rename(self) -> None:
        name = self._current_name()
        if not name:
            return
        new_name, ok = QInputDialog.getText(
            self, "Rename Macro", "New name:", text=name
        )
        if ok and new_name.strip() and new_name.strip() != name:
            cmds = macro_manager.get(name)
            macro_manager.delete_macro(name)
            macro_manager.save_macro(new_name.strip(), cmds)
            self._refresh()

    def _delete(self) -> None:
        name = self._current_name()
        if not name:
            return
        reply = QMessageBox.question(
            self,
            "Delete Macro",
            f"Delete macro '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            macro_manager.delete_macro(name)
            self._refresh()


class MacroSaveDialog(QDialog):
    """Prompt for a name and save a recorded command list as a macro."""

    def __init__(self, commands: list[str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Save Macro")
        self.setMinimumWidth(360)
        self._commands = commands
        self._build_ui()

    def _build_ui(self) -> None:
        from PySide6.QtWidgets import QFormLayout, QLineEdit
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        form = QFormLayout()
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("My macro")
        form.addRow("Macro name:", self._name_edit)
        root.addLayout(form)

        info = QLabel(f"{len(self._commands)} command(s) recorded.")
        root.addWidget(info)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Save).setObjectName("primary")
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    def _save(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Please enter a macro name.")
            return
        macro_manager.save_macro(name, self._commands)
        self.accept()
