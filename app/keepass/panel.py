"""KeePass sidebar panel – KeePassXC-style hierarchical tree view.

Features
--------
* QTreeWidget showing groups (folders) with nested entries, mirroring the
  KeePassXC layout: expand/collapse, icons, sorted alphabetically.
* Multi-database support: QComboBox lets users switch between all currently
  open databases; a "+" button requests opening an additional database.
* Keyboard shortcuts
    Ctrl+U  – copy username of selected entry to clipboard
    Ctrl+P  – copy password of selected entry to clipboard
* Clipboard auto-clear: a QTimer clears the clipboard after a configurable
  timeout (settings key ``clipboard_clear_timeout_s``, default 15 s).
  Set to 0 to disable auto-clear.
* Right-click context menu: Copy Username / Password / URL, SSH Auto-fill,
  Edit Entry, Delete Entry.
* Double-click an entry copies its password (same as KeePassXC default).
* Search bar filters entries across all groups in real time.
"""

from __future__ import annotations

import pathlib
from collections import defaultdict
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.managers.keepass import keepass_manager
from app.managers.logger import get_logger
from app.managers.settings import settings_manager

log = get_logger(__name__)

# Marker stored in UserRole+1 to distinguish tree node types
_TYPE_GROUP = "group"
_TYPE_ENTRY = "entry"

# Unicode icons
_ICON_DB      = "\U0001F5C4"   # 🗄  open cabinet
_ICON_GROUP   = "\U0001F4C2"   # 📂  open folder
_ICON_SUBGRP  = "\U0001F4C1"   # 📁  folder
_ICON_ENTRY   = "\U0001F511"   # 🔑  key


