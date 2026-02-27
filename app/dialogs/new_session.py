"""Dialog for creating or editing a session (SSH / RDP / VNC / Telnet)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
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
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.models import SSHSessionConfig, TunnelConfig
from app.managers.keepass import keepass_manager


class NewSessionDialog(QDialog):
    """Create or edit a session configuration of any supported protocol."""

    _PROTOCOLS = ["ssh", "rdp", "vnc", "telnet"]
    _DEFAULT_PORTS = {"ssh": 22, "rdp": 3389, "vnc": 5900, "telnet": 23}

    def __init__(
        self,
        parent=None,
        session: Optional[SSHSessionConfig] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Session" if session is None else "Edit Session")
        self.setMinimumWidth(540)
        self._session = session
        self._kp_uuid: str = session.keepass_entry_uuid if session else ""
        self._tunnels: list[TunnelConfig] = (
            list(session.tunnels()) if session else []
        )
        self.result_session: Optional[SSHSessionConfig] = None
        self._build_ui()
        if session:
            self._populate(session)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(20, 20, 20, 20)

        tabs = QTabWidget()
        tabs.addTab(self._tab_general(), "General")
        tabs.addTab(self._tab_ssh(), "SSH Options")
        tabs.addTab(self._tab_rdp(), "RDP Options")
        root.addWidget(tabs)

        # KeePass credential
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

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Save).setObjectName("primary")
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    # ── General tab ────────────────────────────────────────────────────

    def _tab_general(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(10)
        form.setContentsMargins(12, 12, 12, 12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("My Server")
        form.addRow("Session Name", self._name_edit)

        self._proto_combo = QComboBox()
        for p in self._PROTOCOLS:
            self._proto_combo.addItem(p.upper(), p)
        self._proto_combo.currentIndexChanged.connect(self._on_proto_changed)
        form.addRow("Protocol", self._proto_combo)

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

        key_row = QHBoxLayout()
        self._key_edit = QLineEdit()
        self._key_edit.setPlaceholderText(
            "~/.ssh/id_rsa  (SSH only – leave blank for password)"
        )
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_key)
        key_row.addWidget(self._key_edit)
        key_row.addWidget(browse_btn)
        form.addRow("Private Key", key_row)

        return w

    # ── SSH Options tab ────────────────────────────────────────────────

    def _tab_ssh(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        self._x11_chk = QCheckBox(
            "Enable X11 forwarding  (requires local X11 server on Linux/macOS)"
        )
        layout.addWidget(self._x11_chk)

        tun_grp = QGroupBox("Local Port Forwarding (SSH Tunnels)")
        tun_v = QVBoxLayout(tun_grp)

        self._tunnel_list = QListWidget()
        tun_v.addWidget(self._tunnel_list)

        tun_btns = QHBoxLayout()
        add_tun = QPushButton("+ Add Tunnel")
        add_tun.clicked.connect(self._add_tunnel)
        tun_btns.addWidget(add_tun)
        rem_tun = QPushButton("Remove")
        rem_tun.setObjectName("danger")
        rem_tun.clicked.connect(self._remove_tunnel)
        tun_btns.addWidget(rem_tun)
        tun_btns.addStretch()
        tun_v.addLayout(tun_btns)

        hint = QLabel(
            "Example: local 5432 → db.internal:5432  (PostgreSQL via SSH)"
        )
        hint.setWordWrap(True)
        tun_v.addWidget(hint)

        layout.addWidget(tun_grp)
        layout.addStretch()
        return w

    # ── RDP Options tab ────────────────────────────────────────────────

    def _tab_rdp(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(10)
        form.setContentsMargins(12, 12, 12, 12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        res_row = QHBoxLayout()
        self._rdp_w_spin = QSpinBox()
        self._rdp_w_spin.setRange(640, 7680)
        self._rdp_w_spin.setValue(1280)
        self._rdp_w_spin.setSuffix("  px")
        self._rdp_h_spin = QSpinBox()
        self._rdp_h_spin.setRange(480, 4320)
        self._rdp_h_spin.setValue(800)
        self._rdp_h_spin.setSuffix("  px")
        res_row.addWidget(self._rdp_w_spin)
        res_row.addWidget(QLabel("×"))
        res_row.addWidget(self._rdp_h_spin)
        res_row.addStretch()
        form.addRow("Resolution", res_row)

        self._rdp_full_chk = QCheckBox("Full-screen mode")
        form.addRow("", self._rdp_full_chk)

        note = QLabel(
            "RDP sessions launch xfreerdp (Linux/macOS) or mstsc (Windows).\n"
            "VNC sessions launch vncviewer.  Ensure the client is installed."
        )
        note.setWordWrap(True)
        form.addRow("", note)
        return w

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------

    def _populate(self, s: SSHSessionConfig) -> None:
        self._name_edit.setText(s.name)
        idx = self._proto_combo.findData(s.protocol)
        if idx >= 0:
            self._proto_combo.setCurrentIndex(idx)
        self._host_edit.setText(s.hostname)
        self._port_edit.setText(str(s.port))
        self._user_edit.setText(s.username)
        self._key_edit.setText(s.key_path)
        self._folder_edit.setText(s.folder)
        self._x11_chk.setChecked(s.x11_forwarding)
        self._rdp_w_spin.setValue(s.rdp_width)
        self._rdp_h_spin.setValue(s.rdp_height)
        self._rdp_full_chk.setChecked(s.rdp_fullscreen)
        if s.keepass_entry_uuid:
            entry = keepass_manager.get_entry_by_uuid(s.keepass_entry_uuid)
            self._kp_label.setText(
                entry.title if entry else f"UUID: {s.keepass_entry_uuid[:8]}…"
            )
        self._refresh_tunnel_list()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_proto_changed(self, idx: int) -> None:
        proto = self._proto_combo.itemData(idx) or "ssh"
        default_port = self._DEFAULT_PORTS.get(proto, 22)
        try:
            current = int(self._port_edit.text())
        except ValueError:
            current = -1
        if current in self._DEFAULT_PORTS.values():
            self._port_edit.setText(str(default_port))

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

    def _refresh_tunnel_list(self) -> None:
        self._tunnel_list.clear()
        for t in self._tunnels:
            self._tunnel_list.addItem(QListWidgetItem(str(t)))

    def _add_tunnel(self) -> None:
        dlg = _TunnelDialog(self)
        if dlg.exec() and dlg.result:
            self._tunnels.append(dlg.result)
            self._refresh_tunnel_list()

    def _remove_tunnel(self) -> None:
        row = self._tunnel_list.currentRow()
        if 0 <= row < len(self._tunnels):
            del self._tunnels[row]
            self._refresh_tunnel_list()

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _save(self) -> None:
        name = self._name_edit.text().strip()
        host = self._host_edit.text().strip()
        proto = self._proto_combo.currentData() or "ssh"
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

        tunnels_dicts = [t.to_dict() for t in self._tunnels]

        if self._session:
            s = self._session
            s.name = name
            s.hostname = host
            s.port = port
            s.protocol = proto
            s.username = self._user_edit.text().strip()
            s.key_path = self._key_edit.text().strip()
            s.folder = self._folder_edit.text().strip()
            s.keepass_entry_uuid = self._kp_uuid
            s.x11_forwarding = self._x11_chk.isChecked()
            s.local_tunnels = tunnels_dicts
            s.rdp_width = self._rdp_w_spin.value()
            s.rdp_height = self._rdp_h_spin.value()
            s.rdp_fullscreen = self._rdp_full_chk.isChecked()
            self.result_session = s
        else:
            self.result_session = SSHSessionConfig(
                name=name,
                hostname=host,
                port=port,
                protocol=proto,
                username=self._user_edit.text().strip(),
                key_path=self._key_edit.text().strip(),
                folder=self._folder_edit.text().strip(),
                keepass_entry_uuid=self._kp_uuid,
                x11_forwarding=self._x11_chk.isChecked(),
                local_tunnels=tunnels_dicts,
                rdp_width=self._rdp_w_spin.value(),
                rdp_height=self._rdp_h_spin.value(),
                rdp_fullscreen=self._rdp_full_chk.isChecked(),
            )
        self.accept()


# ---------------------------------------------------------------------------
# Tunnel sub-dialog
# ---------------------------------------------------------------------------

class _TunnelDialog(QDialog):
    """Mini-dialog to define a single local-port-forward tunnel."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add SSH Tunnel")
        self.setMinimumWidth(360)
        self.result: Optional[TunnelConfig] = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._local_port = QSpinBox()
        self._local_port.setRange(1024, 65535)
        self._local_port.setValue(8080)
        form.addRow("Local port", self._local_port)

        self._remote_host = QLineEdit()
        self._remote_host.setPlaceholderText("remote-host or IP")
        form.addRow("Remote host", self._remote_host)

        self._remote_port = QSpinBox()
        self._remote_port.setRange(1, 65535)
        self._remote_port.setValue(80)
        form.addRow("Remote port", self._remote_port)

        root.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primary")
        btns.accepted.connect(self._ok)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    def _ok(self) -> None:
        rhost = self._remote_host.text().strip()
        if not rhost:
            QMessageBox.warning(self, "Validation", "Remote host is required.")
            return
        self.result = TunnelConfig(
            local_port=self._local_port.value(),
            remote_host=rhost,
            remote_port=self._remote_port.value(),
        )
        self.accept()
