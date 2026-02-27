# SessionVault

A Python SSH/RDP/VNC/Telnet client GUI with integrated KeePass credential management — combining the productivity of MobaXterm-style session management with a secure, full-featured KeePass vault.

## Features

### Connectivity
- **Multi-protocol support** — SSH, RDP, VNC, and Telnet sessions in a single app
- **Multi-tab terminal** — open multiple sessions simultaneously in a tabbed interface
- **SSH tunneling** — configure local port-forwarding tunnels per session
- **X11 forwarding** — run remote GUI apps over SSH (requires local X server)
- **MobaXterm import** — import existing `.mxtsessions` files directly

### SFTP
- **Built-in SFTP browser** — browse, upload, download, create folders, and delete files without leaving the app
- Opens as a dedicated tab alongside the terminal for the active SSH session

### KeePass Integration
- **Open `.kdbx` databases** — KDBX3 (AES-256) and KDBX4 (ChaCha20 + Argon2) supported
- **Create new databases** — choose between Argon2/ChaCha20 (KDBX4) or AES-256/PBKDF2 (KDBX3)
- **Full read/write** — add, edit, and delete entries without leaving the app
- **Auto-fill on connect** — linked KeePass entries supply credentials automatically
- **SSH auto-fill** — paste username or password into the active terminal from the KeePass panel
- **Global Auto-Type** — simulate keystrokes in any focused window (configurable delay)

### Macros
- **Record & playback** — capture a sequence of commands and replay them with one click
- **Named macros** — save macros by name and manage them via the Macros menu
- **Multi-session execution** — replay a macro across multiple open sessions

### Appearance
- **Five built-in themes** — Catppuccin Mocha (default), Catppuccin Latte, Dracula, Nord, One Dark
- **Runtime theme switching** — changes apply immediately without restart
- **Custom application icon** — set any `.png` or `.ico` file as the window icon
- **Full ANSI color support** — 16-color, 256-color, and 24-bit RGB terminal output

### Plugin System
- **Python plugin API** — drop `.py` files into `~/.sessionvault/plugins/` to extend the app
- **Hook points** — `on_session_connect`, `on_session_output`, `add_menu_action`
- **Runtime reload** — reload plugins from the Settings dialog without restarting

### Packaging
- **PyInstaller spec included** — build a self-contained executable for Linux, macOS, or Windows

## Requirements

- Python 3.11+
- See `requirements.txt` for Python package dependencies

### Platform notes

| Platform | Additional requirement |
|----------|----------------------|
| Linux (X11 Auto-Type) | `sudo apt install python3-xlib` |
| macOS (Auto-Type) | Grant **Accessibility** permission in System Settings → Privacy |
| RDP (Linux/macOS) | `xfreerdp` must be installed |
| RDP (Windows) | `mstsc` is built in |
| VNC | `vncviewer` must be installed |
| X11 forwarding | A local X server (e.g. XQuartz on macOS, VcXsrv on Windows) |

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd sessionvault

# Install dependencies
pip install -r requirements.txt

# Linux: also install python3-xlib for Auto-Type
# sudo apt install python3-xlib

