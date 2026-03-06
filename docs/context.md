# OpenSCP — LLM Context Document

> This file describes the entire codebase of **OpenSCP**, a desktop SFTP client built with Python + PyQt6.
> It is optimized for LLM consumption: every module, class, method, signal, and data flow is documented
> so that an AI agent can understand the full application without reading source files.

---

## 1. Overview

**OpenSCP** is a dual-pane SFTP client (similar to WinSCP) for macOS/Linux/Windows.

| Aspect | Value |
|---|---|
| Language | Python 3.9+ |
| GUI Framework | PyQt6 (Fusion style) |
| SSH/SFTP | paramiko |
| Encryption | `cryptography` (AES-256-GCM, PBKDF2-HMAC-SHA256) |
| Threading | `QThread` for all network I/O |
| Entry point | `main.py` → `MainWindow` |

### Key Features
- Dual-pane file manager (local left, remote right)
- Drag-and-drop between panels (including folder-targeted uploads)
- Encrypted connection vault with master password
- Private key authentication (RSA, Ed25519, ECDSA, DSS)
- Built-in tabbed text editor with syntax highlighting
- SSH terminal (interactive shell)
- JSON-based theme system
- Multi-language i18n (English, Português BR)
- Master password change with vault re-encryption

---

## 2. Architecture

```
┌─ main.py ─────────────────────────────────────────────────────┐
│  QApplication → MainWindow                                    │
└───────────────────────────────────────────────────────────────┘
         │
┌─ main_window.py ──────────────────────────────────────────────┐
│  MainWindow(QMainWindow)                                      │
│  ├── Toolbar: [Connections] [Disconnect] [Settings] [info]    │
│  ├── QSplitter (vertical)                                     │
│  │   ├── QSplitter (horizontal)                               │
│  │   │   ├── LocalPanel      ← local_panel.py                │
│  │   │   └── RemotePanel     ← remote_panel.py               │
│  │   └── QTabWidget                                           │
│  │       ├── TextEditorWidget  ← text_editor.py               │
│  │       └── SSHTerminalWidget ← ssh_terminal.py              │
│  └── QStatusBar + QProgressBar                                │
│                                                                │
│  State: ssh_client, sftp_client, _workers[], _current_conn    │
│  Signals wired: panels → MainWindow → workers → panels        │
└───────────────────────────────────────────────────────────────┘
         │
┌─ Support modules ─────────────────────────────────────────────┐
│  sftp_worker.py       — 5 QThread workers for all SFTP ops     │
│  crypto_store.py      — AES-256-GCM encrypted vault            │
│  connection_manager.py — dialogs: master pw, editor, list      │
│  theme_manager.py     — JSON → QSS engine                      │
│  i18n.py              — tr() translation system                 │
│  settings_dialog.py   — theme/language/password UI             │
└───────────────────────────────────────────────────────────────┘
         │
┌─ Data files ──────────────────────────────────────────────────┐
│  themes/dark_default.json, themes/dracula.json                │
│  locales/en.json, locales/pt_BR.json                          │
│  ~/.openscp/connections.enc   (encrypted vault)               │
│  ~/.openscp/settings.json     (theme + language prefs)        │
│  ~/.openscp/themes/           (user-imported themes)          │
└───────────────────────────────────────────────────────────────┘
```

---

## 3. Module Details

### 3.1 `main.py` (19 lines)

Entry point. Creates `QApplication`, sets Fusion style, instantiates `MainWindow`, starts event loop.

---

### 3.2 `main_window.py` (427 lines)

**Class: `MainWindow(QMainWindow)`**

Central orchestrator. Manages connection lifecycle, transfers, and wiring between all components.

**Constructor flow:**
1. `i18n.init()` — loads saved locale
2. `_apply_theme()` — loads saved theme, applies QSS globally
3. `_build_ui()` — creates toolbar, panels, editor, terminal, status bar
4. `_connect_signals()` — wires all signal/slot connections
5. Registers `_retranslate()` for live language switching

