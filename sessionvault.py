#!/usr/bin/env python3
"""
SessionVault - SSH Client with KeePass Integration

A MobaXterm-style SSH client with KeePass credential management.
Organized into clearly marked sections per architecture doc.
"""

# ===========================================================================
# IMPORTS
# ===========================================================================

import configparser
import dataclasses
import json
import os
import pathlib
import queue
import re
import threading
import tkinter as tk
import uuid
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Optional

try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False

try:
    from pykeepass import PyKeePass
    PYKEEPASS_AVAILABLE = True
except ImportError:
    PYKEEPASS_AVAILABLE = False


# ===========================================================================
# CONSTANTS
# ===========================================================================

APP_NAME = "SessionVault"
APP_VERSION = "1.0.0"
DATA_DIR = pathlib.Path.home() / ".sessionvault"
SESSIONS_FILE = DATA_DIR / "sessions.json"

# Catppuccin Mocha color scheme
COLORS = {
    "base":      "#1e1e2e",
    "mantle":    "#181825",
    "crust":     "#11111b",
    "surface0":  "#313244",
    "surface1":  "#45475a",
    "surface2":  "#585b70",
    "overlay0":  "#6c7086",
    "overlay1":  "#7f849c",
    "overlay2":  "#9399b2",
    "subtext0":  "#a6adc8",
    "subtext1":  "#bac2de",
    "text":      "#cdd6f4",
    "lavender":  "#b4befe",
    "blue":      "#89b4fa",
    "sapphire":  "#74c7ec",
    "sky":       "#89dceb",
    "teal":      "#94e2d5",
    "green":     "#a6e3a1",
    "yellow":    "#f9e2af",
    "peach":     "#fab387",
    "maroon":    "#eba0ac",
    "red":       "#f38ba8",
    "mauve":     "#cba6f7",
    "pink":      "#f5c2e7",
    "flamingo":  "#f2cdcd",
    "rosewater": "#f5e0dc",
}

# Standard 8/16 ANSI colors mapped to Catppuccin Mocha palette
ANSI_COLORS_8 = [
    "#45475a",  # 0  black        -> surface1
    "#f38ba8",  # 1  red          -> red
    "#a6e3a1",  # 2  green        -> green
    "#f9e2af",  # 3  yellow       -> yellow
    "#89b4fa",  # 4  blue         -> blue
    "#cba6f7",  # 5  magenta      -> mauve
    "#94e2d5",  # 6  cyan         -> teal
    "#cdd6f4",  # 7  white        -> text
    "#585b70",  # 8  bright black -> surface2
    "#f38ba8",  # 9  bright red
    "#a6e3a1",  # 10 bright green
    "#f9e2af",  # 11 bright yellow
    "#89b4fa",  # 12 bright blue
    "#cba6f7",  # 13 bright magenta
    "#94e2d5",  # 14 bright cyan
    "#cdd6f4",  # 15 bright white
]

# Cache for 256-color lookups
_ANSI_256_CACHE: dict[int, str] = {}


# ===========================================================================
# DATA MODELS
# ===========================================================================

@dataclasses.dataclass
class SSHSessionConfig:
    """Persistent configuration for a single SSH session."""
    name: str
    hostname: str
    port: int = 22
    username: str = ""
    key_path: str = ""
    keepass_entry_uuid: str = ""
    folder: str = ""
    id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SSHSessionConfig":
        valid_fields = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in valid_fields})


# ===========================================================================
# KEEPASS MANAGER SECTION
# ===========================================================================

class KeePassManager:
    """Thread-safe KeePass database manager."""

    def __init__(self):
        self._db: Optional["PyKeePass"] = None
        self._lock = threading.Lock()
        self._db_path: str = ""

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._db is not None

    @property
    def db_path(self) -> str:
        return self._db_path

    def open(self, path: str, password: str, keyfile: str = "") -> None:
        if not PYKEEPASS_AVAILABLE:
            raise RuntimeError("pykeepass is not installed. Run: pip install pykeepass")
        with self._lock:
            self._db = PyKeePass(
                path,
                password=password or None,
                keyfile=keyfile or None,
            )
            self._db_path = path

    def lock(self) -> None:
        with self._lock:
            self._db = None
            self._db_path = ""

    def get_all_entries(self) -> list:
        with self._lock:
            if self._db is None:
                return []
            return list(self._db.entries)

    def get_entry_by_uuid(self, uuid_str: str):
        with self._lock:
            if self._db is None:
                return None
            try:
                target = uuid.UUID(uuid_str)
                for entry in self._db.entries:
                    if entry.uuid == target:
                        return entry
            except Exception:
                pass
            return None

    def get_password_for_session(self, session: SSHSessionConfig) -> Optional[str]:
        if not session.keepass_entry_uuid:
            return None
        entry = self.get_entry_by_uuid(session.keepass_entry_uuid)
        return entry.password if entry else None


# Global singleton
keepass_manager = KeePassManager()


# ===========================================================================
# MOBAXTERM IMPORTER SECTION
# ===========================================================================

