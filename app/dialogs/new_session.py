"""Dialog for creating or editing an SSH session."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.models import SSHSessionConfig
from app.managers.keepass import keepass_manager


class NewSessionDialog(QDialog):
    """Create or edit an SSH session configuration."""

    def __init__(
        self,
        parent=None,
        session: Optional[SSHSessionConfig] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("New SSH Session" if session is None else "Edit Session")
        self.setMinimumWidth(480)
        self._session = session
        self._kp_uuid: str = session.keepass_entry_uuid if session else ""
        self.result_session: Optional[SSHSessionConfig] = None
        self._build_ui()
        if session:
            self._populate(session)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.setContentsMargins(20, 20, 20, 20)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("My Server")
        form.addRow("Session Name", self._name_edit)

        self._host_edit = QLineEdit()
        self._host_edit.setPlaceholderText("192.168.1.1 or hostname")
        form.addRow("Hostname / IP", self._host_edit)

        self._port_edit = QLineEdit("22")
        self._port_edit.setFixedWidth(80)
        form.addRow("Port", self._port_edit)

        self._user_edit = QLineEdit()
        self._user_edit.setPlaceholderText("admin")
        form.addRow("Username", self._user_edit)

        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText("e.g. Production  (optional)")
        form.addRow("Folder", self._folder_edit)

        # Private key row
        key_row = QHBoxLayout()
        self._key_edit = QLineEdit()
        self._key_edit.setPlaceholderText("~/.ssh/id_rsa  (leave blank to use password)")
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_key)
        key_row.addWidget(self._key_edit)
        key_row.addWidget(browse_btn)
        form.addRow("Private Key", key_row)

        root.addLayout(form)

        # KeePass credential group
        kp_grp = QGroupBox("KeePass Credential")
        kp_layout = QHBoxLayout(kp_grp)
        self._kp_label = QLabel("None")
        self._kp_label.setObjectName("kp-entry")
        kp_layout.addWidget(self._kp_label, 1)
        sel_btn = QPushButton("Select Entry…")
        sel_btn.clicked.connect(self._select_kp)
        clr_btn = QPushButton("Clear")
        clr_btn.clicked.connect(self._clear_kp)
        kp_layout.addWidget(sel_btn)
        kp_layout.addWidget(clr_btn)
        root.addWidget(kp_grp)

        # Dialog buttons
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        save_btn = btns.button(QDialogButtonBox.StandardButton.Save)
        save_btn.setObjectName("primary")
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------

    def _populate(self, s: SSHSessionConfig) -> None:
        self._name_edit.setText(s.name)
        self._host_edit.setText(s.hostname)
        self._port_edit.setText(str(s.port))
        self._user_edit.setText(s.username)
        self._key_edit.setText(s.key_path)
        self._folder_edit.setText(s.folder)
        if s.keepass_entry_uuid:
            entry = keepass_manager.get_entry_by_uuid(s.keepass_entry_uuid)
            self._kp_label.setText(
                entry.title if entry else f"UUID: {s.keepass_entry_uuid[:8]}…"
            )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _browse_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Private Key", "", "All files (*)"
        )
        if path:
            self._key_edit.setText(path)

    def _select_kp(self) -> None:
        if not keepass_manager.is_open:
            QMessageBox.warning(
                self,
                "KeePass",
                "No KeePass database is open.\n"
                "Open one via  Tools → Open KeePass Database…",
            )
            return
        from app.dialogs.keepass_selector import KeePassSelectorDialog

        dlg = KeePassSelectorDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_entry is not None:
            self._kp_uuid = str(dlg.selected_entry.uuid)
            self._kp_label.setText(dlg.selected_entry.title or "Unknown")

    def _clear_kp(self) -> None:
        self._kp_uuid = ""
        self._kp_label.setText("None")

    def _save(self) -> None:
        name = self._name_edit.text().strip()
        host = self._host_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Session name is required.")
            return
        if not host:
            QMessageBox.warning(self, "Validation", "Hostname is required.")
            return
        try:
            port = int(self._port_edit.text())
        except ValueError:
            QMessageBox.warning(self, "Validation", "Port must be a number.")
            return

        if self._session:
            self._session.name = name
            self._session.hostname = host
            self._session.port = port
            self._session.username = self._user_edit.text().strip()
            self._session.key_path = self._key_edit.text().strip()
            self._session.folder = self._folder_edit.text().strip()
            self._session.keepass_entry_uuid = self._kp_uuid
            self.result_session = self._session
        else:
            self.result_session = SSHSessionConfig(
                name=name,
                hostname=host,
                port=port,
                username=self._user_edit.text().strip(),
                key_path=self._key_edit.text().strip(),
                folder=self._folder_edit.text().strip(),
                keepass_entry_uuid=self._kp_uuid,
            )
        self.accept()
