"""KeePass entry editor and new-database creation dialogs."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
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


# ---------------------------------------------------------------------------
# Entry create / edit
# ---------------------------------------------------------------------------

class KeePassEntryDialog(QDialog):
    """Create or edit a single KeePass entry."""

    def __init__(self, parent=None, entry=None) -> None:
        super().__init__(parent)
        self._entry = entry
        self.setWindowTitle("New Entry" if entry is None else "Edit Entry")
        self.setMinimumWidth(460)
        self._build_ui()
        if entry:
            self._populate(entry)

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

        self._group_edit = QLineEdit("General")
        form.addRow("Group", self._group_edit)

        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("My Server")
        form.addRow("Title", self._title_edit)

        self._user_edit = QLineEdit()
        form.addRow("Username", self._user_edit)

        # Password row with show/hide toggle
        pw_row = QHBoxLayout()
        self._pw_edit = QLineEdit()
        self._pw_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._show_btn = QPushButton("Show")
        self._show_btn.setCheckable(True)
        self._show_btn.setFixedWidth(56)
        self._show_btn.toggled.connect(self._toggle_pw)
        pw_row.addWidget(self._pw_edit, 1)
        pw_row.addWidget(self._show_btn)
        form.addRow("Password", pw_row)

        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("https://…")
        form.addRow("URL", self._url_edit)

        self._notes_edit = QLineEdit()
        self._notes_edit.setPlaceholderText("Optional notes")
        form.addRow("Notes", self._notes_edit)

        root.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Save).setObjectName("primary")
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------

    def _populate(self, entry) -> None:
        if entry.group:
            self._group_edit.setText(entry.group.name)
        self._title_edit.setText(entry.title or "")
        self._user_edit.setText(entry.username or "")
        self._pw_edit.setText(entry.password or "")
        self._url_edit.setText(entry.url or "")
        self._notes_edit.setText(entry.notes or "")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _toggle_pw(self, checked: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        self._pw_edit.setEchoMode(mode)
        self._show_btn.setText("Hide" if checked else "Show")

    def _save(self) -> None:
        title = self._title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "Validation", "Title is required.")
            return

        if self._entry:
            ok = keepass_manager.update_entry(
                str(self._entry.uuid),
                title=title,
                username=self._user_edit.text(),
                password=self._pw_edit.text(),
                url=self._url_edit.text(),
                notes=self._notes_edit.text(),
            )
            if not ok:
                QMessageBox.critical(self, "Error", "Could not update entry.")
                return
        else:
            entry = keepass_manager.add_entry(
                group_name=self._group_edit.text().strip() or "General",
                title=title,
                username=self._user_edit.text(),
                password=self._pw_edit.text(),
                url=self._url_edit.text(),
                notes=self._notes_edit.text(),
            )
            if entry is None:
                QMessageBox.critical(
                    self, "Error",
                    "Could not create entry.  Is a database open?"
                )
                return
        self.accept()


# ---------------------------------------------------------------------------
# New database
# ---------------------------------------------------------------------------

class KeePassNewDatabaseDialog(QDialog):
    """Create a brand-new .kdbx database file."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create KeePass Database")
        self.setMinimumWidth(480)
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

        # Save path
        db_row = QHBoxLayout()
        self._db_edit = QLineEdit()
        self._db_edit.setPlaceholderText("path/to/new.kdbx")
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)
        db_row.addWidget(self._db_edit, 1)
        db_row.addWidget(browse_btn)
        form.addRow("Save as (.kdbx)", db_row)

        self._pw1_edit = QLineEdit()
        self._pw1_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw1_edit.setPlaceholderText("master password")
        form.addRow("Master password", self._pw1_edit)

        self._pw2_edit = QLineEdit()
        self._pw2_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw2_edit.setPlaceholderText("confirm password")
        form.addRow("Confirm password", self._pw2_edit)

        self._argon2_chk = QCheckBox(
            "Use Argon2 + ChaCha20 encryption  (KDBX4 – recommended)"
        )
        self._argon2_chk.setChecked(True)
        form.addRow("", self._argon2_chk)

        root.addLayout(form)

        note = QLabel(
            "AES-256 / PBKDF2 (KDBX3.1) is available for compatibility\n"
            "with older KeePass clients that don't support KDBX4."
        )
        note.setWordWrap(True)
        root.addWidget(note)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = btns.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setObjectName("success")
        ok_btn.setText("Create Database")
        btns.accepted.connect(self._create)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "New KeePass Database",
            "",
            "KeePass databases (*.kdbx)",
        )
        if path:
            if not path.endswith(".kdbx"):
                path += ".kdbx"
            self._db_edit.setText(path)

    def _create(self) -> None:
        path = self._db_edit.text().strip()
        pw1 = self._pw1_edit.text()
        pw2 = self._pw2_edit.text()
        if not path:
            QMessageBox.warning(self, "Error", "Please choose a file path.")
            return
        if pw1 != pw2:
            QMessageBox.warning(self, "Error", "Passwords do not match.")
            return
        kdf = "argon2" if self._argon2_chk.isChecked() else "aeskdf"
        try:
            keepass_manager.create_database(path, pw1, kdf=kdf)
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
