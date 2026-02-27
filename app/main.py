"""Main application window (QMainWindow) and ``main()`` entry point."""

from __future__ import annotations

import pathlib
import sys
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.constants import APP_NAME, APP_VERSION, C
from app.models import SSHSessionConfig
from app.managers.keepass import keepass_manager, PYKEEPASS_AVAILABLE
from app.managers.session import SessionManager
from app.managers.settings import settings_manager
from app.importers.mobaxterm import MobaXtermImporter
from app.terminal.widget import SSHTerminalWidget
from app.theme import apply_theme, stylesheet
from app.plugins.loader import plugin_loader


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class SessionVaultApp(QMainWindow):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME}  {APP_VERSION}")
        self.resize(1280, 800)
        self.setMinimumSize(800, 500)

        self._session_mgr = SessionManager()
        self._terminals: dict[str, SSHTerminalWidget] = {}  # session_id → widget

        self._build_ui()
        self._build_menu()
        self._refresh_session_tree()
        self._refresh_kp_panel()
        self._apply_saved_settings()
        self._load_plugins()

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    def _apply_saved_settings(self) -> None:
        theme = settings_manager.get("theme", "Catppuccin Mocha")
        apply_theme(theme)
        icon_path = settings_manager.get("app_icon", "")
        if icon_path:
            QApplication.instance().setWindowIcon(QIcon(icon_path))

    def _load_plugins(self) -> None:
        if settings_manager.get("plugins_enabled", True):
            loaded = plugin_loader.load_all()
            if loaded:
                self._status(f"Plugins loaded: {', '.join(loaded)}")
            # Rebuild plugins menu (populated after load_all)
            self._rebuild_plugin_menu()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        h_layout = QHBoxLayout(central)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        h_layout.addWidget(splitter)

        splitter.addWidget(self._build_sidebar())
        splitter.addWidget(self._build_terminal_area())
        splitter.setSizes([240, 1040])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        self._status_lbl = QLabel(f"{APP_NAME} ready.")
        sb = QStatusBar()
        sb.addWidget(self._status_lbl)
        self.setStatusBar(sb)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFrameShape(QFrame.Shape.NoFrame)
        sidebar.setFixedWidth(240)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel(APP_NAME)
        title.setStyleSheet(
            f"background-color: {C['crust']}; color: {C['mauve']};"
            f"font-size: 13pt; font-weight: bold; padding: 8px 12px;"
        )
        layout.addWidget(title)

        sess_hdr = QFrame()
        sess_hdr.setStyleSheet(f"background-color: {C['surface0']};")
        sh = QHBoxLayout(sess_hdr)
        sh.setContentsMargins(8, 3, 6, 3)
        sh_lbl = QLabel("SESSIONS")
        sh_lbl.setStyleSheet(
            f"background: transparent; color: {C['overlay1']};"
            f"font-size: 8pt; font-weight: bold; letter-spacing: 1px;"
        )
        sh.addWidget(sh_lbl)
        sh.addStretch()
        add_btn = QPushButton("+")
        add_btn.setToolTip("New Session  (Ctrl+T)")
        add_btn.setFixedSize(24, 20)
        add_btn.setStyleSheet(
            f"background: transparent; color: {C['green']};"
            f"font-size: 14pt; font-weight: bold; border: none;"
        )
        add_btn.clicked.connect(self._new_session)
        sh.addWidget(add_btn)
        layout.addWidget(sess_hdr)

        self._sess_tree = QTreeWidget()
        self._sess_tree.setHeaderHidden(True)
        self._sess_tree.setRootIsDecorated(True)
        self._sess_tree.setIndentation(16)
        self._sess_tree.itemDoubleClicked.connect(self._on_tree_double_click)
        self._sess_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._sess_tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        layout.addWidget(self._sess_tree, 3)

        kp_hdr = QFrame()
        kp_hdr.setStyleSheet(f"background-color: {C['surface0']};")
        kh = QHBoxLayout(kp_hdr)
        kh.setContentsMargins(8, 3, 6, 3)
        kh_lbl = QLabel("KEEPASS")
        kh_lbl.setStyleSheet(
            f"background: transparent; color: {C['overlay1']};"
            f"font-size: 8pt; font-weight: bold; letter-spacing: 1px;"
        )
        kh.addWidget(kh_lbl)
        layout.addWidget(kp_hdr)

        from PySide6.QtWidgets import QListWidget
        self._kp_list = QListWidget()
        self._kp_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._kp_list.customContextMenuRequested.connect(self._on_kp_context_menu)
        layout.addWidget(self._kp_list, 2)

        return sidebar

    def _build_terminal_area(self) -> QWidget:
        frame = QWidget()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.tabCloseRequested.connect(self._close_tab)
        layout.addWidget(self._tabs)

        return frame

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        bar = self.menuBar()

        # ── File ────────────────────────────────────────────────────────
        file_m = bar.addMenu("&File")
        act_new = file_m.addAction("&New Session")
        act_new.setShortcut(QKeySequence("Ctrl+T"))
        act_new.triggered.connect(self._new_session)
        act_imp = file_m.addAction("&Import MobaXterm Sessions…")
        act_imp.triggered.connect(self._import_mobaxterm)
        file_m.addSeparator()
        act_quit = file_m.addAction("&Quit")
        act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        act_quit.triggered.connect(self.close)

        # ── Tools ───────────────────────────────────────────────────────
        tools_m = bar.addMenu("&Tools")
        act_open_kp = tools_m.addAction("&Open KeePass Database…")
        act_open_kp.triggered.connect(self._open_keepass)
        act_new_kp = tools_m.addAction("&New KeePass Database…")
        act_new_kp.triggered.connect(self._new_keepass)
        act_lock_kp = tools_m.addAction("&Lock KeePass Database")
        act_lock_kp.triggered.connect(self._lock_keepass)
        tools_m.addSeparator()
        act_new_entry = tools_m.addAction("Add KeePass &Entry…")
        act_new_entry.triggered.connect(self._new_kp_entry)
        act_del_entry = tools_m.addAction("&Delete Selected Entry")
        act_del_entry.triggered.connect(self._delete_kp_entry)

        # ── Macros ──────────────────────────────────────────────────────
        macros_m = bar.addMenu("&Macros")
        act_macro_mgr = macros_m.addAction("Macro &Manager…")
        act_macro_mgr.triggered.connect(self._open_macro_manager)

        # ── Plugins ─────────────────────────────────────────────────────
        self._plugins_menu = bar.addMenu("&Plugins")
        self._rebuild_plugin_menu()

        # ── Settings ────────────────────────────────────────────────────
        settings_m = bar.addMenu("&Settings")
        act_settings = settings_m.addAction("&Preferences…")
        act_settings.setShortcut(QKeySequence("Ctrl+,"))
        act_settings.triggered.connect(self._open_settings)

    def _rebuild_plugin_menu(self) -> None:
        self._plugins_menu.clear()
        for label, callback in plugin_loader.api.menu_actions:
            self._plugins_menu.addAction(label, callback)
        if not self._plugins_menu.actions():
            placeholder = self._plugins_menu.addAction("(no plugins loaded)")
            placeholder.setEnabled(False)

    # ------------------------------------------------------------------
    # Session tree
    # ------------------------------------------------------------------

    _PROTO_ICONS = {"ssh": "⚡", "rdp": "🖥", "vnc": "📺", "telnet": "⌨"}

    def _refresh_session_tree(self) -> None:
        self._sess_tree.clear()
        folder_items: dict[str, QTreeWidgetItem] = {}
        for s in self._session_mgr.all():
            if s.folder:
                if s.folder not in folder_items:
                    fi = QTreeWidgetItem(self._sess_tree, [f"\U0001F4C1  {s.folder}"])
                    fi.setExpanded(True)
                    folder_items[s.folder] = fi
                parent: QTreeWidgetItem = folder_items[s.folder]
            else:
                parent = self._sess_tree.invisibleRootItem()
            icon = self._PROTO_ICONS.get(s.protocol, "•")
            item = QTreeWidgetItem(parent, [f"  {icon}  {s.name}"])
            item.setData(0, Qt.ItemDataRole.UserRole, s.id)

    def _item_session(self, item: QTreeWidgetItem) -> Optional[SSHSessionConfig]:
        sid = item.data(0, Qt.ItemDataRole.UserRole)
        return self._session_mgr.get_by_id(sid) if sid else None

    def _on_tree_double_click(self, item: QTreeWidgetItem, _col: int) -> None:
        session = self._item_session(item)
        if session:
            self._connect(session)

    def _on_tree_context_menu(self, pos) -> None:
        item = self._sess_tree.itemAt(pos)
        if item is None:
            return
        session = self._item_session(item)
        if session is None:
            return
        menu = QMenu(self)
        menu.addAction("Connect", lambda: self._connect(session))
        menu.addAction("Edit…", lambda: self._edit_session(session))
        menu.addSeparator()
        menu.addAction("Delete", lambda: self._delete_session(session))
        menu.exec(self._sess_tree.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Session CRUD
    # ------------------------------------------------------------------

    def _new_session(self) -> None:
        from app.dialogs.new_session import NewSessionDialog
        dlg = NewSessionDialog(self)
        if dlg.exec() and dlg.result_session:
            self._session_mgr.add(dlg.result_session)
            self._refresh_session_tree()
            self._status(f"Session '{dlg.result_session.name}' created.")

    def _edit_session(self, session: SSHSessionConfig) -> None:
        from app.dialogs.new_session import NewSessionDialog
        dlg = NewSessionDialog(self, session=session)
        if dlg.exec() and dlg.result_session:
            self._session_mgr.update(dlg.result_session)
            self._refresh_session_tree()
            self._status(f"Session '{session.name}' updated.")

    def _delete_session(self, session: SSHSessionConfig) -> None:
        reply = QMessageBox.question(
            self,
            "Delete Session",
            f"Delete session '{session.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._session_mgr.delete(session.id)
            self._refresh_session_tree()
            self._status(f"Session '{session.name}' deleted.")

    def _connect(self, session: SSHSessionConfig) -> None:
        if session.id in self._terminals:
            for i in range(self._tabs.count()):
                if self._tabs.widget(i) is self._terminals[session.id]:
                    self._tabs.setCurrentIndex(i)
                    return

        password: Optional[str] = None
        if session.keepass_entry_uuid:
            if keepass_manager.is_open:
                password = keepass_manager.get_password_for_session(session)
            else:
                reply = QMessageBox.question(
                    self,
                    "KeePass Locked",
                    "This session uses a KeePass entry but no database is open.\n"
                    "Open KeePass database now?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self._open_keepass()
                    password = keepass_manager.get_password_for_session(session)

        if password is None and not session.key_path and session.protocol == "ssh":
            pw, ok = QInputDialog.getText(
                self,
                "Password",
                f"Password for {session.username}@{session.hostname}:",
                QLineEdit.EchoMode.Password,
            )
            if ok:
                password = pw

        widget = SSHTerminalWidget(session, password=password, parent=self._tabs)
        self._terminals[session.id] = widget
        idx = self._tabs.addTab(widget, session.name)
        self._tabs.setCurrentIndex(idx)
        self._status(f"Connecting to {session.name}…")

        # Fire plugin connect hooks
        plugin_loader.api.fire_connect(session)

    # ------------------------------------------------------------------
    # Tab management
    # ------------------------------------------------------------------

    def _close_tab(self, index: int) -> None:
        widget = self._tabs.widget(index)
        if isinstance(widget, SSHTerminalWidget):
            widget.close_connection()
            for sid, w in list(self._terminals.items()):
                if w is widget:
                    del self._terminals[sid]
                    break
        self._tabs.removeTab(index)

    # ------------------------------------------------------------------
    # KeePass
    # ------------------------------------------------------------------

    def _open_keepass(self) -> None:
        if not PYKEEPASS_AVAILABLE:
            QMessageBox.critical(
                self, "Missing Dependency",
                "pykeepass is not installed.\nRun: pip install pykeepass",
            )
            return
        from app.dialogs.keepass_open import KeePassOpenDialog
        dlg = KeePassOpenDialog(self)
        if dlg.exec():
            self._refresh_kp_panel()
            name = pathlib.Path(keepass_manager.db_path).name
            self._status(f"KeePass '{name}' opened.")

    def _new_keepass(self) -> None:
        if not PYKEEPASS_AVAILABLE:
            QMessageBox.critical(
                self, "Missing Dependency",
                "pykeepass is not installed.\nRun: pip install pykeepass",
            )
            return
        from app.dialogs.keepass_editor import KeePassNewDatabaseDialog
        dlg = KeePassNewDatabaseDialog(self)
        if dlg.exec():
            self._refresh_kp_panel()
            name = pathlib.Path(keepass_manager.db_path).name
            self._status(f"New KeePass database '{name}' created and opened.")

    def _lock_keepass(self) -> None:
        keepass_manager.lock()
        self._refresh_kp_panel()
        self._status("KeePass database locked.")

    def _new_kp_entry(self) -> None:
        if not keepass_manager.is_open:
            QMessageBox.warning(
                self, "KeePass", "Open a KeePass database first."
            )
            return
        from app.dialogs.keepass_editor import KeePassEntryDialog
        dlg = KeePassEntryDialog(self)
        if dlg.exec():
            self._refresh_kp_panel()
            self._status("KeePass entry added.")

    def _delete_kp_entry(self) -> None:
        row = self._kp_list.currentRow()
        entries = getattr(self, "_kp_entries", [])
        if row < 0 or row >= len(entries):
            return
        entry = entries[row]
        reply = QMessageBox.question(
            self,
            "Delete Entry",
            f"Delete entry '{entry.title or '(no title)'}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            ok = keepass_manager.delete_entry(str(entry.uuid))
            if ok:
                self._refresh_kp_panel()
                self._status("Entry deleted.")
            else:
                QMessageBox.critical(self, "Error", "Could not delete entry.")

    def _refresh_kp_panel(self) -> None:
        self._kp_list.clear()
        self._kp_entries: list = []
        if not keepass_manager.is_open:
            self._kp_list.addItem("  (no database open)")
            return
        self._kp_entries = keepass_manager.get_all_entries()
        for e in self._kp_entries:
            label = f"  {e.title or '(no title)'}"
            if e.username:
                label += f"   [{e.username}]"
            self._kp_list.addItem(label)

    def _on_kp_context_menu(self, pos) -> None:
        item = self._kp_list.itemAt(pos)
        if item is None:
            return
        idx = self._kp_list.row(item)
        entries = getattr(self, "_kp_entries", [])
        if idx >= len(entries):
            return
        entry = entries[idx]
        menu = QMenu(self)
        menu.addAction("Copy Username", lambda: self._clipboard(entry.username or ""))
        menu.addAction("Copy Password", lambda: self._clipboard(entry.password or ""))
        menu.addAction("Copy URL", lambda: self._clipboard(entry.url or ""))
        menu.addSeparator()
        menu.addAction("Edit Entry…", lambda: self._edit_kp_entry(entry))
        menu.addAction("Delete Entry", lambda: self._delete_kp_entry_direct(entry))
        menu.exec(self._kp_list.viewport().mapToGlobal(pos))

    def _edit_kp_entry(self, entry) -> None:
        from app.dialogs.keepass_editor import KeePassEntryDialog
        dlg = KeePassEntryDialog(self, entry=entry)
        if dlg.exec():
            self._refresh_kp_panel()
            self._status("KeePass entry updated.")

    def _delete_kp_entry_direct(self, entry) -> None:
        reply = QMessageBox.question(
            self,
            "Delete Entry",
            f"Delete entry '{entry.title or '(no title)'}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            keepass_manager.delete_entry(str(entry.uuid))
            self._refresh_kp_panel()

    # ------------------------------------------------------------------
    # MobaXterm import
    # ------------------------------------------------------------------

    def _import_mobaxterm(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import MobaXterm Sessions",
            "",
            "MobaXterm sessions (*.mxtsessions);;All files (*)",
        )
        if not path:
            return
        try:
            sessions = MobaXtermImporter.parse_file(path)
        except Exception as exc:
            QMessageBox.critical(self, "Import Error", str(exc))
            return

        if not sessions:
            QMessageBox.information(self, "Import", "No SSH sessions found in the file.")
            return

        preview = "\n".join(
            f"  {s.name}  →  {s.username}@{s.hostname}:{s.port}"
            for s in sessions[:20]
        )
        if len(sessions) > 20:
            preview += f"\n  … and {len(sessions) - 20} more"

        reply = QMessageBox.question(
            self,
            "Import Sessions",
            f"Found {len(sessions)} SSH session(s):\n\n{preview}\n\nImport all?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            added = self._session_mgr.import_sessions(sessions)
            self._refresh_session_tree()
            self._status(f"Imported {added} new session(s) from MobaXterm.")

    # ------------------------------------------------------------------
    # Macros
    # ------------------------------------------------------------------

    def _open_macro_manager(self) -> None:
        from app.macros.dialog import MacroManagerDialog
        dlg = MacroManagerDialog(self)
        dlg.exec()

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _open_settings(self) -> None:
        from app.dialogs.settings import SettingsDialog
        dlg = SettingsDialog(self)
        if dlg.exec():
            # Re-apply icon in case it changed
            icon_path = settings_manager.get("app_icon", "")
            if icon_path:
                self.setWindowIcon(QIcon(icon_path))
            self._rebuild_plugin_menu()

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _clipboard(self, text: str) -> None:
        QApplication.clipboard().setText(text)
        self._status("Copied to clipboard.")

    def _status(self, msg: str) -> None:
        self._status_lbl.setText(msg)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyleSheet(stylesheet())
    window = SessionVaultApp()
    window.show()
    sys.exit(app.exec())
