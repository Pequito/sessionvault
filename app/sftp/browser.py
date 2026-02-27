"""SFTP file browser widget – paramiko-backed, runs in a QThread.

Architecture
------------
_SFTPWorker
    Lives in a background QThread.  Owns the SFTPClient and exposes slots
    for cd / upload / download / mkdir / delete.  Emits ``listing_ready``
    with (cwd, items) so the GUI can update safely.

SFTPBrowserWidget
    A QWidget that creates the worker/thread pair and provides a toolbar
    + table for browsing the remote filesystem.
"""

from __future__ import annotations

import pathlib
import posixpath
import stat
from typing import Optional

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:
    import paramiko
    _PARAMIKO = True
except ImportError:
    _PARAMIKO = False


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

class _SFTPWorker(QObject):
    """Paramiko SFTP operations running in a background thread."""

    # (cwd, [(name, size_bytes, is_dir)])
    listing_ready = Signal(str, list)
    error = Signal(str)
    status = Signal(str)

    # Signals from GUI → worker (queued because different threads)
    _do_cd = Signal(str)
    _do_upload = Signal(str, str)       # local_path, remote_name
    _do_download = Signal(str, str)     # remote_name, local_path
    _do_mkdir = Signal(str)
    _do_delete = Signal(str)

    def __init__(self, transport) -> None:
        super().__init__()
        self._transport = transport
        self._sftp: Optional["paramiko.SFTPClient"] = None
        self._cwd: str = "/"

        # Wire internal queued signals to actual handler slots
        self._do_cd.connect(self._cd)
        self._do_upload.connect(self._upload)
        self._do_download.connect(self._download)
        self._do_mkdir.connect(self._mkdir)
        self._do_delete.connect(self._delete)

    # ------------------------------------------------------------------
    # Initialisation (called by QThread.started)
    # ------------------------------------------------------------------

    @Slot()
    def connect(self) -> None:
        if not _PARAMIKO:
            self.error.emit("paramiko is not installed.")
            return
        try:
            self._sftp = paramiko.SFTPClient.from_transport(self._transport)
            self._cwd = self._sftp.normalize(".")
            self.status.emit(f"SFTP connected — {self._cwd}")
            self._emit_listing()
        except Exception as exc:
            self.error.emit(f"SFTP connect error: {exc}")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    @Slot(str)
    def _cd(self, path: str) -> None:
        if self._sftp is None:
            return
        try:
            new = posixpath.normpath(posixpath.join(self._cwd, path))
            self._sftp.chdir(new)
            self._cwd = self._sftp.normalize(".")
            self._emit_listing()
        except Exception as exc:
            self.error.emit(str(exc))

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    @Slot(str, str)
    def _upload(self, local_path: str, remote_name: str) -> None:
        if self._sftp is None:
            return
        try:
            remote = posixpath.join(self._cwd, remote_name)
            self._sftp.put(local_path, remote)
            self.status.emit(f"Uploaded: {remote_name}")
            self._emit_listing()
        except Exception as exc:
            self.error.emit(f"Upload failed: {exc}")

    @Slot(str, str)
    def _download(self, remote_name: str, local_path: str) -> None:
        if self._sftp is None:
            return
        try:
            remote = posixpath.join(self._cwd, remote_name)
            self._sftp.get(remote, local_path)
            self.status.emit(f"Downloaded to: {local_path}")
        except Exception as exc:
            self.error.emit(f"Download failed: {exc}")

    @Slot(str)
    def _mkdir(self, name: str) -> None:
        if self._sftp is None:
            return
        try:
            self._sftp.mkdir(posixpath.join(self._cwd, name))
            self._emit_listing()
        except Exception as exc:
            self.error.emit(f"mkdir failed: {exc}")

    @Slot(str)
    def _delete(self, name: str) -> None:
        if self._sftp is None:
            return
        try:
            path = posixpath.join(self._cwd, name)
            attrs = self._sftp.lstat(path)
            if stat.S_ISDIR(attrs.st_mode):
                self._sftp.rmdir(path)
            else:
                self._sftp.remove(path)
            self._emit_listing()
        except Exception as exc:
            self.error.emit(f"Delete failed: {exc}")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _emit_listing(self) -> None:
        if self._sftp is None:
            return
        try:
            items: list[tuple[str, int, bool]] = []
            for attr in sorted(
                self._sftp.listdir_attr(self._cwd), key=lambda a: a.filename
            ):
                is_dir = bool(attr.st_mode and stat.S_ISDIR(attr.st_mode))
                items.append((attr.filename, attr.st_size or 0, is_dir))
            self.listing_ready.emit(self._cwd, items)
        except Exception as exc:
            self.error.emit(f"Listing error: {exc}")

    def cleanup(self) -> None:
        if self._sftp:
            try:
                self._sftp.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------

