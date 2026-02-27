"""SSH terminal widget (PySide6) – extended with X11, tunnels, macros, autofill.

Architecture
------------
SSHWorker      – paramiko SSH client in a QThread.  Emits transport_ready so
                 an SFTP tab can be opened on the same connection.
TelnetWorker   – socket-based Telnet client in a QThread.
SSHTerminalWidget – tab widget that dispatches to the right worker based on
                 session.protocol.  Also handles macros and KeePass autofill.

Supported protocols
-------------------
ssh     → SSHWorker (paramiko)
telnet  → TelnetWorker (stdlib socket)
rdp     → subprocess xfreerdp / mstsc (external window)
vnc     → subprocess vncviewer (external window)
"""

from __future__ import annotations

import queue
import socket
import subprocess
import sys
import threading
from typing import Optional

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtGui import QColor, QKeyEvent, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.constants import C
from app.models import SSHSessionConfig, TunnelConfig
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

    output = Signal(str)
    status = Signal(str)
    finished = Signal()
    # Emitted after connect – carries the live transport for SFTP
    transport_ready = Signal(object)

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
        self._tunnel_threads: list[threading.Thread] = []

    @Slot(bytes)
    def send(self, data: bytes) -> None:
        self._send_queue.put(data)

    @Slot()
    def stop(self) -> None:
        self._running = False

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
            transport = client.get_transport()

            # ── X11 forwarding ──────────────────────────────────────────
            if self._session.x11_forwarding and transport:
                try:
                    transport.request_x11(screen_number=0)
                    self.status.emit(f"Connecting (X11)…")
                except Exception as x11_err:
                    self.output.emit(
                        f"\r\n\033[33m[X11]\033[0m  X11 forwarding failed: {x11_err}\r\n"
                    )

            # ── Local port forwarding ───────────────────────────────────
            for t in self._session.tunnels():
                self._start_tunnel(transport, t)

            chan = client.invoke_shell(term="xterm-256color", width=220, height=50)
            chan.setblocking(False)
            self._channel = chan
            self._running = True
            self.status.emit(f"Connected — {self._session.username}@{host}")

            # Signal the transport so an SFTP tab can be opened
            if transport:
                self.transport_ready.emit(transport)

            self._io_loop()
        except Exception as exc:
            self.status.emit(f"Error: {exc}")
            self.output.emit(f"\r\n\033[31m[ERROR]\033[0m  {exc}\r\n")

        self._running = False
        self._cleanup()
        self.status.emit("Disconnected")
        self.finished.emit()

    # ------------------------------------------------------------------
    # SSH Tunnels (local port forwarding)
    # ------------------------------------------------------------------

    def _start_tunnel(self, transport, tunnel: TunnelConfig) -> None:
        """Listen on localhost:tunnel.local_port and forward to remote."""
        if not transport:
            return
        t = threading.Thread(
            target=self._tunnel_server,
            args=(transport, tunnel),
            daemon=True,
        )
        t.start()
        self._tunnel_threads.append(t)
        self.output.emit(
            f"\r\n\033[36m[TUNNEL]\033[0m  "
            f"localhost:{tunnel.local_port} → "
            f"{tunnel.remote_host}:{tunnel.remote_port}\r\n"
        )

    @staticmethod
    def _tunnel_server(transport, tunnel: TunnelConfig) -> None:
        """Accept local connections and proxy them over paramiko channels."""
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("127.0.0.1", tunnel.local_port))
            srv.listen(10)
            srv.settimeout(1.0)
        except Exception:
            return

        while transport.is_active():
            try:
                client_sock, _ = srv.accept()
            except socket.timeout:
                continue
            except Exception:
                break
            try:
                chan = transport.open_channel(
                    "direct-tcpip",
                    (tunnel.remote_host, tunnel.remote_port),
                    ("127.0.0.1", tunnel.local_port),
                )
            except Exception:
                client_sock.close()
                continue
            threading.Thread(
                target=_proxy_sockets, args=(client_sock, chan), daemon=True
            ).start()
        srv.close()

    # ------------------------------------------------------------------
    # I/O loop
    # ------------------------------------------------------------------

    def _io_loop(self) -> None:
        import select as _sel
        chan = self._channel
        while self._running and chan and not chan.closed:
            while not self._send_queue.empty():
                try:
                    chan.send(self._send_queue.get_nowait())
                except Exception:
                    pass
            try:
                r, _, _ = _sel.select([chan], [], [], 0.05)
                if r:
                    data = chan.recv(self._READ_CHUNK)
                    if data:
                        self.output.emit(data.decode("utf-8", errors="replace"))
                    else:
                        break
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
# Telnet Worker
# ---------------------------------------------------------------------------

