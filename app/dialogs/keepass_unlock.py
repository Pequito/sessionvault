"""Re-unlock dialog for a previously-opened KeePass database.

Shows the file path read-only and only asks for the master password
(and optional key file).  Used when a database is known but locked.

Written by Christopher Malo
"""

from __future__ import annotations

import pathlib

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.managers.keepass import keepass_manager


class KeePassUnlockDialog(QDialog):
    """Prompt only for the master password to re-open a known .kdbx file."""

    def __init__(self, parent=None, *, path: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Unlock KeePass Database")
        self.setMinimumWidth(420)
        self._path = path
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(20, 20, 20, 20)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Database name (read-only)
        name_lbl = QLabel(f"<b>{pathlib.Path(self._path).name}</b>")
        name_lbl.setToolTip(self._path)
        name_lbl.setObjectName("kp-entry")
        form.addRow("Database", name_lbl)

        # Key file (optional)
        kf_row = QHBoxLayout()
        self._kf_edit = QLineEdit()
        self._kf_edit.setPlaceholderText("optional")
        kf_browse = QPushButton("Browse…")
        kf_browse.clicked.connect(self._browse_kf)
        kf_row.addWidget(self._kf_edit, 1)
        kf_row.addWidget(kf_browse)
        form.addRow("Key File", kf_row)

        # Master password
        self._pw_edit = QLineEdit()
        self._pw_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw_edit.setPlaceholderText("master password")
        form.addRow("Master Password", self._pw_edit)

        root.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Open
            | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = btns.button(QDialogButtonBox.StandardButton.Open)
        ok_btn.setObjectName("success")
        ok_btn.setText("Unlock")
        btns.accepted.connect(self._unlock)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        self._pw_edit.returnPressed.connect(self._unlock)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._pw_edit.setFocus)
        if self.parent():
            geo = self.frameGeometry()
            geo.moveCenter(self.parent().geometry().center())
            self.move(geo.topLeft())

    def _browse_kf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Key File", "", "All files (*)"
        )
        if path:
            self._kf_edit.setText(path)

    def _unlock(self) -> None:
        try:
            keepass_manager.open(
                self._path,
                self._pw_edit.text(),
                self._kf_edit.text().strip(),
            )
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Could Not Unlock", str(exc))
            self._pw_edit.clear()
            self._pw_edit.setFocus()