# Run the application
python sessionvault.py
```

### Build a standalone executable (optional)

```bash
pip install pyinstaller
pyinstaller sessionvault.spec
# Output: dist/SessionVault/
```

## Usage

### Starting a Session

1. Click **+ New Session** (or `Ctrl+T`) to add a server
2. Choose a protocol (SSH / RDP / VNC / Telnet), fill in hostname, port, and credentials
3. Double-click a session in the left panel to connect

### SSH Tunnels

In the **New/Edit Session** dialog → **SSH Options** tab:
- Click **+ Add Tunnel**, enter a local port, remote host, and remote port
- Tunnels are established automatically when the SSH session connects

### SFTP Browser

While an SSH session is active, click the **SFTP** button in the terminal toolbar.
A new tab opens with a full file browser for the remote host.

### Macros

- Click **Record** in the terminal toolbar to start capturing commands
- Click **Stop** to save the macro with a name
- **Macros → \<name\>** to replay; **Macros → Manage…** to rename or delete

### KeePass

1. **Tools → Open KeePass Database…** — unlock your `.kdbx` file
2. Browse entries in the **KeePass** panel (bottom-left)
3. Right-click an entry → **Copy Username / Password / URL**, or **SSH Auto-fill**
4. When creating/editing a session, click **Select Entry** to link credentials
5. **Tools → New KeePass Database…** — create a new KDBX4 vault
6. **Tools → Add KeePass Entry…** — add an entry to the open database

### Auto-Type

1. Open **Settings → Preferences** → **Auto-Type** tab, configure the keystroke delay
2. In the KeePass panel, right-click an entry → **Global Auto-Type**
   The username + password will be typed into whatever window currently has focus

### Plugins

Drop a `.py` file into `~/.sessionvault/plugins/`. Example plugin:

```python
def setup(api):
    api.on_session_connect(lambda session: print(f"Connected: {session.name}"))
    api.add_menu_action("Say Hello", lambda: print("Hello from plugin!"))
```

Reload via **Settings → Preferences → Plugins → Reload plugins**.

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+T` | New session |
| `Ctrl+W` | Close current tab |
| `Ctrl+,` | Open Preferences |
| `Ctrl+Q` | Quit |
| `Double-click` | Connect to session |
| `Right-click` | Session / KeePass context menu |

## Security Notes

- **Passwords are never saved to disk.** Session configs store only hostname, port, username, key path, and KeePass entry UUID.
- **KeePass passwords stay in memory only** while the database is unlocked.
- Use **Tools → Lock KeePass Database** to clear credentials from memory.
- SSH host keys are auto-accepted on first connect. For production use, configure `~/.ssh/known_hosts` manually.
- New KeePass databases are created with **ChaCha20 + Argon2** (KDBX4) by default for maximum security.

## Application Data

All data is stored under `~/.sessionvault/`:

| File / Folder | Contents |
|---------------|----------|
| `sessions.json` | Session configurations |
| `settings.json` | Application preferences |
| `macros.json` | Saved macros |
| `plugins/` | User plugin directory |

## Architecture

```
sessionvault/
├── sessionvault.py          # Entry point
├── sessionvault.spec        # PyInstaller build spec
├── requirements.txt
└── app/
    ├── constants.py         # Themes, paths, app metadata
    ├── models.py            # SSHSessionConfig, TunnelConfig dataclasses
    ├── theme.py             # QSS stylesheet + apply_theme()
    ├── main.py              # SessionVaultApp main window
    ├── managers/
    │   ├── keepass.py       # KeePass r/w (open, create, CRUD, save)
    │   ├── session.py       # Session CRUD + JSON persistence
    │   └── settings.py      # Application settings persistence
    ├── terminal/
    │   ├── ansi.py          # ANSI escape code parser
    │   └── widget.py        # SSHTerminalWidget, SSHWorker, TelnetWorker
    ├── sftp/
    │   └── browser.py       # SFTPBrowserWidget (threaded paramiko SFTP)
    ├── macros/
    │   ├── manager.py       # MacroManager (record/save/load)
    │   └── dialog.py        # MacroManagerDialog, MacroSaveDialog
    ├── plugins/
    │   └── loader.py        # PluginAPI + PluginLoader
    ├── dialogs/
    │   ├── new_session.py   # New/Edit session dialog (all protocols)
    │   ├── keepass_open.py  # KeePass open dialog
    │   ├── keepass_selector.py  # KeePass entry picker
    │   ├── keepass_editor.py    # KeePass entry + new-DB dialogs
    │   └── settings.py      # Preferences dialog
    └── importers/
        └── mobaxterm.py     # MobaXterm .mxtsessions importer
```
