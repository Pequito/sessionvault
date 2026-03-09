"""Dialog for opening (unlocking) a KeePass .kdbx database.

Written by Christopher Malo
"""

from __future__ import annotations

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
from app.managers.settings import settings_manager


class KeePassOpenDialog(QDialog):
    """Prompt the user for a .kdbx path, optional key file, and password.

    The last-used database path is stored in settings so the user only
    needs to enter the master password on subsequent launches.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Open KeePass Database")
        self.setMinimumWidth(460)
        self._build_ui()
        self._restore_last_path()

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

        # Hint shown when path is pre-filled from last session
        self._hint_lbl = QLabel(
            "Last-used database pre-filled. Enter master password to unlock."
        )
        self._hint_lbl.setObjectName("status-connecting")
        self._hint_lbl.setWordWrap(True)
        self._hint_lbl.setVisible(False)
        form.addRow("", self._hint_lbl)

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
    # Last-path persistence
    # ------------------------------------------------------------------

    def _restore_last_path(self) -> None:
        """Pre-fill the database path from the most recently opened file."""
        last_paths: list[str] = settings_manager.get("keepass_last_paths", [])
        if last_paths:
            self._db_edit.setText(last_paths[0])
            self._hint_lbl.setVisible(True)
        def showEvent(self, event) -> None:
            super().showEvent(event)
            if self._db_edit.text().strip():
                QTimer.singleShot(0, self._pw_edit.setFocus)
            else:
                QTimer.singleShot(0, self._db_edit.setFocus)
            if self.parent():
                geo = self.frameGeometry()
                geo.moveCenter(self.parent().geometry().center())
                self.move(geo.topLeft())

    
    def _save_last_path(self, path: str) -> None:
        """Persist ``path`` as the most-recently-used database."""
        last_paths: list[str] = settings_manager.get("keepass_last_paths", [])
        # Move to front, deduplicate, keep at most 5
        paths = [path] + [p for p in last_paths if p != path]
        settings_manager.set("keepass_last_paths", paths[:5])

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
            self._save_last_path(db_path)
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Could Not Open Database", str(exc))
