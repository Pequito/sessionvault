# Changelog

All notable changes to SessionVault are documented here.
This project follows [Semantic Versioning](https://semver.org/).

---

## [2.0.0] – 2026-02-27

### Added

#### Multi-protocol support
- RDP sessions launch `xfreerdp` (Linux/macOS) or `mstsc` (Windows)
- VNC sessions launch `vncviewer`
- Telnet sessions via a built-in async worker with IAC negotiation stripping
- Protocol selector in the New/Edit Session dialog; default port updates automatically

#### SFTP browser
- Built-in graphical SFTP browser opens as a dedicated tab alongside the terminal
- Supports navigate, upload, download, create folder, and delete
- Fully threaded via `QThread` + queued signals — no GUI blocking

#### SSH tunneling & X11 forwarding
- Per-session local port-forwarding tunnels (add/remove in SSH Options tab)
- Tunnels are established automatically on connect via `paramiko.open_channel("direct-tcpip")`
- X11 forwarding checkbox in SSH Options tab (requires a local X server)

#### Macros
- Record a sequence of commands in the terminal, then save with a name
- Replay macros via the **Macros** menu or the terminal toolbar
- Manage (rename/delete) macros from **Macros → Manage…**
- Macros persisted to `~/.sessionvault/macros.json`

#### Plugin system
- Drop `.py` files into `~/.sessionvault/plugins/` to extend the app at runtime
- `PluginAPI` exposes `on_session_connect`, `on_session_output`, and `add_menu_action` hooks
- Reload plugins without restarting from **Settings → Preferences → Plugins**

#### Themes
- Added four new built-in themes: **Catppuccin Latte**, **Dracula**, **Nord**, **One Dark**
- Themes switch at runtime with no restart required (`apply_theme()`)
- QSS coverage extended: tables, spinboxes, comboboxes, checkboxes

#### Full KeePass read/write
- **Tools → New KeePass Database…** — create a new vault (KDBX4 or KDBX3)
- **Tools → Add KeePass Entry…** / **Edit Entry** / **Delete Entry** — full CRUD without leaving the app
- KeePass panel context menu now includes Edit and Delete Entry actions

#### Encryption upgrade
- New databases default to **ChaCha20 + Argon2** (KDBX4)
- AES-256 + PBKDF2 (KDBX3) available as an alternative
- Graceful fallback for older `pykeepass` versions that do not accept the `encryption=` kwarg

#### Global Auto-Type & SSH auto-fill
- **Global Auto-Type** simulates keystrokes into any focused window via `pynput`
- Configurable keystroke delay (Settings → Preferences → Auto-Type)
- **SSH Auto-fill** pastes username or password directly into the active terminal

#### Settings dialog
- **Settings → Preferences** (`Ctrl+,`) with four tabs: Appearance, Terminal, Auto-Type, Plugins
- Theme picker, custom application icon chooser (`.png` / `.ico`), terminal font-size spinner

#### Packaging
- `sessionvault.spec` — PyInstaller build spec for Linux, macOS, and Windows
- macOS `.app` bundle with `NSHighResolutionCapable` and `LSMinimumSystemVersion 12.0`

### Changed

- **GUI framework migrated from `tkinter` to `PySide6`** (Qt 6) — richer widgets, proper theming, native look-and-feel
- `sessionvault.py` refactored into a fully modular `app/` package
- `SSHSessionConfig` extended with `protocol`, `x11_forwarding`, `local_tunnels`, `rdp_width`, `rdp_height`, `rdp_fullscreen`
- New/Edit Session dialog is now tabbed: **General**, **SSH Options**, **RDP Options**
- `requirements.txt` updated — added `pynput`; `pyinstaller` listed as optional

### New modules

| Module | Description |
|--------|-------------|
| `app/managers/settings.py` | JSON-backed application settings persistence |
| `app/sftp/browser.py` | Threaded SFTP browser widget |
| `app/macros/manager.py` | Macro record/save/load |
| `app/macros/dialog.py` | Macro manager and save dialogs |
| `app/plugins/loader.py` | Plugin API and loader |
| `app/dialogs/keepass_editor.py` | KeePass entry editor and new-database dialog |
| `app/dialogs/settings.py` | Application preferences dialog |

---

## [1.0.0] – 2025-01-01

### Added

- Multi-tab SSH terminal with ANSI 256-color and 24-bit RGB support
- Session management with folder organisation, persisted to `~/.sessionvault/sessions.json`
- KeePass `.kdbx` read-only integration — auto-fill credentials on connect
- MobaXterm `.mxtsessions` import
- Catppuccin Mocha dark theme
- `tkinter`-based GUI
