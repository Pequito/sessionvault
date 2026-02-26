"""SSH terminal widget built with PySide6.

Architecture
------------
SSHWorker
    A ``QObject`` that lives inside a ``QThread``.  It owns the paramiko
    SSH client and channel, runs a non-blocking I/O loop, and communicates
    with the GUI exclusively through Qt signals / slots.

SSHTerminalWidget
    A ``QWidget`` containing a read-only ``QTextEdit`` for coloured output
    and a slim status label.  It creates the worker/thread pair and routes
    user key-presses to the worker via a queued signal.
"""

from __future__ import annotations

import queue
from typing import Optional

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtGui import QColor, QKeyEvent, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QLabel,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.constants import C
from app.models import SSHSessionConfig
from app.terminal.ansi import AnsiParser

try:
    import paramiko
    _PARAMIKO = True
except ImportError:
    _PARAMIKO = False


# ---------------------------------------------------------------------------
# SSH Worker
# ---------------------------------------------------------------------------

class SSHWorker(QObject):
    """Manages a single SSH connection inside a background QThread."""

    output = Signal(str)    # raw terminal data from server
    status = Signal(str)    # human-readable connection status
    finished = Signal()     # emitted when the connection is closed

    _READ_CHUNK = 4096

    def __init__(
        self,
        session: SSHSessionConfig,
        password: Optional[str] = None,
    ) -> None:
        super().__init__()
        self._session = session
        self._password = password
        self._channel: Optional["paramiko.Channel"] = None
        self._ssh: Optional["paramiko.SSHClient"] = None
        self._running = False
        self._send_queue: queue.Queue[bytes] = queue.Queue()

    # ------------------------------------------------------------------
    # Public slots (called from GUI thread via queued connections)
    # ------------------------------------------------------------------

    @Slot(bytes)
    def send(self, data: bytes) -> None:
        """Queue *data* to be written to the remote channel."""
        self._send_queue.put(data)

    @Slot()
    def stop(self) -> None:
        """Request the I/O loop to terminate."""
        self._running = False

    # ------------------------------------------------------------------
    # Main run method – invoked by QThread.started signal
    # ------------------------------------------------------------------

    @Slot()
    def run(self) -> None:
        if not _PARAMIKO:
            self.status.emit("Error: paramiko not installed")
            self.output.emit(
                "\r\n\033[31m[ERROR]\033[0m  paramiko is not installed.\r\n"
                "Run:  pip install paramiko\r\n"
            )
            self.finished.emit()
            return

        host = self._session.hostname
        port = self._session.port
        self.status.emit(f"Connecting to {host}:{port}…")

        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            kwargs: dict = {
                "hostname": host,
                "port": port,
                "username": self._session.username,
                "timeout": 15,
            }
            if self._session.key_path:
                kwargs["key_filename"] = self._session.key_path
            if self._password:
                kwargs["password"] = self._password
            client.connect(**kwargs)
            self._ssh = client
            chan = client.invoke_shell(term="xterm-256color", width=220, height=50)
            chan.setblocking(False)
            self._channel = chan
            self._running = True
            self.status.emit(f"Connected — {self._session.username}@{host}")
            self._io_loop()
        except Exception as exc:
            self.status.emit(f"Error: {exc}")
            self.output.emit(f"\r\n\033[31m[ERROR]\033[0m  {exc}\r\n")

        self._running = False
        self._cleanup()
        self.status.emit("Disconnected")
        self.finished.emit()

    # ------------------------------------------------------------------
    # I/O loop
    # ------------------------------------------------------------------

    def _io_loop(self) -> None:
        import select as _sel

        chan = self._channel
        while self._running and chan and not chan.closed:
            # Flush outbound keystrokes
            while not self._send_queue.empty():
                try:
                    chan.send(self._send_queue.get_nowait())
                except Exception:
                    pass
            # Read inbound data
            try:
                r, _, _ = _sel.select([chan], [], [], 0.05)
                if r:
                    data = chan.recv(self._READ_CHUNK)
                    if data:
                        self.output.emit(data.decode("utf-8", errors="replace"))
                    else:
                        break  # server closed channel
            except Exception:
                break

    def _cleanup(self) -> None:
        for obj in (self._channel, self._ssh):
            if obj is not None:
                try:
                    obj.close()
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# Terminal widget
# ---------------------------------------------------------------------------