class MobaXtermImporter:
    """
    Parser for MobaXterm .mxtsessions files.

    File format (INI-style):
        [Bookmarks]
        SubRep=
        ImgNum=42
        SessionName=#SessionType#Server#Port#Username#...

    SSH session type = 0.  Other types (RDP=4, etc.) are skipped.
    Folder sections map to the SSHSessionConfig.folder field.
    """

    SSH_TYPE = "0"

    @classmethod
    def parse_file(cls, path: str) -> list[SSHSessionConfig]:
        sessions: list[SSHSessionConfig] = []
        config = configparser.RawConfigParser()
        config.read(path, encoding="utf-8-sig")

        for section in config.sections():
            # Top-level "Bookmarks" section has no folder; sub-sections become folders
            folder = "" if section in ("Bookmarks", "Bookmarks_0") else section
            for key, value in config.items(section):
                if key.lower() in ("subrep", "imgnum"):
                    continue
                parsed = cls._parse_line(key, value, folder)
                if parsed:
                    sessions.append(parsed)
        return sessions

    @classmethod
    def _parse_line(
        cls, name: str, value: str, folder: str
    ) -> Optional[SSHSessionConfig]:
        if not value.startswith("#"):
            return None
        parts = value.split("#")
        # parts[0] is always empty (text before leading '#')
        if len(parts) < 2:
            return None
        session_type = parts[1]
        if session_type != cls.SSH_TYPE:
            return None
        hostname = parts[2] if len(parts) > 2 else ""
        port_str = parts[3] if len(parts) > 3 else "22"
        username = parts[4] if len(parts) > 4 else ""
        try:
            port = int(port_str)
        except ValueError:
            port = 22
        return SSHSessionConfig(
            name=name,
            hostname=hostname,
            port=port,
            username=username,
            folder=folder,
        )


# ===========================================================================
# SESSION MANAGER SECTION
# ===========================================================================