**Instance state:**
- `ssh_client: paramiko.SSHClient | None`
- `sftp_client: paramiko.SFTPClient | None`
- `_workers: list[QThread]` — active background workers
- `_connected_host: str` — display name
- `_current_conn: dict` — current connection data

**Key methods:**
| Method | Purpose |
|---|---|
| `_open_connection_manager()` | Opens `ConnectionManagerDialog.open_manager()` factory |
| `_on_saved_connect(conn: dict)` | Extracts host/port/user/pass/key from conn dict, starts `SFTPConnectWorker` |
| `_on_connected(ssh, sftp)` | Stores clients, connects terminal, lists remote home dir |
| `_on_disconnect()` | Closes SSH/SFTP, disconnects terminal, resets UI |
| `_upload_files(local_paths, target_dir="")` | Uploads each file; uses `target_dir` if provided (folder-targeted drop), otherwise `remote_panel.current_path` |
| `_download_files(remote_paths)` | Downloads to `local_panel.current_path` |
| `_start_transfer(direction, local, remote)` | Creates `SFTPTransferWorker`, wires progress/finish/error |
| `_edit_remote_file(remote_path)` | Downloads to tempfile, reads content, opens in `TextEditorWidget` |
| `_save_editor_file(remote_path, content, local_tmp)` | Writes content to local temp, `sftp.put()` back to remote |
| `_delete_remote(path, is_dir)` | Starts `SFTPDeleteWorker` |
| `_mkdir_remote(path)` | Starts `SFTPMkdirWorker` |
| `_open_settings()` | Opens `SettingsDialog` |
| `_retranslate()` | Updates all UI text when language changes |
| `closeEvent()` | Calls `_on_disconnect()` |

---

### 3.3 `sftp_worker.py` (172 lines)

All network operations run on background `QThread`s to keep the UI responsive.

**Class: `SFTPConnectWorker(QThread)`**
- Constructor: `__init__(host, port, username, password, private_key="", key_passphrase="")`
- `private_key`: base64-encoded key file content
- `_load_pkey()`: tries `paramiko.RSAKey`, `Ed25519Key`, `ECDSAKey`, `DSSKey` in order
- Signals: `connected(ssh_client, sftp_client)`, `error(str)`

**Class: `SFTPListWorker(QThread)`**
- Constructor: `__init__(sftp, remote_path)`
- Calls `sftp.listdir_attr(path)`
- Signals: `finished(path, list[SFTPAttributes])`, `error(str)`

**Class: `SFTPTransferWorker(QThread)`**
- Constructor: `__init__(sftp, direction, local_path, remote_path)`
- `direction`: `"upload"` or `"download"` (class constants `UPLOAD`, `DOWNLOAD`)
- Uses `sftp.put()` / `sftp.get()` with progress callback
- Signals: `progress(transferred, total)`, `finished(msg)`, `error(str)`

**Class: `SFTPDeleteWorker(QThread)`**
- Constructor: `__init__(sftp, remote_path, is_dir=False)`
- `_rm_recursive(path)`: recursively deletes directory tree
- Signals: `finished(msg)`, `error(str)`

**Class: `SFTPMkdirWorker(QThread)`**
- Constructor: `__init__(sftp, remote_path)`
- Calls `sftp.mkdir(path)`
- Signals: `finished(msg)`, `error(str)`

---

### 3.4 `local_panel.py` (203 lines)

**Class: `LocalTreeView(QTreeView)`**
- Accepts drops of remote SFTP paths (mime type `application/x-sftp-remote-paths`)
- Signal: `file_drop_requested(list[str])` — remote paths decoded from mime

**Class: `LocalPanel(QWidget)`**
- Uses `QFileSystemModel` for native filesystem browsing
- State: `current_path: str` (initially `Path.home()`)
- Tree shows: Name, Size, Date Modified (Type column hidden)
- Signals:
  - `upload_requested(list[str])` — local file paths to upload
  - `download_requested(list[str])` — remote paths (from drop)