class SSHTerminalWidget(QWidget):
    """A self-contained SSH terminal tab widget."""

    def __init__(
        self,
        session: SSHSessionConfig,
        password: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._session = session
        self._ansi = AnsiParser()
        self._build_ui()
        self._start_worker(password)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Status bar
        self._status_lbl = QLabel("Connecting…")
        self._status_lbl.setObjectName("status-connecting")
        self._status_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        layout.addWidget(self._status_lbl)

        # Terminal area
        self._editor = _TerminalEdit(self)
        self._editor.setObjectName("terminal")
        self._editor.setReadOnly(True)
        self._editor.key_pressed.connect(self._on_key)
        layout.addWidget(self._editor)

    # ------------------------------------------------------------------
    # Worker / thread setup
    # ------------------------------------------------------------------

    def _start_worker(self, password: Optional[str]) -> None:
        self._thread = QThread(self)
        self._worker = SSHWorker(self._session, password)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.output.connect(self._append_ansi)
        self._worker.status.connect(self._on_status)
        self._worker.finished.connect(self._thread.quit)

        self._thread.start()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @Slot(str)
    def _on_status(self, msg: str) -> None:
        self._status_lbl.setText(msg)
        msg_l = msg.lower()
        if "connected" in msg_l and "dis" not in msg_l:
            name = "status-connected"
        elif "error" in msg_l or "disconnected" in msg_l:
            name = "status-error"
        else:
            name = "status-connecting"
        self._status_lbl.setObjectName(name)
        # Force Qt to re-apply the stylesheet for the new object name
        self._status_lbl.style().unpolish(self._status_lbl)
        self._status_lbl.style().polish(self._status_lbl)

    @Slot(str)
    def _append_ansi(self, data: str) -> None:
        cursor = self._editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        for text, style in self._ansi.feed(data):
            cursor.insertText(text, _style_to_fmt(style))
        self._editor.setTextCursor(cursor)
        self._editor.ensureCursorVisible()

    @Slot(bytes)
    def _on_key(self, data: bytes) -> None:
        self._worker.send(data)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close_connection(self) -> None:
        """Gracefully stop the SSH worker and its thread."""
        if hasattr(self, "_worker"):
            self._worker.stop()
        if hasattr(self, "_thread"):
            self._thread.quit()
            self._thread.wait(3000)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

class _TerminalEdit(QTextEdit):
    """Read-only QTextEdit that captures key events and emits them as bytes."""

    key_pressed = Signal(bytes)

    _SPECIAL: dict[int, bytes] = {
        Qt.Key.Key_Return:    b"\r",
        Qt.Key.Key_Enter:     b"\r",
        Qt.Key.Key_Backspace: b"\x7f",
        Qt.Key.Key_Tab:       b"\t",
        Qt.Key.Key_Escape:    b"\x1b",
        Qt.Key.Key_Up:        b"\x1b[A",
        Qt.Key.Key_Down:      b"\x1b[B",
        Qt.Key.Key_Right:     b"\x1b[C",
        Qt.Key.Key_Left:      b"\x1b[D",
        Qt.Key.Key_Home:      b"\x1b[H",
        Qt.Key.Key_End:       b"\x1b[F",
        Qt.Key.Key_Delete:    b"\x1b[3~",
        Qt.Key.Key_PageUp:    b"\x1b[5~",
        Qt.Key.Key_PageDown:  b"\x1b[6~",
        Qt.Key.Key_F1:        b"\x1bOP",
        Qt.Key.Key_F2:        b"\x1bOQ",
        Qt.Key.Key_F3:        b"\x1bOR",
        Qt.Key.Key_F4:        b"\x1bOS",
    }

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key in self._SPECIAL:
            self.key_pressed.emit(self._SPECIAL[key])
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            text = event.text()
            if text:
                self.key_pressed.emit(text.encode("utf-8"))
            return
        text = event.text()
        if text:
            self.key_pressed.emit(text.encode("utf-8"))


def _style_to_fmt(style: dict) -> QTextCharFormat:
    """Convert an :class:`AnsiParser` style dict to a ``QTextCharFormat``."""
    fmt = QTextCharFormat()
    if style.get("fg"):
        fmt.setForeground(QColor(style["fg"]))
    if style.get("bg"):
        fmt.setBackground(QColor(style["bg"]))
    if style.get("bold"):
        fmt.setFontWeight(700)
    if style.get("underline"):
        fmt.setFontUnderline(True)
    return fmt