class TelnetWorker(QObject):
    """Minimal Telnet client via raw socket (IAC negotiation best-effort)."""

    output = Signal(str)
    status = Signal(str)
    finished = Signal()

    _IAC = b"\xff"
    _READ_CHUNK = 4096

    def __init__(self, session: SSHSessionConfig) -> None:
        super().__init__()
        self._session = session
        self._sock: Optional[socket.socket] = None
        self._running = False
        self._send_queue: queue.Queue[bytes] = queue.Queue()

    @Slot(bytes)
    def send(self, data: bytes) -> None:
        self._send_queue.put(data)

    @Slot()
    def stop(self) -> None:
        self._running = False

    @Slot()
    def run(self) -> None:
        host = self._session.hostname
        port = self._session.port
        self.status.emit(f"Connecting Telnet to {host}:{port}…")
        try:
            self._sock = socket.create_connection((host, port), timeout=15)
            self._sock.settimeout(0.05)
            self._running = True
            self.status.emit(f"Telnet connected — {host}:{port}")
            self._io_loop()
        except Exception as exc:
            self.status.emit(f"Error: {exc}")
            self.output.emit(f"\r\n\033[31m[ERROR]\033[0m  {exc}\r\n")
        finally:
            if self._sock:
                try:
                    self._sock.close()
                except Exception:
                    pass
            self.status.emit("Disconnected")
            self.finished.emit()

    def _io_loop(self) -> None:
        buf = b""
        while self._running:
            while not self._send_queue.empty():
                try:
                    self._sock.sendall(self._send_queue.get_nowait())
                except Exception:
                    self._running = False
                    break
            try:
                chunk = self._sock.recv(self._READ_CHUNK)
                if not chunk:
                    break
                buf += chunk
                text, buf = self._strip_iac(buf)
                if text:
                    self.output.emit(text.decode("utf-8", errors="replace"))
            except socket.timeout:
                continue
            except Exception:
                break

    def _strip_iac(self, data: bytes) -> tuple[bytes, bytes]:
        """Remove IAC telnet negotiation sequences, return printable bytes."""
        out = bytearray()
        i = 0
        while i < len(data):
            if data[i:i+1] == self._IAC:
                if i + 1 < len(data):
                    cmd = data[i+1]
                    if cmd in (251, 252, 253, 254) and i + 2 < len(data):
                        i += 3   # IAC WILL/WONT/DO/DONT <opt>
                    elif cmd == 255:
                        out.append(255)
                        i += 2   # escaped IAC
                    else:
                        i += 2
                else:
                    break   # incomplete – leave in buf
            else:
                out.append(data[i])
                i += 1
        return bytes(out), data[i:]


# ---------------------------------------------------------------------------
# Proxy helper (for SSH tunnels)
# ---------------------------------------------------------------------------

def _proxy_sockets(sock_a, sock_b) -> None:
    """Bidirectionally forward data between two socket-like objects."""
    import select as _sel
    try:
        while True:
            r, _, _ = _sel.select([sock_a, sock_b], [], [], 1.0)
            if sock_a in r:
                data = sock_a.recv(4096)
                if not data:
                    break
                sock_b.sendall(data)
            if sock_b in r:
                data = sock_b.recv(4096)
                if not data:
                    break
                sock_a.sendall(data)
    except Exception:
        pass
    finally:
        for s in (sock_a, sock_b):
            try:
                s.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Terminal widget
# ---------------------------------------------------------------------------