class SessionManager:
    """CRUD operations and JSON persistence for SSH sessions."""

    def __init__(self):
        self._sessions: list[SSHSessionConfig] = []
        self._load()

    # --- Persistence ---

    def _load(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if SESSIONS_FILE.exists():
            try:
                with open(SESSIONS_FILE, "r", encoding="utf-8") as fh:
                    raw = json.load(fh)
                self._sessions = [SSHSessionConfig.from_dict(d) for d in raw]
            except Exception:
                self._sessions = []

    def _save(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(SESSIONS_FILE, "w", encoding="utf-8") as fh:
            json.dump([s.to_dict() for s in self._sessions], fh, indent=2)

    # --- CRUD ---

    def all(self) -> list[SSHSessionConfig]:
        return list(self._sessions)

    def add(self, session: SSHSessionConfig) -> None:
        self._sessions.append(session)
        self._save()

    def update(self, session: SSHSessionConfig) -> None:
        for i, s in enumerate(self._sessions):
            if s.id == session.id:
                self._sessions[i] = session
                self._save()
                return

    def delete(self, session_id: str) -> None:
        self._sessions = [s for s in self._sessions if s.id != session_id]
        self._save()

    def import_sessions(self, sessions: list[SSHSessionConfig]) -> int:
        """Add sessions that don't already exist (deduplicated by host+port+user).
        Returns number of newly added sessions."""
        existing = {(s.hostname, s.port, s.username) for s in self._sessions}
        added = 0
        for s in sessions:
            key = (s.hostname, s.port, s.username)
            if key not in existing:
                self._sessions.append(s)
                existing.add(key)
                added += 1
        self._save()
        return added


# ===========================================================================
# SSH TERMINAL WIDGET SECTION
# ===========================================================================

class AnsiParser:
    """
    Stream parser for ANSI/VT escape sequences.

    Converts a string containing ANSI escapes into a list of
    (text, tag_name) tuples suitable for insertion into a
    tkinter.Text widget.
    """

    # Matches CSI (ESC[) sequences
    _CSI_RE = re.compile(r"\x1b\[([0-9;]*)([A-Za-z])")
    # Matches any other ESC sequence (to strip it)
    _ESC_RE = re.compile(r"\x1b[^\x1b]*?(?=[^x1b]|$)")

    def __init__(self):
        self._fg: Optional[str] = None
        self._bg: Optional[str] = None
        self._bold = False
        self._underline = False

    # --- Public API ---

    def feed(self, data: str) -> list[tuple[str, Optional[str]]]:
        """Return list of (text, tag_name) pairs ready for Text.insert()."""
        results: list[tuple[str, Optional[str]]] = []
        pos = 0
        for m in self._CSI_RE.finditer(data):
            start, end = m.span()
            if start > pos:
                chunk = self._strip_esc(data[pos:start])
                if chunk:
                    results.append((chunk, self._current_tag()))
            self._handle_csi(m.group(1), m.group(2))
            pos = end
        if pos < len(data):
            chunk = self._strip_esc(data[pos:])
            if chunk:
                results.append((chunk, self._current_tag()))
        return results

    # --- Internal helpers ---

    def _strip_esc(self, text: str) -> str:
        return self._ESC_RE.sub("", text)

    def _current_tag(self) -> Optional[str]:
        parts = []
        if self._fg:
            parts.append(f"fg:{self._fg}")
        if self._bg:
            parts.append(f"bg:{self._bg}")
        if self._bold:
            parts.append("bold")
        if self._underline:
            parts.append("underline")
        return "|".join(parts) if parts else None

    def _handle_csi(self, params_str: str, command: str) -> None:
        if command == "m":
            self._handle_sgr(params_str)
        # Other CSI commands (cursor movement, erase, etc.) are intentionally ignored

    def _handle_sgr(self, params_str: str) -> None:
        if not params_str:
            params = [0]
        else:
            try:
                params = [int(p) if p else 0 for p in params_str.split(";")]
            except ValueError:
                return

        i = 0
        while i < len(params):
            p = params[i]
            if p == 0:
                self._fg = self._bg = None
                self._bold = self._underline = False
            elif p == 1:
                self._bold = True
            elif p == 4:
                self._underline = True
            elif p == 22:
                self._bold = False
            elif p == 24:
                self._underline = False
            elif p == 39:
                self._fg = None
            elif p == 49:
                self._bg = None
            elif 30 <= p <= 37:
                self._fg = ANSI_COLORS_8[p - 30]
            elif 40 <= p <= 47:
                self._bg = ANSI_COLORS_8[p - 40]
            elif 90 <= p <= 97:
                self._fg = ANSI_COLORS_8[p - 90 + 8]
            elif 100 <= p <= 107:
                self._bg = ANSI_COLORS_8[p - 100 + 8]
            elif p in (38, 48) and i + 2 < len(params) and params[i + 1] == 5:
                color = _ansi_256_color(params[i + 2])
                if p == 38:
                    self._fg = color
                else:
                    self._bg = color
                i += 2
            elif p in (38, 48) and i + 4 < len(params) and params[i + 1] == 2:
                r, g, b = params[i + 2], params[i + 3], params[i + 4]
                color = f"#{r:02x}{g:02x}{b:02x}"
                if p == 38:
                    self._fg = color
                else:
                    self._bg = color
                i += 4
            i += 1


def _ansi_256_color(n: int) -> str:
    """Convert a 256-color index to a hex color string."""
    if n in _ANSI_256_CACHE:
        return _ANSI_256_CACHE[n]
    if n < 16:
        color = ANSI_COLORS_8[n]
    elif n < 232:
        n -= 16
        b = n % 6
        g = (n // 6) % 6
        r = (n // 36) % 6
        def c(x: int) -> int:
            return 0 if x == 0 else 55 + x * 40
        color = f"#{c(r):02x}{c(g):02x}{c(b):02x}"
    else:
        v = 8 + (n - 232) * 10
        color = f"#{v:02x}{v:02x}{v:02x}"
    _ANSI_256_CACHE[n] = color
    return color


class SSHTerminalWidget(tk.Frame):
    """
    A self-contained tkinter widget that opens an SSH connection and
    renders the interactive shell with ANSI color support.
    """

    _READ_CHUNK = 4096
    _POLL_MS = 50

    def __init__(
        self,
        parent: tk.Widget,
        session: SSHSessionConfig,
        password: Optional[str] = None,
    ):
        super().__init__(parent, bg=COLORS["base"])
        self._session = session
        self._password = password
        self._ssh: Optional["paramiko.SSHClient"] = None
        self._channel: Optional["paramiko.Channel"] = None
        self._running = False
        self._queue: queue.Queue = queue.Queue()
        self._ansi = AnsiParser()
        self._defined_tags: set[str] = set()

        self._build_ui()
        self._start_connection()

    # --- UI ---

    def _build_ui(self) -> None:
        self._status_var = tk.StringVar(value="Connecting…")
        tk.Label(
            self,
            textvariable=self._status_var,
            bg=COLORS["surface0"],
            fg=COLORS["subtext0"],
            anchor="w",
            padx=8,
            pady=2,
            font=("Monospace", 9),
        ).pack(side=tk.TOP, fill=tk.X)

        frame = tk.Frame(self, bg=COLORS["base"])
        frame.pack(fill=tk.BOTH, expand=True)

        sb = tk.Scrollbar(frame)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        self._text = tk.Text(
            frame,
            bg=COLORS["base"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            font=("Monospace", 11),
            wrap=tk.WORD,
            yscrollcommand=sb.set,
            state=tk.DISABLED,
            cursor="xterm",
            relief=tk.FLAT,
        )
        self._text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=self._text.yview)

        # Built-in style tags
        self._text.tag_configure("bold", font=("Monospace", 11, "bold"))
        self._text.tag_configure("underline", underline=True)
        self._text.tag_configure("error", foreground=COLORS["red"])

        self._text.bind("<Key>", self._on_key)
        self._text.bind("<Return>", self._on_return)
        self._text.bind("<BackSpace>", self._on_backspace)
        self._text.focus_set()

    def _ensure_tag(self, tag: str) -> None:
        if tag in self._defined_tags:
            return
        self._defined_tags.add(tag)
        kwargs: dict = {}
        for part in tag.split("|"):
            if part.startswith("fg:"):
                kwargs["foreground"] = part[3:]
            elif part.startswith("bg:"):
                kwargs["background"] = part[3:]
            elif part == "bold":
                kwargs["font"] = ("Monospace", 11, "bold")
            elif part == "underline":
                kwargs["underline"] = True
        self._text.tag_configure(tag, **kwargs)

    # --- Connection ---

    def _start_connection(self) -> None:
        if not PARAMIKO_AVAILABLE:
            self._append_text(
                "[ERROR] paramiko is not installed.\nRun: pip install paramiko\n",
                "error",
            )
            self._status_var.set("Error – paramiko missing")
            return
        self._running = True
        threading.Thread(target=self._connect_thread, daemon=True).start()
        self._schedule_poll()

    def _connect_thread(self) -> None:
        host = self._session.hostname
        port = self._session.port
        try:
            self._queue.put(("status", f"Connecting to {host}:{port}…"))
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
            self._queue.put(("status", f"Connected – {self._session.username}@{host}"))
            self._read_loop()
        except Exception as exc:
            self._queue.put(("status", f"Error: {exc}"))
            self._queue.put(("text", f"\n[ERROR] {exc}\n", "error"))
            self._running = False

    def _read_loop(self) -> None:
        import select as _select
        while self._running and self._channel and not self._channel.closed:
            try:
                ready, _, _ = _select.select([self._channel], [], [], 0.05)
                if ready:
                    data = self._channel.recv(self._READ_CHUNK)
                    if data:
                        self._queue.put(("data", data.decode("utf-8", errors="replace")))
                    else:
                        break
            except Exception:
                break
        self._running = False
        self._queue.put(("status", "Disconnected"))

    # --- Polling / rendering ---

    def _schedule_poll(self) -> None:
        if not self.winfo_exists():
            return
        self._drain_queue()
        if self._running or not self._queue.empty():
            self.after(self._POLL_MS, self._schedule_poll)

    def _drain_queue(self) -> None:
        try:
            while True:
                item = self._queue.get_nowait()
                kind = item[0]
                if kind == "status":
                    self._status_var.set(item[1])
                elif kind == "data":
                    self._render_ansi(item[1])
                elif kind == "text":
                    tag = item[2] if len(item) > 2 else None
                    self._append_text(item[1], tag)
        except queue.Empty:
            pass

    def _render_ansi(self, data: str) -> None:
        chunks = self._ansi.feed(data)
        self._text.config(state=tk.NORMAL)
        for text, tag in chunks:
            if tag:
                self._ensure_tag(tag)
                self._text.insert(tk.END, text, tag)
            else:
                self._text.insert(tk.END, text)
        self._text.see(tk.END)
        self._text.config(state=tk.DISABLED)

    def _append_text(self, text: str, tag: Optional[str] = None) -> None:
        self._text.config(state=tk.NORMAL)
        if tag:
            self._text.insert(tk.END, text, tag)
        else:
            self._text.insert(tk.END, text)
        self._text.see(tk.END)
        self._text.config(state=tk.DISABLED)

    # --- Key handling ---

    def _on_key(self, event: tk.Event) -> str:
        if not self._channel or self._channel.closed:
            return "break"
        char = event.char
        if char and event.keysym not in ("Return", "BackSpace"):
            try:
                self._channel.send(char.encode("utf-8"))
            except Exception:
                pass
        return "break"

    def _on_return(self, event: tk.Event) -> str:
        if self._channel and not self._channel.closed:
            try:
                self._channel.send(b"\r\n")
            except Exception:
                pass
        return "break"

    def _on_backspace(self, event: tk.Event) -> str:
        if self._channel and not self._channel.closed:
            try:
                self._channel.send(b"\x7f")
            except Exception:
                pass
        return "break"

    # --- Lifecycle ---

    def close(self) -> None:
        self._running = False
        for obj in (self._channel, self._ssh):
            if obj:
                try:
                    obj.close()
                except Exception:
                    pass


# ===========================================================================
# DIALOG CLASSES
# ===========================================================================

class _ThemedDialog(tk.Toplevel):
    """Base class providing consistent dark-theme helpers."""

    def _lbl(self, parent: tk.Widget, text: str) -> tk.Label:
        return tk.Label(
            parent, text=text, bg=COLORS["base"], fg=COLORS["subtext0"],
            anchor="w", font=("Sans", 10),
        )

    def _ent(self, parent: tk.Widget, **kw) -> tk.Entry:
        return tk.Entry(
            parent, bg=COLORS["surface0"], fg=COLORS["text"],
            insertbackground=COLORS["text"], relief=tk.FLAT,
            font=("Monospace", 10), **kw,
        )

    def _btn(self, parent: tk.Widget, text: str, command, accent=False) -> tk.Button:
        if accent:
            return tk.Button(
                parent, text=text, command=command,
                bg=COLORS["blue"], fg=COLORS["base"],
                relief=tk.FLAT, padx=10, font=("Sans", 10, "bold"),
            )
        return tk.Button(
            parent, text=text, command=command,
            bg=COLORS["surface1"], fg=COLORS["text"],
            relief=tk.FLAT, padx=10,
        )


class NewSessionDialog(_ThemedDialog):
    """Dialog for creating or editing an SSH session."""

    def __init__(self, parent: tk.Widget, session: Optional[SSHSessionConfig] = None):
        super().__init__(parent)
        self.title("New SSH Session" if session is None else "Edit Session")
        self.configure(bg=COLORS["base"])
        self.resizable(False, False)
        self.result: Optional[SSHSessionConfig] = None
        self._session = session
        self._kp_uuid = session.keepass_entry_uuid if session else ""
        self._kp_label_var = tk.StringVar(value="None")
        self._build_ui()
        self._populate(session)
        self.grab_set()
        self.wait_window()

    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 4}
        ew = {"sticky": "ew"}

        f = tk.Frame(self, bg=COLORS["base"], padx=16, pady=14)
        f.pack(fill=tk.BOTH, expand=True)
        f.columnconfigure(1, weight=1)

        def row_entry(row: int, label: str, var: tk.StringVar, **kw) -> None:
            self._lbl(f, label).grid(row=row, column=0, **pad, **ew)
            self._ent(f, textvariable=var, **kw).grid(row=row, column=1, **pad, **ew)

        r = 0
        self._name_var = tk.StringVar()
        row_entry(r, "Session Name", self._name_var, width=38); r += 1

        self._host_var = tk.StringVar()
        row_entry(r, "Hostname / IP", self._host_var); r += 1

        self._port_var = tk.StringVar(value="22")
        self._lbl(f, "Port").grid(row=r, column=0, **pad, **ew)
        self._ent(f, textvariable=self._port_var, width=8).grid(
            row=r, column=1, **pad, sticky="w"); r += 1

        self._user_var = tk.StringVar()
        row_entry(r, "Username", self._user_var); r += 1

        # Private key row with Browse button
        self._lbl(f, "Private Key Path").grid(row=r, column=0, **pad, **ew)
        kf = tk.Frame(f, bg=COLORS["base"]); kf.grid(row=r, column=1, **pad, **ew)
        kf.columnconfigure(0, weight=1)
        self._key_var = tk.StringVar()
        self._ent(kf, textvariable=self._key_var).grid(row=0, column=0, sticky="ew")
        self._btn(kf, "Browse", self._browse_key).grid(row=0, column=1, padx=(4, 0))
        r += 1

        self._folder_var = tk.StringVar()
        row_entry(r, "Folder", self._folder_var); r += 1

        # KeePass entry row
        self._lbl(f, "KeePass Entry").grid(row=r, column=0, **pad, **ew)
        kp = tk.Frame(f, bg=COLORS["base"]); kp.grid(row=r, column=1, **pad, **ew)
        kp.columnconfigure(0, weight=1)
        tk.Label(
            kp, textvariable=self._kp_label_var,
            bg=COLORS["surface0"], fg=COLORS["text"],
            anchor="w", padx=6, width=26, font=("Monospace", 10),
        ).grid(row=0, column=0, sticky="ew")
        self._btn(kp, "Select Entry", self._select_kp).grid(row=0, column=1, padx=(4, 0))
        self._btn(kp, "Clear", self._clear_kp).grid(row=0, column=2, padx=(4, 0))
        r += 1

        # Action buttons
        bf = tk.Frame(f, bg=COLORS["base"])
        bf.grid(row=r, column=0, columnspan=2, pady=(12, 0), sticky="e")
        self._btn(bf, "Cancel", self.destroy).pack(side=tk.RIGHT, padx=(6, 0))
        self._btn(bf, "Save", self._save, accent=True).pack(side=tk.RIGHT)

    def _populate(self, s: Optional[SSHSessionConfig]) -> None:
        if s is None:
            return
        self._name_var.set(s.name)
        self._host_var.set(s.hostname)
        self._port_var.set(str(s.port))
        self._user_var.set(s.username)
        self._key_var.set(s.key_path)
        self._folder_var.set(s.folder)
        if s.keepass_entry_uuid:
            entry = keepass_manager.get_entry_by_uuid(s.keepass_entry_uuid)
            if entry:
                self._kp_label_var.set(entry.title or "Unknown")
            else:
                self._kp_label_var.set(f"UUID:{s.keepass_entry_uuid[:8]}…")

    def _browse_key(self) -> None:
        path = filedialog.askopenfilename(
            parent=self, title="Select Private Key",
            filetypes=[("All files", "*"), ("PEM files", "*.pem")],
        )
        if path:
            self._key_var.set(path)

    def _select_kp(self) -> None:
        if not keepass_manager.is_open:
            messagebox.showwarning(
                "KeePass",
                "No KeePass database is open.\nOpen one via Tools → Open KeePass Database…",
                parent=self,
            )
            return
        dlg = KeePassSelectorDialog(self)
        if dlg.selected_entry is not None:
            self._kp_uuid = str(dlg.selected_entry.uuid)
            self._kp_label_var.set(dlg.selected_entry.title or "Unknown")

    def _clear_kp(self) -> None:
        self._kp_uuid = ""
        self._kp_label_var.set("None")

    def _save(self) -> None:
        name = self._name_var.get().strip()
        host = self._host_var.get().strip()
        if not name:
            messagebox.showerror("Validation", "Session name is required.", parent=self)
            return
        if not host:
            messagebox.showerror("Validation", "Hostname is required.", parent=self)
            return
        try:
            port = int(self._port_var.get())
        except ValueError:
            messagebox.showerror("Validation", "Port must be a number.", parent=self)
            return
        if self._session:
            self._session.name = name
            self._session.hostname = host
            self._session.port = port
            self._session.username = self._user_var.get().strip()
            self._session.key_path = self._key_var.get().strip()
            self._session.folder = self._folder_var.get().strip()
            self._session.keepass_entry_uuid = self._kp_uuid
            self.result = self._session
        else:
            self.result = SSHSessionConfig(
                name=name,
                hostname=host,
                port=port,
                username=self._user_var.get().strip(),
                key_path=self._key_var.get().strip(),
                folder=self._folder_var.get().strip(),
                keepass_entry_uuid=self._kp_uuid,
            )
        self.destroy()


class KeePassSelectorDialog(_ThemedDialog):
    """Browse and select a KeePass entry."""

    def __init__(self, parent: tk.Widget):
        super().__init__(parent)
        self.title("Select KeePass Entry")
        self.configure(bg=COLORS["base"])
        self.geometry("520x420")
        self.selected_entry = None
        self._all_entries: list = []
        self._build_ui()
        self._populate()
        self.grab_set()
        self.wait_window()

    def _build_ui(self) -> None:
        # Search bar
        sf = tk.Frame(self, bg=COLORS["base"], padx=8, pady=8)
        sf.pack(fill=tk.X)
        tk.Label(sf, text="Search:", bg=COLORS["base"], fg=COLORS["subtext0"]).pack(side=tk.LEFT)
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._filter())
        self._ent(sf, textvariable=self._search_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0)
        )

        # Listbox
        lf = tk.Frame(self, bg=COLORS["base"], padx=8)
        lf.pack(fill=tk.BOTH, expand=True)
        sb = tk.Scrollbar(lf); sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._listbox = tk.Listbox(
            lf, bg=COLORS["surface0"], fg=COLORS["text"],
            selectbackground=COLORS["blue"], selectforeground=COLORS["base"],
            font=("Monospace", 10), relief=tk.FLAT, yscrollcommand=sb.set,
        )
        self._listbox.pack(fill=tk.BOTH, expand=True)
        sb.config(command=self._listbox.yview)
        self._listbox.bind("<Double-Button-1>", self._confirm)

        # Buttons
        bf = tk.Frame(self, bg=COLORS["base"], padx=8, pady=8)
        bf.pack(fill=tk.X)
        self._btn(bf, "Cancel", self.destroy).pack(side=tk.RIGHT, padx=(6, 0))
        self._btn(bf, "Select", self._confirm, accent=True).pack(side=tk.RIGHT)

    def _populate(self) -> None:
        self._all_entries = keepass_manager.get_all_entries()
        self._render(self._all_entries)

    def _render(self, entries: list) -> None:
        self._listbox.delete(0, tk.END)
        for e in entries:
            group = e.group.name if e.group else ""
            label = f"{group} / {e.title or ''}"
            if e.username:
                label += f"  [{e.username}]"
            self._listbox.insert(tk.END, label)

    def _filter(self) -> None:
        q = self._search_var.get().lower()
        if not q:
            self._render(self._all_entries)
            return
        self._render([
            e for e in self._all_entries
            if q in (e.title or "").lower()
            or q in (e.username or "").lower()
            or q in (e.group.name if e.group else "").lower()
        ])

    def _current_filtered(self) -> list:
        q = self._search_var.get().lower()
        if not q:
            return self._all_entries
        return [
            e for e in self._all_entries
            if q in (e.title or "").lower()
            or q in (e.username or "").lower()
            or q in (e.group.name if e.group else "").lower()
        ]

    def _confirm(self, _event=None) -> None:
        sel = self._listbox.curselection()
        if not sel:
            return
        filtered = self._current_filtered()
        idx = sel[0]
        if idx < len(filtered):
            self.selected_entry = filtered[idx]
        self.destroy()


class KeePassOpenDialog(_ThemedDialog):
    """Dialog for unlocking a .kdbx file."""

    def __init__(self, parent: tk.Widget):
        super().__init__(parent)
        self.title("Open KeePass Database")
        self.configure(bg=COLORS["base"])
        self.resizable(False, False)
        self.success = False
        self._build_ui()
        self.grab_set()
        self.wait_window()

    def _build_ui(self) -> None:
        f = tk.Frame(self, bg=COLORS["base"], padx=16, pady=14)
        f.pack(fill=tk.BOTH, expand=True)
        f.columnconfigure(1, weight=1)
        pad = {"padx": 8, "pady": 5}

        def browse_row(row: int, label: str, var: tk.StringVar, title: str, ftypes: list) -> None:
            self._lbl(f, label).grid(row=row, column=0, **pad, sticky="w")
            rf = tk.Frame(f, bg=COLORS["base"])
            rf.grid(row=row, column=1, **pad, sticky="ew")
            rf.columnconfigure(0, weight=1)
            self._ent(rf, textvariable=var, width=36).grid(row=0, column=0, sticky="ew")
            self._btn(
                rf, "Browse",
                lambda: var.set(filedialog.askopenfilename(
                    parent=self, title=title, filetypes=ftypes
                ) or var.get()),
            ).grid(row=0, column=1, padx=(4, 0))

        self._db_var = tk.StringVar()
        browse_row(
            0, "Database (.kdbx)", self._db_var,
            "Select KeePass Database",
            [("KeePass files", "*.kdbx"), ("All files", "*")],
        )

        self._kf_var = tk.StringVar()
        browse_row(
            1, "Key File (optional)", self._kf_var,
            "Select Key File",
            [("All files", "*"), ("Key files", "*.key")],
        )

        self._lbl(f, "Master Password").grid(row=2, column=0, **pad, sticky="w")
        self._pw_var = tk.StringVar()
        self._ent(f, textvariable=self._pw_var, show="*").grid(
            row=2, column=1, **pad, sticky="ew"
        )

        bf = tk.Frame(f, bg=COLORS["base"])
        bf.grid(row=3, column=0, columnspan=2, pady=(12, 0), sticky="e")
        self._btn(bf, "Cancel", self.destroy).pack(side=tk.RIGHT, padx=(6, 0))
        self._btn(
            bf, "Open", self._open,
            accent=True,  # blue accent replaced with green below
        ).pack(side=tk.RIGHT)
        # Patch the accent button to use green
        for w in bf.winfo_children():
            if isinstance(w, tk.Button) and w["text"] == "Open":
                w.config(bg=COLORS["green"])

        self.bind("<Return>", lambda _e: self._open())

    def _open(self) -> None:
        db_path = self._db_var.get().strip()
        if not db_path:
            messagebox.showerror("Error", "Please select a KeePass database file.", parent=self)
            return
        try:
            keepass_manager.open(db_path, self._pw_var.get(), self._kf_var.get().strip())
            self.success = True
            self.destroy()
        except Exception as exc:
            messagebox.showerror("Could Not Open Database", str(exc), parent=self)


# ===========================================================================
# MAIN APPLICATION
# ===========================================================================

class SessionVaultApp(tk.Tk):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1280x800")
        self.configure(bg=COLORS["base"])
        self.minsize(800, 500)

        self._session_mgr = SessionManager()
        self._terminals: dict[str, SSHTerminalWidget] = {}  # session_id -> widget

        self._configure_ttk_style()
        self._build_ui()
        self._refresh_session_tree()
        self._refresh_kp_panel()

    # --- TTK Style ---

    def _configure_ttk_style(self) -> None:
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(
            "Treeview",
            background=COLORS["mantle"],
            foreground=COLORS["text"],
            fieldbackground=COLORS["mantle"],
            borderwidth=0,
            rowheight=26,
            font=("Monospace", 10),
        )
        s.configure(
            "Treeview.Heading",
            background=COLORS["surface0"],
            foreground=COLORS["subtext0"],
            borderwidth=0,
        )
        s.map(
            "Treeview",
            background=[("selected", COLORS["blue"])],
            foreground=[("selected", COLORS["base"])],
        )
        s.configure(
            "TNotebook",
            background=COLORS["crust"],
            borderwidth=0,
        )
        s.configure(
            "TNotebook.Tab",
            background=COLORS["surface0"],
            foreground=COLORS["subtext0"],
            padding=(10, 4),
        )
        s.map(
            "TNotebook.Tab",
            background=[("selected", COLORS["base"])],
            foreground=[("selected", COLORS["text"])],
        )

    # --- UI construction ---

    def _build_ui(self) -> None:
        self._build_menu()

        # Horizontal pane: left sidebar + right terminal area
        paned = tk.PanedWindow(
            self, orient=tk.HORIZONTAL,
            bg=COLORS["surface1"], sashwidth=4, sashrelief=tk.FLAT,
        )
        paned.pack(fill=tk.BOTH, expand=True)

        paned.add(self._build_sidebar(paned), minsize=180, width=240)

        right = tk.Frame(paned, bg=COLORS["base"])
        paned.add(right, minsize=400)

        self._notebook = ttk.Notebook(right)
        self._notebook.pack(fill=tk.BOTH, expand=True)
        self._notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # Bottom status bar
        self._status_lbl = tk.Label(
            self, text=f"{APP_NAME} ready.", anchor="w", padx=8,
            bg=COLORS["mantle"], fg=COLORS["subtext0"], font=("Sans", 9),
        )
        self._status_lbl.pack(side=tk.BOTTOM, fill=tk.X)

    def _build_sidebar(self, parent: tk.Widget) -> tk.Frame:
        sidebar = tk.Frame(parent, bg=COLORS["mantle"])

        # App title header
        hdr = tk.Frame(sidebar, bg=COLORS["crust"], pady=6, padx=8)
        hdr.pack(fill=tk.X)
        tk.Label(
            hdr, text=APP_NAME, bg=COLORS["crust"], fg=COLORS["mauve"],
            font=("Sans", 13, "bold"),
        ).pack(side=tk.LEFT)

        # -- Sessions section --
        sh = tk.Frame(sidebar, bg=COLORS["surface0"], pady=4, padx=8)
        sh.pack(fill=tk.X)
        tk.Label(
            sh, text="SSH SESSIONS", bg=COLORS["surface0"],
            fg=COLORS["overlay1"], font=("Sans", 8),
        ).pack(side=tk.LEFT)
        tk.Button(
            sh, text="+", command=self._new_session,
            bg=COLORS["surface0"], fg=COLORS["green"],
            relief=tk.FLAT, font=("Sans", 12, "bold"), padx=4, pady=0,
        ).pack(side=tk.RIGHT)

        sf = tk.Frame(sidebar, bg=COLORS["mantle"])
        sf.pack(fill=tk.BOTH, expand=True)
        ssb = tk.Scrollbar(sf); ssb.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree = ttk.Treeview(
            sf, show="tree", yscrollcommand=ssb.set, selectmode="browse",
        )
        self._tree.pack(fill=tk.BOTH, expand=True)
        ssb.config(command=self._tree.yview)
        self._tree.bind("<Double-Button-1>", self._on_tree_double_click)
        self._tree.bind("<Button-3>", self._on_tree_right_click)

        # -- KeePass section --
        kh = tk.Frame(sidebar, bg=COLORS["surface0"], pady=4, padx=8)
        kh.pack(fill=tk.X)
        tk.Label(
            kh, text="KEEPASS", bg=COLORS["surface0"],
            fg=COLORS["overlay1"], font=("Sans", 8),
        ).pack(side=tk.LEFT)

        kf = tk.Frame(sidebar, bg=COLORS["mantle"])
        kf.pack(fill=tk.BOTH)
        ksb = tk.Scrollbar(kf); ksb.pack(side=tk.RIGHT, fill=tk.Y)
        self._kp_list = tk.Listbox(
            kf, bg=COLORS["mantle"], fg=COLORS["text"],
            selectbackground=COLORS["mauve"], selectforeground=COLORS["base"],
            font=("Monospace", 9), relief=tk.FLAT, height=8,
            yscrollcommand=ksb.set,
        )
        self._kp_list.pack(fill=tk.BOTH, expand=True)
        ksb.config(command=self._kp_list.yview)
        self._kp_list.bind("<Button-3>", self._on_kp_right_click)

        return sidebar

    def _build_menu(self) -> None:
        def _menu(**kw) -> tk.Menu:
            return tk.Menu(
                self, bg=COLORS["surface0"], fg=COLORS["text"],
                activebackground=COLORS["blue"], activeforeground=COLORS["base"],
                relief=tk.FLAT, tearoff=False, **kw,
            )

        bar = _menu()

        file_m = _menu()
        file_m.add_command(label="New SSH Session\tCtrl+T", command=self._new_session)
        file_m.add_command(label="Import MobaXterm Sessions…", command=self._import_mobaxterm)
        file_m.add_separator()
        file_m.add_command(label="Quit\tCtrl+Q", command=self.quit)
        bar.add_cascade(label="File", menu=file_m)

        tools_m = _menu()
        tools_m.add_command(label="Open KeePass Database…", command=self._open_keepass)
        tools_m.add_command(label="Lock KeePass Database", command=self._lock_keepass)
        bar.add_cascade(label="Tools", menu=tools_m)

        self.config(menu=bar)

        self.bind_all("<Control-t>", lambda _e: self._new_session())
        self.bind_all("<Control-w>", lambda _e: self._close_current_tab())
        self.bind_all("<Control-q>", lambda _e: self.quit())

    # --- Session tree ---

    def _refresh_session_tree(self) -> None:
        self._tree.delete(*self._tree.get_children())
        folders: dict[str, str] = {}
        for s in self._session_mgr.all():
            if s.folder:
                if s.folder not in folders:
                    fid = self._tree.insert(
                        "", tk.END, text=f"\U0001F4C1 {s.folder}", open=True
                    )
                    folders[s.folder] = fid
                parent = folders[s.folder]
            else:
                parent = ""
            self._tree.insert(parent, tk.END, iid=s.id, text=f"  {s.name}", values=(s.id,))

    def _on_tree_double_click(self, event: tk.Event) -> None:
        item = self._tree.identify_row(event.y)
        if item:
            session = self._find_session(item)
            if session:
                self._connect(session)

    def _on_tree_right_click(self, event: tk.Event) -> None:
        item = self._tree.identify_row(event.y)
        if not item:
            return
        self._tree.selection_set(item)
        session = self._find_session(item)
        if not session:
            return
        m = tk.Menu(
            self, tearoff=False,
            bg=COLORS["surface0"], fg=COLORS["text"],
            activebackground=COLORS["blue"], activeforeground=COLORS["base"],
        )
        m.add_command(label="Connect", command=lambda: self._connect(session))
        m.add_command(label="Edit…", command=lambda: self._edit_session(session))
        m.add_separator()
        m.add_command(label="Delete", command=lambda: self._delete_session(session))
        m.tk_popup(event.x_root, event.y_root)

    def _find_session(self, item_id: str) -> Optional[SSHSessionConfig]:
        return next((s for s in self._session_mgr.all() if s.id == item_id), None)

    # --- Session actions ---

    def _new_session(self) -> None:
        dlg = NewSessionDialog(self)
        if dlg.result:
            self._session_mgr.add(dlg.result)
            self._refresh_session_tree()
            self._status(f"Session '{dlg.result.name}' created.")

    def _edit_session(self, session: SSHSessionConfig) -> None:
        dlg = NewSessionDialog(self, session=session)
        if dlg.result:
            self._session_mgr.update(dlg.result)
            self._refresh_session_tree()
            self._status(f"Session '{session.name}' updated.")

    def _delete_session(self, session: SSHSessionConfig) -> None:
        if messagebox.askyesno("Delete Session", f"Delete '{session.name}'?", parent=self):
            self._session_mgr.delete(session.id)
            self._refresh_session_tree()
            self._status(f"Session '{session.name}' deleted.")

    def _connect(self, session: SSHSessionConfig) -> None:
        # Re-focus existing tab if already open
        if session.id in self._terminals:
            for tab in self._notebook.tabs():
                if self._notebook.tab(tab, "text") == session.name:
                    self._notebook.select(tab)
                    return

        # Resolve password
        password: Optional[str] = None
        if session.keepass_entry_uuid:
            if keepass_manager.is_open:
                password = keepass_manager.get_password_for_session(session)
            else:
                if messagebox.askyesno(
                    "KeePass Locked",
                    "This session uses a KeePass entry but no database is open.\n"
                    "Open KeePass database now?",
                    parent=self,
                ):
                    self._open_keepass()
                    password = keepass_manager.get_password_for_session(session)

        if password is None and not session.key_path:
            password = simpledialog.askstring(
                "Password",
                f"Password for {session.username}@{session.hostname}:",
                show="*",
                parent=self,
            )

        terminal = SSHTerminalWidget(self._notebook, session, password=password)
        self._terminals[session.id] = terminal
        self._notebook.add(terminal, text=session.name)
        self._notebook.select(terminal)
        self._status(f"Connecting to {session.name}…")

    # --- Tab management ---

    def _close_current_tab(self) -> None:
        current = self._notebook.select()
        if not current:
            return
        for sid, widget in list(self._terminals.items()):
            if str(widget) == current:
                widget.close()
                del self._terminals[sid]
                break
        self._notebook.forget(current)

    def _on_tab_changed(self, _event: tk.Event) -> None:
        pass

    # --- KeePass ---

    def _open_keepass(self) -> None:
        if not PYKEEPASS_AVAILABLE:
            messagebox.showerror(
                "Missing Dependency",
                "pykeepass is not installed.\nRun: pip install pykeepass",
                parent=self,
            )
            return
        dlg = KeePassOpenDialog(self)
        if dlg.success:
            self._refresh_kp_panel()
            self._status(f"KeePass '{pathlib.Path(keepass_manager.db_path).name}' opened.")

    def _lock_keepass(self) -> None:
        keepass_manager.lock()
        self._refresh_kp_panel()
        self._status("KeePass database locked.")

    def _refresh_kp_panel(self) -> None:
        self._kp_list.delete(0, tk.END)
        self._kp_entries: list = []
        if not keepass_manager.is_open:
            self._kp_list.insert(tk.END, "  (no database open)")
            return
        self._kp_entries = keepass_manager.get_all_entries()
        for e in self._kp_entries:
            label = f"  {e.title or '(no title)'}"
            if e.username:
                label += f"  [{e.username}]"
            self._kp_list.insert(tk.END, label)

    def _on_kp_right_click(self, event: tk.Event) -> None:
        idx = self._kp_list.nearest(event.y)
        if idx < 0:
            return
        self._kp_list.selection_clear(0, tk.END)
        self._kp_list.selection_set(idx)
        entries = getattr(self, "_kp_entries", [])
        if idx >= len(entries):
            return
        entry = entries[idx]
        m = tk.Menu(
            self, tearoff=False,
            bg=COLORS["surface0"], fg=COLORS["text"],
            activebackground=COLORS["mauve"], activeforeground=COLORS["base"],
        )
        m.add_command(label="Copy Username",
                      command=lambda: self._clipboard(entry.username or ""))
        m.add_command(label="Copy Password",
                      command=lambda: self._clipboard(entry.password or ""))
        m.add_command(label="Copy URL",
                      command=lambda: self._clipboard(entry.url or ""))
        m.tk_popup(event.x_root, event.y_root)

    # --- MobaXterm import ---

    def _import_mobaxterm(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Import MobaXterm Sessions",
            filetypes=[("MobaXterm sessions", "*.mxtsessions"), ("All files", "*")],
        )
        if not path:
            return
        try:
            sessions = MobaXtermImporter.parse_file(path)
        except Exception as exc:
            messagebox.showerror("Import Error", str(exc), parent=self)
            return

        if not sessions:
            messagebox.showinfo("Import", "No SSH sessions found in the file.", parent=self)
            return

        preview = "\n".join(
            f"  {s.name}  →  {s.username}@{s.hostname}:{s.port}"
            for s in sessions[:20]
        )
        if len(sessions) > 20:
            preview += f"\n  … and {len(sessions) - 20} more"

        if messagebox.askyesno(
            "Import Sessions",
            f"Found {len(sessions)} SSH session(s):\n\n{preview}\n\nImport all?",
            parent=self,
        ):
            added = self._session_mgr.import_sessions(sessions)
            self._refresh_session_tree()
            self._status(f"Imported {added} new session(s) from MobaXterm.")

    # --- Utilities ---

    def _clipboard(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self._status("Copied to clipboard.")

    def _status(self, msg: str) -> None:
        self._status_lbl.config(text=msg)


# ===========================================================================
# ENTRY POINT
# ===========================================================================

def main() -> None:
    app = SessionVaultApp()
    app.mainloop()


if __name__ == "__main__":
    main()
