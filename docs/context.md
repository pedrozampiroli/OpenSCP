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
- JSON-based theme system (supports Dark, Neon, and High-Contrast Light themes)
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
│  │       ├── SSHTerminalWidget ← ssh_terminal.py              │
│  │       └── TasksPanelWidget  ← tasks_panel.py               │
│  └── QStatusBar + QProgressBar                                │
│                                                                │
│  State: ssh_client, sftp_client, _workers[], _current_conn    │
│  Signals wired: panels → MainWindow → workers → panels        │
└───────────────────────────────────────────────────────────────┘
         │
┌─ Support modules ─────────────────────────────────────────────┐
│  sftp_worker.py       — 7 QThread workers for all SFTP ops     │
│  crypto_store.py      — AES-256-GCM encrypted vault            │
│  connection_manager.py — dialogs: master pw, editor, list      │
│  theme_manager.py     — JSON → QSS engine (Centralized CSS)    │
│  i18n.py              — tr() translation system                 │
│  settings_dialog.py   — theme/language/password UI             │
└───────────────────────────────────────────────────────────────┘
         │
┌─ Data files ──────────────────────────────────────────────────┐
│  themes/dark_default.json, themes/one_dark.json,              │
│  themes/github_light.json, themes/solarized_light.json        │
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

### 3.2 `main_window.py` (450+ lines)

**Class: `MainWindow(QMainWindow)`**

Central orchestrator. Manages connection lifecycle, transfers, and wiring between all components.

**Key UI Components with ObjectNames:**
- `btn_connections`: "Connections" toolbar button.
- `btn_disconnect`: "Disconnect" toolbar button.
- `btn_settings`: "Settings" toolbar button.

**Key methods:**
- `_apply_theme()`: Loads theme, applies global QSS. Uses `theme_manager.theme_to_qss()`.
- `_open_settings()`: Opens `SettingsDialog`.

---

### 3.3 `sftp_worker.py` (190+ lines)

Includes new workers for file loading and saving in the text editor.

---

### 3.4 `local_panel.py` (180+ lines)

**STRICT THEMING**: All hardcoded colors removed.
- Header title object: `local_panel_title`.
- Uses `QFileSystemModel` for native OS icons.

---

### 3.5 `remote_panel.py` (320+ lines)

**STRICT THEMING**: All hardcoded colors removed.
- Header title object: `remote_panel_title`.
- Populates custom model with directory listing, handles drag-out and drop-in.

---

### 3.6 `crypto_store.py` (179 lines)

AES-256-GCM encrypted vault for storing connection credentials.

---

### 3.7 `connection_manager.py` (450+ lines)

**STRICT THEMING**: Separators use `mgr_sep`, titles use `conn_mgr_title`.
- `ConnectionManagerDialog`: List of saved connections, Connect, Add, Edit, Delete, Export, Import.
- `MasterPasswordDialog`: Unlocks/Creates vault with session caching.

---

### 3.8 `theme_manager.py` (350+ lines)

**Centralized Styling Engine**:
- `theme_to_qss(theme) → str`: Generates the entire app's stylesheet. 
- **Important**: This is the ONLY place where CSS colors/borders should be defined.
- Supports object-name targeting for specific widgets (buttons, titles, separators).
- Handles high-contrast Light themes by explicitly setting `selection-color`.

---

### 3.11 `ssh_terminal.py` (260+ lines)

**Interactive Terminal**:
- `_ANSI_RE`: Strips CSI/OSC but preserves `\r` and `\n` for manual processing.
- `_on_output()`: Correctly handles `\r` (carriage return) by moving cursor to line start, preventing prompt duplication.
- `TerminalTextEdit`: Captures keystrokes, sends raw bytes to paramiko.
- **Key shortcuts**: Support for `Ctrl+W` (word-delete), `Ctrl+U` (line-kill), `Alt+Backspace`, and standard arrow navigation.

---

### 3.13 `tasks_panel.py` (80+ lines)

**Background Tasks Viewer**:
- `list_widget`: ObjectName `tasks_list`.
- `TaskItemWidget`: Shows progress bars, titles, and status labels (`task_status`).
- Dynamic status coloring: Success (`state="finished"`) and Error (`state="error"`) labels.

---

## 4. Signal Flow Diagram

*Unchanged since initial version.*

---

## 6. Important Conventions

1. **NO HARDCODED CSS**: Do NOT use `setStyleSheet()` with literal colors in Python files. Everything must use `setObjectName` and theme tokens in `theme_manager.py`.
2. **QThread Workers**: Always follow the patterns established in `sftp_worker.py`.
3. **i18n**: All UI strings must use `tr()` with keys present in `en.json` and `pt_BR.json`.
4. **Terminal Stability**: Terminal output processing must handle `\r` (carriage return) for prompt stability.
5. **Private Keys**: Base64-encoded strings in dicts, never saved in plaintext.