class SSHTerminalWidget(QWidget):
    """A self-contained session tab (SSH / Telnet / RDP-launcher / VNC-launcher)."""

    def __init__(
        self,
        session: SSHSessionConfig,
        password: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._session = session
        self._password = password
        self._ansi = AnsiParser()
        self._recording = False
        self._recorded_cmds: list[str] = []
        self._transport = None   # set by SSH worker after connect

        self._build_ui()
        self._start_connection()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Status bar row
        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)

        self._status_lbl = QLabel("Connecting…")
        self._status_lbl.setObjectName("status-connecting")
        self._status_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        status_row.addWidget(self._status_lbl)

        # Quick-action buttons
        self._sftp_btn = QPushButton("SFTP")
        self._sftp_btn.setToolTip("Open SFTP browser for this session")
        self._sftp_btn.setFixedHeight(22)
        self._sftp_btn.setEnabled(False)
        self._sftp_btn.clicked.connect(self._open_sftp)
        status_row.addWidget(self._sftp_btn)

        self._macro_btn = QPushButton("Macros")
        self._macro_btn.setToolTip("Record / play macros")
        self._macro_btn.setFixedHeight(22)
        self._macro_btn.clicked.connect(self._show_macro_menu)
        status_row.addWidget(self._macro_btn)

        self._autofill_btn = QPushButton("Auto-fill")
        self._autofill_btn.setToolTip("Type KeePass credentials into terminal")
        self._autofill_btn.setFixedHeight(22)
        self._autofill_btn.clicked.connect(self._show_autofill_menu)
        status_row.addWidget(self._autofill_btn)

        layout.addLayout(status_row)

        self._editor = _TerminalEdit(self)
        self._editor.setObjectName("terminal")
        self._editor.setReadOnly(True)
        self._editor.key_pressed.connect(self._on_key)
        self._editor.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._editor.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self._editor)

    # ------------------------------------------------------------------
    # Connection dispatch
    # ------------------------------------------------------------------

    def _start_connection(self) -> None:
        proto = self._session.protocol

        if proto == "rdp":
            self._launch_rdp()
            return
        if proto == "vnc":
            self._launch_vnc()
            return

        if proto == "telnet":
            self._start_telnet()
        else:
            self._start_ssh()

    def _start_ssh(self) -> None:
        self._thread = QThread(self)
        self._worker = SSHWorker(self._session, self._password)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.output.connect(self._append_ansi)
        self._worker.status.connect(self._on_status)
        self._worker.finished.connect(self._thread.quit)
        self._worker.transport_ready.connect(self._on_transport_ready)

        self._thread.start()

    def _start_telnet(self) -> None:
        self._thread = QThread(self)
        self._worker = TelnetWorker(self._session)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.output.connect(self._append_ansi)
        self._worker.status.connect(self._on_status)
        self._worker.finished.connect(self._thread.quit)

        self._thread.start()

    def _launch_rdp(self) -> None:
        s = self._session
        self._append_ansi(
            f"\r\n\033[36m[RDP]\033[0m  Launching RDP client for "
            f"{s.username}@{s.hostname}:{s.port}…\r\n"
        )
        try:
            if sys.platform.startswith("win"):
                cmd = ["mstsc", f"/v:{s.hostname}:{s.port}"]
            else:
                cmd = [
                    "xfreerdp",
                    f"/v:{s.hostname}:{s.port}",
                    f"/u:{s.username}",
                    f"/size:{s.rdp_width}x{s.rdp_height}",
                ]
                if s.rdp_fullscreen:
                    cmd.append("/f")
            subprocess.Popen(cmd)
            self._on_status("RDP client launched (external window)")
        except FileNotFoundError as exc:
            self._append_ansi(
                f"\r\n\033[31m[ERROR]\033[0m  RDP client not found: {exc}\r\n"
                "Install xfreerdp (Linux/macOS) or use mstsc (Windows).\r\n"
            )

    def _launch_vnc(self) -> None:
        s = self._session
        self._append_ansi(
            f"\r\n\033[36m[VNC]\033[0m  Launching VNC viewer for "
            f"{s.hostname}:{s.port}…\r\n"
        )
        try:
            subprocess.Popen(["vncviewer", f"{s.hostname}:{s.port}"])
            self._on_status("VNC client launched (external window)")
        except FileNotFoundError:
            self._append_ansi(
                "\r\n\033[31m[ERROR]\033[0m  vncviewer not found.\r\n"
                "Install tigervnc-viewer or a compatible VNC client.\r\n"
            )

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @Slot(object)
    def _on_transport_ready(self, transport) -> None:
        self._transport = transport
        self._sftp_btn.setEnabled(True)

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
        if self._recording:
            try:
                self._recorded_cmds.append(data.decode("utf-8", errors="replace"))
            except Exception:
                pass
        if hasattr(self, "_worker"):
            self._worker.send(data)

    # ------------------------------------------------------------------
    # SFTP
    # ------------------------------------------------------------------

    def _open_sftp(self) -> None:
        if self._transport is None:
            return
        from app.sftp.browser import SFTPBrowserWidget
        # Find parent tab widget and add the SFTP tab next to this one
        parent_tabs = self.parent()
        if hasattr(parent_tabs, "addTab"):
            sftp_widget = SFTPBrowserWidget(
                self._transport, self._session.name, parent=parent_tabs
            )
            idx = parent_tabs.addTab(sftp_widget, f"SFTP: {self._session.name}")
            parent_tabs.setCurrentIndex(idx)

    # ------------------------------------------------------------------
    # Macros
    # ------------------------------------------------------------------

    def _show_macro_menu(self) -> None:
        from app.macros.manager import macro_manager
        menu = QMenu(self)

        if self._recording:
            stop_act = menu.addAction("■  Stop Recording")
            stop_act.triggered.connect(self._stop_recording)
        else:
            rec_act = menu.addAction("●  Start Recording")
            rec_act.triggered.connect(self._start_recording)

        menu.addSeparator()

        names = macro_manager.names()
        if names:
            for name in names:
                act = menu.addAction(f"▶  {name}")
                act.triggered.connect(lambda _=False, n=name: self._play_macro(n))
            menu.addSeparator()

        mgr_act = menu.addAction("Manage Macros…")
        mgr_act.triggered.connect(self._open_macro_manager)

        menu.exec(self._macro_btn.mapToGlobal(
            self._macro_btn.rect().bottomLeft()
        ))

    def _start_recording(self) -> None:
        self._recorded_cmds = []
        self._recording = True
        self._macro_btn.setText("● REC")
        self._status_lbl.setText("Recording macro – type commands in the terminal…")

    def _stop_recording(self) -> None:
        self._recording = False
        self._macro_btn.setText("Macros")
        if self._recorded_cmds:
            from app.macros.dialog import MacroSaveDialog
            dlg = MacroSaveDialog(self._recorded_cmds, self)
            dlg.exec()
        else:
            self._status_lbl.setText("No commands recorded.")

    def _play_macro(self, name: str) -> None:
        from app.macros.manager import macro_manager
        cmds = macro_manager.get(name)
        self._play_commands(cmds)

    def _play_commands(self, cmds: list[str]) -> None:
        if hasattr(self, "_worker"):
            for cmd in cmds:
                self._worker.send(cmd.encode("utf-8"))

    def _open_macro_manager(self) -> None:
        from app.macros.dialog import MacroManagerDialog
        dlg = MacroManagerDialog(self, on_play=self._play_commands)
        dlg.exec()

    # ------------------------------------------------------------------
    # KeePass Auto-fill
    # ------------------------------------------------------------------

    def _show_autofill_menu(self) -> None:
        from app.managers.keepass import keepass_manager
        menu = QMenu(self)

        # In-terminal SSH autofill (send to channel)
        if self._session.keepass_entry_uuid and keepass_manager.is_open:
            entry = keepass_manager.get_entry_by_uuid(self._session.keepass_entry_uuid)
            if entry:
                u_act = menu.addAction(f"Send Username: {entry.username or '(none)'}")
                u_act.triggered.connect(
                    lambda: self._send_text(entry.username or "")
                )
                p_act = menu.addAction("Send Password")
                p_act.triggered.connect(
                    lambda: self._send_text(entry.password or "")
                )
                menu.addSeparator()

        # Global auto-type (pynput)
        menu.addAction("Global Auto-Type (pynput)…").triggered.connect(
            self._global_autotype
        )

        menu.exec(self._autofill_btn.mapToGlobal(
            self._autofill_btn.rect().bottomLeft()
        ))

    def _send_text(self, text: str) -> None:
        """Type text into the SSH channel (in-terminal autofill)."""
        if hasattr(self, "_worker") and text:
            self._worker.send(text.encode("utf-8"))

    def _global_autotype(self) -> None:
        """Simulate keystrokes in the focused window using pynput."""
        from app.managers.keepass import keepass_manager
        from app.managers.settings import settings_manager
        import time

        if not self._session.keepass_entry_uuid or not keepass_manager.is_open:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Auto-Type",
                "No KeePass entry linked to this session.",
            )
            return

        entry = keepass_manager.get_entry_by_uuid(self._session.keepass_entry_uuid)
        if not entry:
            return

        try:
            from pynput.keyboard import Controller, Key
        except ImportError:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Auto-Type",
                "pynput is not installed.\nRun: pip install pynput",
            )
            return

        delay = settings_manager.get("autotype_delay_ms", 50) / 1000.0
        kb = Controller()

        def _type(text: str) -> None:
            for ch in text:
                kb.press(ch)
                kb.release(ch)
                if delay > 0:
                    time.sleep(delay)

        sequence = f"{entry.username or ''}\t{entry.password or ''}\n"
        threading.Thread(target=lambda: _type(sequence), daemon=True).start()

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _on_context_menu(self, pos) -> None:
        menu = QMenu(self)
        menu.addAction(
            "Copy",
            lambda: self._editor.copy(),
        )
        menu.addSeparator()
        menu.addAction("Clear Terminal", self._editor.clear)
        menu.addSeparator()
        if self._recording:
            menu.addAction("■ Stop Recording Macro", self._stop_recording)
        else:
            menu.addAction("● Start Recording Macro", self._start_recording)
        menu.exec(self._editor.mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close_connection(self) -> None:
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
