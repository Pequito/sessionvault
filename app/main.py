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
from app.managers.logger import get_logger
from app.importers.mobaxterm import MobaXtermImporter
from app.terminal.widget import SSHTerminalWidget
from app.theme import apply_theme, stylesheet
from app.plugins.loader import plugin_loader

log = get_logger(__name__)


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
        self._kp_panel.refresh()
        self._apply_saved_settings()
        self._load_plugins()
        self._start_browser_server()
        log.info("%s %s started", APP_NAME, APP_VERSION)

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
                log.info("Plugins loaded: %s", ", ".join(loaded))
            self._rebuild_plugin_menu()

    def _start_browser_server(self) -> None:
        if not settings_manager.get("browser_integration", False):
            return
        from app.browser.server import browser_server  # noqa: PLC0415
        port = settings_manager.get("browser_port", 19456)
        try:
            browser_server.start(port)
            self._status(f"Browser integration active on port {port}.")
        except OSError as exc:
            log.error("Browser server failed to start: %s", exc)
            self._status(f"Browser server error: {exc}")

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

        # ── App title ─────────────────────────────────────────────────
        title = QLabel(APP_NAME)
        title.setStyleSheet(
            f"background-color: {C['crust']}; color: {C['mauve']};"
            f"font-size: 13pt; font-weight: bold; padding: 8px 12px;"
        )
        layout.addWidget(title)

        # ── Sessions header ───────────────────────────────────────────
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

        # ── Session tree ──────────────────────────────────────────────
        self._sess_tree = QTreeWidget()
        self._sess_tree.setHeaderHidden(True)
        self._sess_tree.setRootIsDecorated(True)
        self._sess_tree.setIndentation(16)
        self._sess_tree.itemDoubleClicked.connect(self._on_tree_double_click)
        self._sess_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._sess_tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        layout.addWidget(self._sess_tree, 3)

        # ── KeePass header ────────────────────────────────────────────
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

        # ── KeePass hierarchical panel ────────────────────────────────
        from app.keepass.panel import KeePassPanel  # noqa: PLC0415
        self._kp_panel = KeePassPanel(sidebar)
        self._kp_panel.open_db_requested.connect(self._open_keepass)
        self._kp_panel.autofill_requested.connect(self._autofill_terminal)
        layout.addWidget(self._kp_panel, 2)

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
        tools_m.addSeparator()
        act_lock_kp = tools_m.addAction("Lock &Active Database")
        act_lock_kp.triggered.connect(self._lock_active_keepass)
        act_lock_all = tools_m.addAction("Lock &All Databases")
        act_lock_all.triggered.connect(self._lock_all_keepass)
        tools_m.addSeparator()
        act_new_entry = tools_m.addAction("Add KeePass &Entry…")
        act_new_entry.triggered.connect(self._new_kp_entry)
        tools_m.addSeparator()
        act_browser = tools_m.addAction("&Browser Integration…")
        act_browser.triggered.connect(self._open_browser_settings)

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
        menu.addAction("Connect",  lambda: self._connect(session))
        menu.addAction("Edit…",    lambda: self._edit_session(session))
        menu.addSeparator()
        menu.addAction("Delete",   lambda: self._delete_session(session))
        menu.exec(self._sess_tree.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Session CRUD
    # ------------------------------------------------------------------

    def _new_session(self) -> None:
        from app.dialogs.new_session import NewSessionDialog  # noqa: PLC0415
        dlg = NewSessionDialog(self)
        if dlg.exec() and dlg.result_session:
            self._session_mgr.add(dlg.result_session)
            self._refresh_session_tree()
            self._status(f"Session '{dlg.result_session.name}' created.")
            log.info("Session created: %s", dlg.result_session.name)

    def _edit_session(self, session: SSHSessionConfig) -> None:
        from app.dialogs.new_session import NewSessionDialog  # noqa: PLC0415
        dlg = NewSessionDialog(self, session=session)
        if dlg.exec() and dlg.result_session:
            self._session_mgr.update(dlg.result_session)
            self._refresh_session_tree()
            self._status(f"Session '{session.name}' updated.")
            log.info("Session updated: %s", session.name)

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
            log.info("Session deleted: %s", session.name)

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
        log.info("Connecting to session: %s (%s)", session.name, session.protocol)

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
        from app.dialogs.keepass_open import KeePassOpenDialog  # noqa: PLC0415
        dlg = KeePassOpenDialog(self)
        if dlg.exec():
            self._kp_panel.refresh()
            name = pathlib.Path(keepass_manager.db_path).name
            self._status(f"KeePass '{name}' opened.")
            log.info("KeePass database opened via dialog: %s", name)

    def _new_keepass(self) -> None:
        if not PYKEEPASS_AVAILABLE:
            QMessageBox.critical(
                self, "Missing Dependency",
                "pykeepass is not installed.\nRun: pip install pykeepass",
            )
            return
        from app.dialogs.keepass_editor import KeePassNewDatabaseDialog  # noqa: PLC0415
        dlg = KeePassNewDatabaseDialog(self)
        if dlg.exec():
            self._kp_panel.refresh()
            name = pathlib.Path(keepass_manager.db_path).name
            self._status(f"New KeePass database '{name}' created.")
            log.info("New KeePass database created: %s", name)

    def _lock_active_keepass(self) -> None:
        path = keepass_manager.db_path
        if not path:
            self._status("No active KeePass database.")
            return
        name = pathlib.Path(path).name
        keepass_manager.close_db(path)
        self._kp_panel.refresh()
        self._status(f"KeePass '{name}' locked.")
        log.info("KeePass database locked: %s", path)

    def _lock_all_keepass(self) -> None:
        count = len(keepass_manager.open_paths)
        keepass_manager.lock()
        self._kp_panel.refresh()
        self._status(f"All KeePass databases locked ({count} db(s) cleared).")
        log.info("All KeePass databases locked")

    def _new_kp_entry(self) -> None:
        if not keepass_manager.is_open:
            QMessageBox.warning(self, "KeePass", "Open a KeePass database first.")
            return
        from app.dialogs.keepass_editor import KeePassEntryDialog  # noqa: PLC0415
        dlg = KeePassEntryDialog(self)
        if dlg.exec():
            self._kp_panel.refresh()
            self._status("KeePass entry added.")

    # ------------------------------------------------------------------
    # Terminal auto-fill  (from KeePass panel signal)
    # ------------------------------------------------------------------

    def _autofill_terminal(self, username: str, password: str) -> None:
        """Paste KeePass credentials into the currently active terminal tab."""
        widget = self._tabs.currentWidget()
        if isinstance(widget, SSHTerminalWidget):
            if username:
                widget.send_input(username)
            if password:
                widget.send_input(password)
            log.debug("KeePass auto-fill sent to active terminal")
        else:
            self._status("No active terminal for auto-fill.")

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
            log.error("MobaXterm import error: %s", exc)
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
            log.info("MobaXterm import: %d sessions added", added)

    # ------------------------------------------------------------------
    # Macros
    # ------------------------------------------------------------------

    def _open_macro_manager(self) -> None:
        from app.macros.dialog import MacroManagerDialog  # noqa: PLC0415
        dlg = MacroManagerDialog(self)
        dlg.exec()

    # ------------------------------------------------------------------
    # Browser integration
    # ------------------------------------------------------------------

    def _open_browser_settings(self) -> None:
        """Open Settings dialog pre-navigated to the Browser tab."""
        from app.dialogs.settings import SettingsDialog  # noqa: PLC0415
        dlg = SettingsDialog(self)
        # Browser tab is index 4 (Appearance=0 Terminal=1 AutoType=2 KeePass=3 Browser=4)
        dlg.findChild(__import__("PySide6.QtWidgets", fromlist=["QTabWidget"]).QTabWidget
                      ).setCurrentIndex(4)
        if dlg.exec():
            icon_path = settings_manager.get("app_icon", "")
            if icon_path:
                self.setWindowIcon(QIcon(icon_path))
            self._rebuild_plugin_menu()

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _open_settings(self) -> None:
        from app.dialogs.settings import SettingsDialog  # noqa: PLC0415
        dlg = SettingsDialog(self)
        if dlg.exec():
            icon_path = settings_manager.get("app_icon", "")
            if icon_path:
                self.setWindowIcon(QIcon(icon_path))
            self._rebuild_plugin_menu()

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        from app.browser.server import browser_server  # noqa: PLC0415
        browser_server.stop()
        log.info("%s shutting down", APP_NAME)
        super().closeEvent(event)

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