- Context menu: "Upload to remote", "Refresh"
- Navigation: double-click dirs, Up button, path bar

---

### 3.5 `remote_panel.py` (342 lines)

**Class: `RemoteTreeView(QTreeView)`**
- Drag out: encodes selected remote paths as `application/x-sftp-remote-paths` mime
- Drop in: accepts file URLs from OS/local panel
- **Folder-targeted drop**: on `dropEvent`, checks `indexAt(event.position())` — if the item under cursor is a folder (`UserRole+2 == True`), emits its path as `target_dir`
- **Drag hover feedback**: `dragMoveEvent` highlights folder rows when dragging over them
- Signal: `upload_drop_requested(list[str], str)` — `(local_paths, target_remote_dir)` where `target_remote_dir` is `""` if not dropped on a folder

**Class: `RemotePanel(QWidget)`**
- Uses `QStandardItemModel` populated via `populate(remote_path, list[SFTPAttributes])`
- State: `current_path: str` (initially `"/"`)
- Each item stores `UserRole+1 = full_remote_path`, `UserRole+2 = is_dir`
- Signals:
  - `download_requested(list[str])` — remote paths to download
  - `upload_requested(list[str], str)` — `(local_paths, target_dir)`
  - `delete_requested(str, bool)` — `(remote_path, is_dir)`
  - `mkdir_requested(str)` — full remote path
  - `navigate_requested(str)` — navigate to remote dir
  - `edit_requested(str)` — remote file path to open in editor
- Context menu: "Download", "Edit" (single file), "Delete", "New Folder", "Refresh"
- Navigation: double-click dirs, Up button, path bar

---

### 3.6 `crypto_store.py` (179 lines)

AES-256-GCM encrypted vault for storing connection credentials.

**Constants:**
- `STORE_DIR = ~/.openscp/`
- `STORE_FILE = ~/.openscp/connections.enc`
- `PBKDF2_ITERATIONS = 600_000`

**Helper functions:**
- `_derive_key(password, salt) → bytes` — PBKDF2-HMAC-SHA256, 32-byte key
- `_encrypt(data, key) → (nonce, ciphertext)` — AES-256-GCM
- `_decrypt(nonce, ciphertext, key) → bytes` — raises `InvalidTag` on wrong key

**Class: `CryptoStore`**
- State: `_key: bytes | None`, `_connections: list[dict]`, `_salt: bytes`
- Properties: `is_unlocked → bool`, `connections → list[dict]`

| Method | Signature | Purpose |
|---|---|---|
| `vault_exists()` | `@staticmethod → bool` | Checks if `connections.enc` exists |
| `create_vault(master_password)` | `→ None` | Generates salt+key, saves empty vault |
| `unlock(master_password)` | `→ bool` | Reads vault, derives key, decrypts |
| `save(connections)` | `→ None` | Replaces all connections, re-encrypts |
| `add_connection(conn)` | `→ None` | Append + save |
| `update_connection(index, conn)` | `→ None` | Replace at index + save |
| `delete_connection(index)` | `→ None` | Pop at index + save |
| `export_connections(file_path, master_password)` | `→ None` | Fresh PBKDF2 derivation → encrypted `.openscp` file |
| `import_connections(file_path, master_password)` | `@staticmethod → list[dict]` | Decrypts `.openscp` file |
| `change_master_password(old_pw, new_pw)` | `→ bool` | Derives new key, re-encrypts vault |

**Vault file format (JSON):**
```json
{
  "version": 1,
  "salt": "<base64>",
  "nonce": "<base64>",
  "data": "<base64 of AES-256-GCM encrypted JSON array>"
}
```

**Connection dict schema:**
```json
{
  "name": "My Server",
  "host": "192.168.1.1",
  "port": 22,
  "username": "root",
  "password": "secret",
  "private_key": "<base64-encoded key file content, or empty string>",
  "key_passphrase": "<passphrase for private key, or empty string>"
}
```

