# Changelog

All notable changes to SessionVault are documented here.
This project follows [Semantic Versioning](https://semver.org/).

---

## [2.2.0] – 2026-03-09

### Added

- **YubiKey / OTP authentication** — SSH Connect dialog now has a **PIN + OTP** field;
  the value is appended to the password before sending, matching the PAM `pam_yubico`
  server-side expectation (`password + PIN + OTP`)

### Fixed

- **FIDO2 / hardware-key agent crash** — when the SSH agent contains `sk-ecdsa` or
  `sk-ed25519` keys, `paramiko` previously raised `SSHException: key cannot be used for
  signing` from the transport thread. Connections that supply a key file or password now
  skip the agent entirely; pure-agent sessions fall back automatically on that error
- **KeePass dialog focus** — password field now reliably receives focus the moment the
  Unlock / Open dialog appears (deferred via `QTimer.singleShot` so focus fires after Qt
  has finished painting the window)
- **KeePass dialog placement** — both the Unlock and Open dialogs now centre themselves
  on the main application window instead of appearing at the OS default position
- **Terminal carriage-return handling** — `\r` (used by shell prompts, progress bars,
  and `rsync` / `wget` output) now overwrites the current line rather than stacking new
  lines; `\r\n` Windows line endings are normalised correctly
- **Terminal VT100 sequences** — the following control sequences are now acted upon
  rather than silently dropped:

  | Sequence | Effect |
  |----------|--------|
  | `\x1b[2J` / `\x1b[J` | Clear screen (`clear` command) |
  | `\x1b[K` | Erase to end of current line |
  | `\x1b[H` / `\x1b[r;cH` | Absolute cursor position (ncurses apps) |
  | `\x1b[nA/B/C/D` | Relative cursor movement up / down / right / left |

- **Terminal blinking cursor** — the terminal widget no longer sets `setReadOnly(True)`;
  Qt's native blinking text cursor is now visible. Key input is still fully intercepted
  so the user cannot accidentally type into the widget buffer

---

## [2.1.0] – 2026-03-04

### Added

- **SSH Connect dialog** — per-session credential prompt shown on connect; supports
  username override, manual password entry, and KeePass entry selection from a
  searchable combo box
- **KeePass multi-database panel** — sidebar tree view shows all open databases with
  groups and entries; supports opening, locking, and re-unlocking individual databases
  without closing others
- **KeePass path persistence** — last-used database paths survive restarts and are shown
  as locked entries in the panel on next launch; re-unlock with one click
- **Desktop lock detection** — app responds to OS session-lock events and locks all open
  KeePass databases automatically
- **Sessions search bar** — filter the session tree in real time by typing in the search
  field above the session list
- **Browser extension integration** — credential auto-fill endpoint for compatible
  browser extensions via a local WebSocket bridge
- **Full documentation** — every module and public class now carries a docstring and
  author attribution

### Fixed

- **KeePass unlock dialog** was not appearing on first launch in certain configurations
- **KeePass panel content** shifted left after panel resize; layout now anchors correctly
- **pykeepass `Group` attribute** — `parent_group` renamed to `parentgroup` to match the
  installed library version; previously raised `AttributeError` when expanding groups
- **`NameError` in KeePass tree build** — `_add_entry_item` closure was referenced
  before assignment inside `_add_group`; call order corrected
- **MobaXterm importer** — updated value-format parser to handle the new field layout in
  recent MobaXterm exports; `SubRep` folder names are now parsed correctly
- **MobaXterm import crash** — duplicate session names no longer raise an unhandled
  exception during import

### Changed

- KeePass tree view polished: collapsible groups, locked-state icons, cleaner row
  spacing, and an **Apply** button for pending edits
- Activity log panel added for connection and KeePass events

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
