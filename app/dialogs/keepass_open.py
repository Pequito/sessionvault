"""Dialog for opening (unlocking) a KeePass .kdbx database."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.managers.keepass import keepass_manager


class KeePassOpenDialog(QDialog):
    """Prompt the user for a .kdbx path, optional key file, and password."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Open KeePass Database")
        self.setMinimumWidth(460)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(20, 20, 20, 20)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Database path
        db_row = QHBoxLayout()
        self._db_edit = QLineEdit()
        self._db_edit.setPlaceholderText("path/to/database.kdbx")
        db_browse = QPushButton("Browse…")
        db_browse.clicked.connect(self._browse_db)
        db_row.addWidget(self._db_edit, 1)
        db_row.addWidget(db_browse)
        form.addRow("Database (.kdbx)", db_row)

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

        # Dialog buttons
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Open
            | QDialogButtonBox.StandardButton.Cancel
        )
        open_btn = btns.button(QDialogButtonBox.StandardButton.Open)
        open_btn.setObjectName("success")
        open_btn.setText("Unlock Database")
        btns.accepted.connect(self._open)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        self._pw_edit.returnPressed.connect(self._open)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _browse_db(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select KeePass Database",
            "",
            "KeePass databases (*.kdbx);;All files (*)",
        )
        if path:
            self._db_edit.setText(path)

    def _browse_kf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Key File", "", "All files (*)"
        )
        if path:
            self._kf_edit.setText(path)

    def _open(self) -> None:
        db_path = self._db_edit.text().strip()
        if not db_path:
            QMessageBox.warning(self, "Error", "Please select a database file.")
            return
        try:
            keepass_manager.open(
                db_path,
                self._pw_edit.text(),
                self._kf_edit.text().strip(),
            )
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Could Not Open Database", str(exc))