---

### 3.7 `connection_manager.py` (448 lines)

**Session cache (module-level):**
- `_session_cache = {"password": str|None, "expires_at": float}`
- `_cache_password(password, duration_secs)` — stores with expiry
- `_get_cached_password() → str|None` — returns if not expired

**Class: `MasterPasswordDialog(QDialog)`**
- Constructor: `__init__(is_new: bool, parent)`
- If `is_new`: shows confirm field + "Create" button; else "Unlock" button
- Remember duration combo: Don't remember / 15min / 1h / 1 day / 1 week
- Output: `self.password`, `self.remember_duration`
- Auto-centered via `showEvent()`

**Class: `ConnectionEditorDialog(QDialog)`**
- Fields: Name, Host, Port (QSpinBox), User, Password, Private Key (Browse/Clear), Key Passphrase
- Private key stored as `self._private_key_b64` (base64 of raw file bytes)
- Output: `self.result_conn` (dict matching connection schema)

**Class: `ConnectionManagerDialog(QDialog)`**
- **Factory method: `open_manager(parent) → ConnectionManagerDialog | None`**
  1. Checks session cache for valid password
  2. If miss: shows `MasterPasswordDialog`
  3. Creates or unlocks vault
  4. Caches password with selected duration
  5. Returns ready-to-use dialog (or `None` if cancelled)
- Signal: `connect_requested(dict)` — emits connection dict on double-click/connect
- List shows: `name — host:port 🔑` (key icon if private_key present)
- Buttons: Connect, Add, Edit, Delete, Export, Import
- Export: prompts for export password, writes `.openscp` file
- Import: prompts for password, decrypts, adds non-duplicate connections

---

### 3.8 `theme_manager.py` (335 lines)

**Constants:**
- `THEMES_SYSTEM_DIR` = `<project>/themes/`
- `THEMES_USER_DIR` = `~/.openscp/themes/`
- `SETTINGS_FILE` = `~/.openscp/settings.json`

**Functions:**
| Function | Purpose |
|---|---|
| `_load_settings() → dict` | Reads `settings.json` |
| `_save_settings(dict)` | Writes `settings.json` |
| `get_current_theme_name() → str` | From settings, default `"dark_default"` |
| `set_current_theme_name(name)` | Saves to settings |
| `list_themes() → list[str]` | Scans system + user dirs for `.json` files |
| `load_theme(name) → dict` | Loads JSON theme (user dir first, then system) |
| `import_theme(file_path) → str` | Copies JSON to user dir, returns name |
| `export_theme(name, dest_path)` | Exports theme to file |
| `theme_to_qss(theme) → str` | **Core function**: converts theme color tokens to comprehensive QSS |

**Theme JSON schema:**
```json
{
  "name": "Theme Name",
  "author": "Author",
  "colors": {
    "background": "#hex",
    "background_secondary": "#hex",
    "background_tertiary": "#hex",
    "foreground": "#hex",
    "foreground_dim": "#hex",
    "foreground_muted": "#hex",
    "accent": "#hex",
    "accent_hover": "#hex",
    "accent_secondary": "#hex",
    "border": "#hex",
    "border_active": "#hex",
    "selection": "#hex",
    "success": "#hex",
    "warning": "#hex",
    "error": "#hex",
    "button": "#hex",
    "button_hover": "#hex",
    "header": "#hex",
    "header_foreground": "#hex",
    "input": "#hex",
    "statusbar": "#hex",
    "scrollbar": "#hex",
    "scrollbar_handle": "#hex",
    "tab_active": "#hex",
    "tab_inactive": "#hex",
    "terminal": "#hex",
    "terminal_foreground": "#hex",
    "local_accent": "#hex",
    "remote_accent": "#hex"
  }
}
```

