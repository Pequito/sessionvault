"""Dialog for browsing and selecting a KeePass entry."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from app.managers.keepass import keepass_manager


class KeePassSelectorDialog(QDialog):
    """Browse all entries in the currently open KeePass database."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select KeePass Entry")
        self.setMinimumSize(520, 440)
        self.selected_entry = None
        self._all_entries: list = []
        self._build_ui()
        self._load_entries()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 16, 16, 16)

        # Search bar
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Search:"))
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Filter by title, username, or group…")
        self._search_edit.textChanged.connect(self._filter)
        search_row.addWidget(self._search_edit, 1)
        root.addLayout(search_row)

        # Entry list
        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._confirm)
        root.addWidget(self._list, 1)

        # Dialog buttons
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = btns.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setObjectName("primary")
        ok_btn.setText("Select")
        btns.accepted.connect(self._confirm)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _load_entries(self) -> None:
        self._all_entries = keepass_manager.get_all_entries()
        self._render(self._all_entries)

    def _render(self, entries: list) -> None:
        self._list.clear()
        for entry in entries:
            group = entry.group.name if entry.group else ""
            label = f"{group} / {entry.title or ''}"
            if entry.username:
                label += f"   [{entry.username}]"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self._list.addItem(item)

    def _filter(self, query: str) -> None:
        q = query.lower()
        if not q:
            self._render(self._all_entries)
            return
        self._render([
            e for e in self._all_entries
            if q in (e.title or "").lower()
            or q in (e.username or "").lower()
            or q in (e.group.name if e.group else "").lower()
        ])

    # ------------------------------------------------------------------
    # Confirmation
    # ------------------------------------------------------------------

    def _confirm(self, *_args) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        self.selected_entry = item.data(Qt.ItemDataRole.UserRole)
        self.accept()
