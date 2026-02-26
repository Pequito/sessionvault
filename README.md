# SessionVault

A Python SSH client GUI with integrated KeePass credential management — combining the productivity of MobaXterm-style session management with secure KeePass vault access.

## Features

- **Multi-tab SSH terminal** — open multiple sessions simultaneously in a tabbed interface
- **MobaXterm import** — import your existing `.mxtsessions` files directly
- **KeePass integration** — open `.kdbx` databases and auto-fill SSH credentials
- **Session management** — organize sessions into folders, persist to disk
- **ANSI color support** — full 256-color and RGB terminal output
- **Dark theme** — eye-friendly Catppuccin Mocha color scheme

## Requirements

- Python 3.11+
- `tkinter` (included with standard Python on most systems)

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd sessionvault

# Install dependencies
pip install -r requirements.txt

# Run the application
python sessionvault.py
```

## Usage

### Starting a Session

1. Click **+ New SSH Session** (or `Ctrl+T`) to add a server
2. Fill in hostname, port, username, and credentials
3. Double-click a session in the left panel to connect

### Importing from MobaXterm

1. In MobaXterm: **Tools → Export all sessions** → save as `.mxtsessions`
2. In SessionVault: **File → Import MobaXterm Sessions...**
3. Review the import preview and click **Import**

### Using KeePass

1. **Tools → Open KeePass Database...** — unlock your `.kdbx` file
2. Browse entries in the **KeePass** panel (bottom-left)
3. Right-click any entry to **Copy Username**, **Copy Password**, or **Copy URL**
4. When creating/editing a session, click **Select Entry** to link a KeePass entry — the password will be fetched automatically on connect

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+T` | New SSH session |
| `Ctrl+W` | Close current tab |
| `Ctrl+Q` | Quit |
| `Double-click` | Connect to session |
| `Right-click` | Session / KeePass context menu |

## Security Notes

- **Passwords are never saved to disk.** Session configs store only hostname, port, username, key path, and KeePass entry UUID.
- **KeePass passwords stay in memory only** while the database is unlocked.
- Use **Tools → Lock KeePass Database** to clear credentials from memory.
- SSH host keys are auto-accepted on first connect (MobaXterm behavior). For production use, configure `~/.ssh/known_hosts` manually.

## Application Data

Session configurations are stored at:
```
~/.sessionvault/sessions.json
```

## Architecture

`sessionvault.py` is organized into clearly marked sections:

| Section | Purpose |
|---------|---------|
| `CONSTANTS` | Color scheme, paths, app metadata |
| `DATA MODELS` | `SSHSessionConfig` dataclass |
| `KEEPASS MANAGER SECTION` | Thread-safe KeePass database access |
| `MOBAXTERM IMPORTER SECTION` | `.mxtsessions` file parser |
| `SESSION MANAGER SECTION` | CRUD + JSON persistence for sessions |
| `SSH TERMINAL WIDGET SECTION` | `AnsiParser` + `SSHTerminalWidget` |
| `DIALOG CLASSES` | New session, KeePass selector, KeePass open |
| `MAIN APPLICATION` | `SessionVaultApp` main window |
| `ENTRY POINT` | `main()` function |