`theme_to_qss()` generates QSS rules for: `QMainWindow`, `QDialog`, `QWidget`, `QSplitter`, `QStatusBar`, `QProgressBar`, `QLineEdit`, `QSpinBox`, `QComboBox`, `QPushButton`, `QTreeView`, `QHeaderView`, `QListWidget`, `QTabWidget`, `QTabBar`, `QMenu`, `QMessageBox`, `QInputDialog`, `QGroupBox`, `QScrollBar`, `QPlainTextEdit`, `QTextEdit`.

---

### 3.9 `i18n.py` (86 lines)

Simple JSON-based translation system.

**Module-level state:**
- `_current_locale: str` — active locale code
- `_translations: dict[str, str]` — loaded key→value map
- `_callbacks: list` — functions to call on language change

**Functions:**
| Function | Purpose |
|---|---|
| `init()` | Loads saved language preference, populates `_translations` |
| `tr(key, **kwargs) → str` | Returns translated string with `{var}` placeholder support; falls back to key itself |
| `get_current_language() → str` | From settings.json |
| `set_language(code)` | Loads locale, saves preference, fires callbacks |
| `on_language_changed(callback)` | Registers callback for live language switching |
| `list_languages() → list[(code, display_name)]` | Scans `locales/` dir |

**Locale file format:** JSON with `_language_name` key + flat key-value pairs. Keys use dot notation: `"dlg.master_pw.title"`, `"status.connected"`, `"toolbar.settings"`, etc.

**Available locales:** `en.json` (English), `pt_BR.json` (Português Brasil)

---

### 3.10 `text_editor.py` (285 lines)

Built-in text editor for editing remote files.

**Syntax highlighting rules** defined for: `.py`, `.json`, `.sh`/`.bash`/`.zsh`, `.yaml`

**Class: `GenericHighlighter(QSyntaxHighlighter)`**
- Takes a dict of `{category: regex_pattern}` rules
- Color map: keywords=#569cd6, strings=#ce9178, comments=#6a9955, numbers=#b5cea8, functions=#dcdcaa, keys=#9cdcfe, booleans=#569cd6, variables=#4ec9b0

**Class: `LineNumberArea(QWidget)`** — painted alongside `CodeEditor`

**Class: `CodeEditor(QPlainTextEdit)`**
- Line numbers on left gutter
- Monospace font (Menlo, 13px)
- Tab = 4 spaces

**Class: `TextEditorWidget(QWidget)`**
- `QTabWidget` with closeable tabs
- Toolbar: Save, Wrap toggle, Close, Find
- State: `_tabs: dict[remote_path → {editor, highlighter, local_tmp}]`
- Signal: `save_requested(remote_path, content, local_tmp)` — wired to `MainWindow._save_editor_file()`
- `open_file(remote_path, content, local_tmp)` — creates or focuses tab
- Key methods: `_on_save()`, `_toggle_wrap()`, `_close_tab()`, `_find_text()`

**Editor data flow:**
1. User right-clicks file in remote panel → "Edit"
2. `RemotePanel.edit_requested` → `MainWindow._edit_remote_file(remote_path)`
3. MainWindow downloads file to temp, reads content, calls `text_editor.open_file()`
4. User edits, clicks Save
5. `TextEditorWidget.save_requested` → `MainWindow._save_editor_file()`
6. MainWindow writes content to temp file, `sftp.put()` back to remote

---

### 3.11 `ssh_terminal.py` (237 lines)

Interactive SSH terminal widget.

**Class: `ChannelReader(QThread)`**
- Reads from `paramiko.Channel` in a loop (50ms polling)
- Signals: `output_received(str)`, `channel_closed()`

**Escape sequence stripping:**
- Comprehensive regex `_ANSI_RE` catches: OSC (`ESC]...BEL/ST`), bare OSC, CSI (`ESC[...letter`), charset switches, OSC 8 hyperlinks, stray BEL, carriage returns
- `strip_escape_sequences(text) → str`