class SFTPBrowserWidget(QWidget):
    """SFTP file browser shown as a tab alongside the SSH terminal."""

    def __init__(self, transport, session_name: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._transport = transport
        self._session_name = session_name
        self._listing: list[tuple[str, int, bool]] = []
        self._current_dir: str = "/"
        self._build_ui()
        self._start_worker()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # ── Toolbar ────────────────────────────────────────────────────
        tb = QHBoxLayout()
        tb.setContentsMargins(6, 4, 6, 4)

        self._up_btn = QPushButton("↑ Up")
        self._up_btn.setFixedWidth(60)
        self._up_btn.clicked.connect(lambda: self._worker._do_cd.emit(".."))
        tb.addWidget(self._up_btn)

        self._path_lbl = QLineEdit("/")
        self._path_lbl.setReadOnly(True)
        tb.addWidget(self._path_lbl, 1)

        refresh_btn = QPushButton("⟳")
        refresh_btn.setFixedWidth(36)
        refresh_btn.clicked.connect(lambda: self._worker._do_cd.emit("."))
        tb.addWidget(refresh_btn)

        mkdir_btn = QPushButton("+ Folder")
        mkdir_btn.clicked.connect(self._mkdir)
        tb.addWidget(mkdir_btn)

        upload_btn = QPushButton("⬆ Upload")
        upload_btn.clicked.connect(self._upload)
        tb.addWidget(upload_btn)

        download_btn = QPushButton("⬇ Download")
        download_btn.clicked.connect(self._download)
        tb.addWidget(download_btn)

        delete_btn = QPushButton("✕ Delete")
        delete_btn.setObjectName("danger")
        delete_btn.clicked.connect(self._delete)
        tb.addWidget(delete_btn)

        layout.addLayout(tb)

        # ── File table ─────────────────────────────────────────────────
        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Name", "Size", "Type"])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)

        # ── Status bar ─────────────────────────────────────────────────
        self._status_lbl = QLabel("Connecting to SFTP…")
        layout.addWidget(self._status_lbl)

    # ------------------------------------------------------------------
    # Worker / thread
    # ------------------------------------------------------------------

    def _start_worker(self) -> None:
        self._thread = QThread(self)
        self._worker = _SFTPWorker(self._transport)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.connect)
        self._worker.listing_ready.connect(self._on_listing)
        self._worker.error.connect(self._on_error)
        self._worker.status.connect(self._status_lbl.setText)

        self._thread.start()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @Slot(str, list)
    def _on_listing(self, cwd: str, items: list) -> None:
        self._current_dir = cwd
        self._listing = items
        self._path_lbl.setText(cwd)
        self._table.setRowCount(0)
        for name, size, is_dir in items:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(name))
            self._table.setItem(row, 1, QTableWidgetItem(
                "—" if is_dir else f"{size:,}"
            ))
            self._table.setItem(row, 2, QTableWidgetItem(
                "Directory" if is_dir else "File"
            ))
        self._status_lbl.setText(f"{cwd}  —  {len(items)} item(s)")

    @Slot(str)
    def _on_error(self, msg: str) -> None:
        self._status_lbl.setText(f"Error: {msg}")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _selected(self) -> Optional[tuple[str, int, bool]]:
        row = self._table.currentRow()
        if 0 <= row < len(self._listing):
            return self._listing[row]
        return None

    def _on_double_click(self, _item: QTableWidgetItem) -> None:
        sel = self._selected()
        if sel and sel[2]:   # is_dir
            self._worker._do_cd.emit(sel[0])

    def _mkdir(self) -> None:
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name.strip():
            self._worker._do_mkdir.emit(name.strip())

    def _upload(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Upload files")
        for p in paths:
            self._worker._do_upload.emit(p, pathlib.Path(p).name)

    def _download(self) -> None:
        sel = self._selected()
        if sel is None:
            return
        name, _size, is_dir = sel
        if is_dir:
            QMessageBox.information(
                self, "SFTP", "Recursive directory download is not supported."
            )
            return
        dest = QFileDialog.getExistingDirectory(self, "Download to…")
        if dest:
            local = str(pathlib.Path(dest) / name)
            self._worker._do_download.emit(name, local)

    def _delete(self) -> None:
        sel = self._selected()
        if sel is None:
            return
        name = sel[0]
        reply = QMessageBox.question(
            self,
            "Delete",
            f"Delete '{name}'?  This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._worker._do_delete.emit(name)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        self._worker.cleanup()
        self._thread.quit()
        self._thread.wait(2000)
        super().closeEvent(event)
