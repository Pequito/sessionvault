"""SSH connection credential dialog.

Shows hostname/port (read-only), editable username, and password.
If a KeePass database is open the user can pick a matching entry
instead of typing a password manually.

Written by Christopher Malo
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from app.managers.keepass import keepass_manager


class SSHConnectDialog(QDialog):
    """Credential prompt shown when connecting to an SSH session.

    Attributes
    ----------
    username : str
        The username to use (may have been pre-filled from the session config).
    password : str | None
        The password chosen by the user, or ``None`` if cancelled.
    """

    def __init__(
        self,
        parent=None,
        *,
        hostname: str = "",
        port: int = 22,
        username: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("SSH Connect")
        self.setMinimumWidth(420)

        self._hostname = hostname
        self._port     = port
        self._pre_user = username
        self.password: Optional[str] = None

        self._build_ui()
        self._populate_keepass_entries()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(20, 20, 20, 20)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Host label (read-only)
        host_lbl = QLabel(f"<b>{self._hostname}</b>  :  {self._port}")
        host_lbl.setObjectName("kp-entry")
        form.addRow("Host", host_lbl)

        # Username
        self._user_edit = QLineEdit(self._pre_user)
        self._user_edit.setPlaceholderText("username")
        form.addRow("Username", self._user_edit)

        # Password
        self._pw_edit = QLineEdit()
        self._pw_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw_edit.setPlaceholderText("password")
        form.addRow("Password", self._pw_edit)

        root.addLayout(form)

        # KeePass section (only shown when a db is open)
        self._kp_row = QHBoxLayout()
        self._kp_row.setSpacing(6)

        kp_icon = QLabel("🔑")
        kp_icon.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._kp_row.addWidget(kp_icon)

        self._kp_combo = QComboBox()
        self._kp_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._kp_combo.setToolTip("Select a KeePass entry to use its credentials")
        self._kp_combo.currentIndexChanged.connect(self._on_kp_entry_selected)
        self._kp_row.addWidget(self._kp_combo, 1)

        self._kp_clear_btn = QPushButton("Clear")
        self._kp_clear_btn.setToolTip("Stop using KeePass entry; type password manually")
        self._kp_clear_btn.setFixedWidth(56)
        self._kp_clear_btn.clicked.connect(self._on_kp_clear)
        self._kp_row.addWidget(self._kp_clear_btn)

        kp_widget_wrapper = QLabel()          # invisible spacer row label
        kp_widget_wrapper.setText("KeePass")
        form.addRow(kp_widget_wrapper, self._kp_row)

        # KeePass row visibility is controlled after populating combo
        self._kp_form_label = kp_widget_wrapper

        # Buttons
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = btns.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setObjectName("primary")
        ok_btn.setText("Connect")
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        self._pw_edit.returnPressed.connect(self._accept)

    # ------------------------------------------------------------------
    # KeePass integration
    # ------------------------------------------------------------------

    def _populate_keepass_entries(self) -> None:
        """Fill the KeePass combo with entries matching the host."""
        if not keepass_manager.is_open:
            self._set_kp_row_visible(False)
            return

        self._kp_combo.blockSignals(True)
        self._kp_combo.clear()
        self._kp_combo.addItem("— select entry —", userData=None)

        entries = keepass_manager.get_all_entries()
        hostname_lc = self._hostname.lower()

        # Sort: matching entries first, then all others
        matching, others = [], []
        for e in entries:
            url = (e.url or "").lower()
            title = (e.title or "").lower()
            if hostname_lc and (hostname_lc in url or hostname_lc in title):
                matching.append(e)
            else:
                others.append(e)

        for e in matching + others:
            label = e.title or "(no title)"
            if e.username:
                label += f"  [{e.username}]"
            self._kp_combo.addItem("🔑  " + label, userData=e)

        self._kp_combo.blockSignals(False)
        self._set_kp_row_visible(True)

    def _set_kp_row_visible(self, visible: bool) -> None:
        for i in range(self._kp_row.count()):
            w = self._kp_row.itemAt(i).widget()
            if w:
                w.setVisible(visible)
        self._kp_form_label.setVisible(visible)

    def _on_kp_entry_selected(self, index: int) -> None:
        entry = self._kp_combo.itemData(index)
        if entry is None:
            return
        # Fill username and password from the selected entry
        if entry.username:
            self._user_edit.setText(entry.username)
        pw = entry.password or ""
        self._pw_edit.setText(pw)

    def _on_kp_clear(self) -> None:
        self._kp_combo.setCurrentIndex(0)
        self._user_edit.setText(self._pre_user)
        self._pw_edit.clear()

    # ------------------------------------------------------------------
    # Accept
    # ------------------------------------------------------------------

    def _accept(self) -> None:
        self.username = self._user_edit.text()
        self.password = self._pw_edit.text()
        self.accept()