**Class: `SSHTerminalWidget(QWidget)`**
- Uses `TerminalTextEdit` for the display area
- `connect_to_ssh(ssh_client)`: opens `invoke_shell(term="dumb")`, sends `export TERM=dumb` and `unset PROMPT_COMMAND` to minimize escape sequences, starts `ChannelReader`
- `disconnect()`: stops reader, closes channel
- `_on_key(data: bytes)`: sends raw bytes to channel
- `_on_output(text)`: strips escape sequences, appends to display

**Class: `TerminalTextEdit(QTextEdit)`**
- Intercepts **all keystrokes** and emits them as raw bytes via `key_pressed(bytes)` signal
- Does NOT insert text locally (the remote echo handles display)
- Key mappings:
  - Tab → `\t` (autocomplete)
  - Enter → `\n`
  - Backspace → `\x7f`
  - Ctrl+C → `\x03`, Ctrl+D → `\x04`, Ctrl+Z → `\x1a`, Ctrl+L → `\x0c`
  - Arrow keys → ANSI escape sequences (`ESC[A/B/C/D`)
  - Home/End → `ESC[H` / `ESC[F`
  - Delete → `ESC[3~`
  - Escape → `ESC`
  - Regular text → UTF-8 bytes

---

### 3.12 `settings_dialog.py` (187 lines)

**Class: `SettingsDialog(QDialog)`**
- Sections:
  1. **Appearance**: theme selector (QComboBox), language selector (QComboBox), Import Theme button
  2. **Security**: old password, new password, confirm, Change Password button
- Theme changes apply immediately via `QApplication.instance().setStyleSheet(qss)`
- Language changes call `set_language(code)` which fires i18n callbacks
- Password change: creates fresh `CryptoStore`, unlocks with old pw, calls `change_master_password(old, new)`

---

## 4. Signal Flow Diagram

```
LocalPanel                          RemotePanel
  │                                      │
  ├─ upload_requested(list) ────────►    │
  ├─ download_requested(list) ──────►    │
  │                                      ├─ upload_requested(list, str) ──┐
  │                                      ├─ download_requested(list) ─────┤
  │                                      ├─ delete_requested(str, bool) ──┤
  │                                      ├─ mkdir_requested(str) ─────────┤
  │                                      ├─ navigate_requested(str) ──────┤
  │                                      ├─ edit_requested(str) ──────────┤
  │                                      │                                │
  └──────────────────────────────────────┴──────► MainWindow ◄────────────┘
                                                       │
                                    ┌──────────────────┼──────────────────┐
                                    ▼                  ▼                  ▼
                             SFTPConnectWorker  SFTPListWorker   SFTPTransferWorker
                                    │                  │                  │
                                    ▼                  ▼                  ▼
                               connected()        finished()         progress()
                               error()            error()            finished()
                                                                     error()
```

---

## 5. Data Storage Layout

```
~/.openscp/
├── connections.enc       # AES-256-GCM encrypted vault (JSON)
├── settings.json         # {"theme": "dracula", "language": "pt_BR"}
└── themes/               # User-imported theme files
    └── custom_theme.json
```

---

## 6. Important Conventions

1. **All QThread workers** follow the pattern: create → connect signals → append to `_workers` → `start()`. Cleanup via `_cleanup_worker()` on `finished`.
2. **All dialogs** are centered on screen via `showEvent()` override calling `_center_dialog()`.
3. **All UI strings** use `tr("key.name")` from `i18n.py`. Adding a string requires updating both `en.json` and `pt_BR.json`.
4. **Theming**: global QSS is applied via `QApplication.setStyleSheet()`. Individual widget stylesheets should be avoided; use theme tokens.
5. **`from __future__ import annotations`** is present in every module for Python 3.9 compatibility.
6. **Private keys**: stored as base64-encoded raw bytes in the connection dict, never written to disk in plaintext.
7. **Connection dict** is the universal data structure passed between ConnectionManager → MainWindow → SFTPConnectWorker.