class KeePassPanel(QWidget):
    """KeePassXC-style sidebar panel for KeePass database browsing.

    Signals
    -------
    autofill_requested(username, password)
        Emitted when the user clicks "SSH Auto-fill" on an entry.  The
        terminal widget connects this to paste credentials into the shell.
    open_db_requested()
        Emitted when the user clicks the "+" button to open another database.
        The main window is expected to show the open-database dialog and call
        :meth:`refresh` afterwards.
    """

    autofill_requested = Signal(str, str)   # username, password
    open_db_requested  = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._clipboard_timer = QTimer(self)
        self._clipboard_timer.setSingleShot(True)
        self._clipboard_timer.timeout.connect(self._clear_clipboard)
        self._build_ui()
        self._install_shortcuts()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Database selector row ──────────────────────────────────────
        db_bar = QWidget()
        db_bar.setObjectName("kp-db-bar")
        db_row = QHBoxLayout(db_bar)
        db_row.setContentsMargins(6, 3, 4, 3)
        db_row.setSpacing(3)

        self._db_combo = QComboBox()
        self._db_combo.setToolTip("Active database  (click + to open another)")
        self._db_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._db_combo.currentIndexChanged.connect(self._on_db_changed)
        db_row.addWidget(self._db_combo, 1)

        open_btn = QPushButton("+")
        open_btn.setToolTip("Open another KeePass database")
        open_btn.setFixedSize(22, 22)
        open_btn.setObjectName("kp-db-btn")
        open_btn.clicked.connect(self.open_db_requested.emit)
        db_row.addWidget(open_btn)

        close_btn = QPushButton("✕")
        close_btn.setToolTip("Close active database")
        close_btn.setFixedSize(22, 22)
        close_btn.setObjectName("kp-db-btn")
        close_btn.clicked.connect(self._close_active_db)
        db_row.addWidget(close_btn)

        layout.addWidget(db_bar)

        # ── Search bar ────────────────────────────────────────────────
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("  Search entries…")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.setObjectName("kp-search")
        self._search_edit.textChanged.connect(self._on_search)
        layout.addWidget(self._search_edit)

        # ── Tree ──────────────────────────────────────────────────────
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setRootIsDecorated(True)
        self._tree.setIndentation(14)
        self._tree.setAnimated(True)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self._tree.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._tree, 1)

        # ── Status label ──────────────────────────────────────────────
        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("kp-status")
        self._status_lbl.setWordWrap(False)
        layout.addWidget(self._status_lbl)

    def _install_shortcuts(self) -> None:
        sc_u = QShortcut(QKeySequence("Ctrl+U"), self)
        sc_u.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_u.activated.connect(self._copy_username)

        sc_p = QShortcut(QKeySequence("Ctrl+P"), self)
        sc_p.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_p.activated.connect(self._copy_password)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Rebuild the database selector combo and the tree from manager state."""
        self._rebuild_combo()
        self._rebuild_tree()

    # ------------------------------------------------------------------
    # Database combo
    # ------------------------------------------------------------------

    def _rebuild_combo(self) -> None:
        self._db_combo.blockSignals(True)
        self._db_combo.clear()
        paths = keepass_manager.open_paths
        if paths:
            for path in paths:
                self._db_combo.addItem(
                    f"{_ICON_DB}  {pathlib.Path(path).name}",
                    userData=path,
                )
            # Select the active db
            active = keepass_manager.db_path
            for i in range(self._db_combo.count()):
                if self._db_combo.itemData(i) == active:
                    self._db_combo.setCurrentIndex(i)
                    break
        else:
            self._db_combo.addItem("(no database open)")
        self._db_combo.blockSignals(False)

    def _on_db_changed(self, index: int) -> None:
        path = self._db_combo.itemData(index)
        if path:
            keepass_manager.set_active(path)
            self._rebuild_tree()
            log.debug("KeePass panel switched to database: %s", path)

    # ------------------------------------------------------------------
    # Tree construction
    # ------------------------------------------------------------------

    def _rebuild_tree(self) -> None:
        self._tree.clear()
        self._search_edit.blockSignals(True)
        self._search_edit.clear()
        self._search_edit.blockSignals(False)

        if not keepass_manager.is_open:
            placeholder = QTreeWidgetItem(self._tree, ["  (open a database first)"])
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            return

        groups  = keepass_manager.get_groups()
        entries = keepass_manager.get_all_entries()

        # Map group UUID string → list of entries
        group_entries: dict[str, list] = defaultdict(list)
        for entry in entries:
            gid = str(entry.group.uuid) if entry.group else "__root__"
            group_entries[gid].append(entry)

        # Separate root group from child groups
        root_group   = None
        child_groups: list = []
        for g in groups:
            if g.parent_group is None:
                root_group = g
            else:
                child_groups.append(g)

        child_groups.sort(key=lambda g: (g.name or "").lower())

        def _add_group(
            parent_item: Optional[QTreeWidgetItem],
            group,
            depth: int = 0,
        ) -> QTreeWidgetItem:
            gname = group.name or "(unnamed)"
            icon  = _ICON_GROUP if depth == 0 else _ICON_SUBGRP
            label = f"  {icon}  {gname}"

            if parent_item is None:
                item = QTreeWidgetItem(self._tree, [label])
            else:
                item = QTreeWidgetItem(parent_item, [label])

            item.setData(0, Qt.ItemDataRole.UserRole + 1, _TYPE_GROUP)
            item.setData(0, Qt.ItemDataRole.UserRole, group)
            item.setExpanded(True)

            # Entries under this group (sorted by title)
            gid = str(group.uuid)
            for entry in sorted(
                group_entries.get(gid, []),
                key=lambda e: (e.title or "").lower(),
            ):
                _add_entry_item(item, entry)

            # Direct child sub-groups (sorted by name)
            direct_children = [
                g for g in child_groups
                if g.parent_group and str(g.parent_group.uuid) == gid
            ]
            for sg in sorted(direct_children, key=lambda g: (g.name or "").lower()):
                _add_group(item, sg, depth + 1)

            return item

        if root_group:
            _add_group(None, root_group, 0)

    def _add_entry_item(
        self,
        parent: QTreeWidgetItem,
        entry,
    ) -> QTreeWidgetItem:
        title    = entry.title    or "(no title)"
        username = entry.username or ""
        label = f"  {_ICON_ENTRY}  {title}"
        if username:
            label += f"   [{username}]"
        item = QTreeWidgetItem(parent, [label])
        item.setData(0, Qt.ItemDataRole.UserRole,     entry)
        item.setData(0, Qt.ItemDataRole.UserRole + 1, _TYPE_ENTRY)
        return item

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _on_search(self, query: str) -> None:
        if not query.strip():
            self._rebuild_tree()
            return
        q = query.lower()
        self._tree.clear()
        if not keepass_manager.is_open:
            return
        for entry in keepass_manager.get_all_entries():
            if (
                q in (entry.title    or "").lower()
                or q in (entry.username or "").lower()
                or q in (entry.url      or "").lower()
                or (entry.group and q in (entry.group.name or "").lower())
            ):
                self._add_entry_item(self._tree.invisibleRootItem(), entry)

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _on_context_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        if item is None:
            return
        if item.data(0, Qt.ItemDataRole.UserRole + 1) != _TYPE_ENTRY:
            return
        entry = item.data(0, Qt.ItemDataRole.UserRole)
        if entry is None:
            return

        menu = QMenu(self)
        menu.addAction(
            f"Copy &Username  (Ctrl+U)",
            lambda: self._copy_entry_field(entry, "username"),
        )
        menu.addAction(
            f"Copy &Password  (Ctrl+P)",
            lambda: self._copy_entry_field(entry, "password"),
        )
        menu.addAction(
            "Copy &URL",
            lambda: self._copy_entry_field(entry, "url"),
        )
        menu.addSeparator()
        menu.addAction("SSH &Auto-fill", lambda: self._do_autofill(entry))
        menu.addSeparator()
        menu.addAction("&Edit Entry…",  lambda: self._edit_entry(entry))
        menu.addAction("&Delete Entry", lambda: self._delete_entry(entry))
        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _on_double_click(self, item: QTreeWidgetItem, _col: int) -> None:
        if item.data(0, Qt.ItemDataRole.UserRole + 1) == _TYPE_ENTRY:
            entry = item.data(0, Qt.ItemDataRole.UserRole)
            if entry:
                self._copy_entry_field(entry, "password")

    # ------------------------------------------------------------------
    # Clipboard helpers
    # ------------------------------------------------------------------

    def _selected_entry(self):
        item = self._tree.currentItem()
        if item is None:
            return None
        if item.data(0, Qt.ItemDataRole.UserRole + 1) != _TYPE_ENTRY:
            return None
        return item.data(0, Qt.ItemDataRole.UserRole)

    def _copy_username(self) -> None:
        entry = self._selected_entry()
        if entry:
            self._copy_entry_field(entry, "username")

    def _copy_password(self) -> None:
        entry = self._selected_entry()
        if entry:
            self._copy_entry_field(entry, "password")

    def _copy_entry_field(self, entry, field: str) -> None:
        value = getattr(entry, field, "") or ""
        QApplication.clipboard().setText(value)
        label_map = {"username": "Username", "password": "Password", "url": "URL"}
        label = label_map.get(field, field.title())
        timeout_s: int = settings_manager.get("clipboard_clear_timeout_s", 15)
        if timeout_s > 0:
            self._status(f"{label} copied — clipboard clears in {timeout_s}s")
            self._clipboard_timer.stop()
            self._clipboard_timer.start(timeout_s * 1000)
            log.debug("Clipboard set (%s); auto-clear in %ds", label, timeout_s)
        else:
            self._status(f"{label} copied to clipboard.")
            log.debug("Clipboard set (%s); auto-clear disabled", label)

    def _clear_clipboard(self) -> None:
        QApplication.clipboard().clear()
        self._status("Clipboard cleared.")
        log.debug("Clipboard auto-cleared by timer")

    def _do_autofill(self, entry) -> None:
        self.autofill_requested.emit(entry.username or "", entry.password or "")
        log.debug("SSH auto-fill requested for entry: %s", entry.title)

    # ------------------------------------------------------------------
    # Entry CRUD
    # ------------------------------------------------------------------

    def _edit_entry(self, entry) -> None:
        from app.dialogs.keepass_editor import KeePassEntryDialog  # noqa: PLC0415
        dlg = KeePassEntryDialog(self, entry=entry)
        if dlg.exec():
            self.refresh()
            self._status("Entry updated.")

    def _delete_entry(self, entry) -> None:
        reply = QMessageBox.question(
            self,
            "Delete Entry",
            f"Delete entry '{entry.title or '(no title)'}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            ok = keepass_manager.delete_entry(str(entry.uuid))
            if ok:
                self.refresh()
                self._status("Entry deleted.")
            else:
                QMessageBox.critical(self, "Error", "Could not delete entry.")

    # ------------------------------------------------------------------
    # Close active database
    # ------------------------------------------------------------------

    def _close_active_db(self) -> None:
        path = keepass_manager.db_path
        if not path:
            return
        name = pathlib.Path(path).name
        reply = QMessageBox.question(
            self,
            "Close Database",
            f"Close '{name}'?\nUnsaved changes will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            keepass_manager.close_db(path)
            self.refresh()
            self._status(f"'{name}' closed.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _status(self, msg: str) -> None:
        self._status_lbl.setText(f"  {msg}")
