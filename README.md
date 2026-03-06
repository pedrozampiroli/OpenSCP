# OpenSCP

**A modern, secure SFTP client with dual-pane interface, built-in text editor, SSH terminal, and encrypted connection vault.**

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## Features

| Feature | Description |
|---|---|
| Dual-pane file manager | Local panel (left) + Remote SFTP panel (right) |
| Drag & drop | Drag files between panels or from Finder/Explorer; drop onto folders for direct upload |
| Encrypted vault | AES-256-GCM encrypted connection storage with PBKDF2 key derivation |
| Private key authentication | Attach RSA, Ed25519, ECDSA, or DSS keys to connections |
| Import / Export | Encrypted `.openscp` files for sharing connections securely |
| Text editor | Tabbed editor with line numbers and syntax highlighting (Python, JSON, YAML, Shell) |
| SSH Terminal | Interactive shell via `invoke_shell()` with Ctrl+C support |
| Themes | JSON-based theme engine; ships with Dark Default and Dracula |
| Internationalization | Multi-language support (English, Português BR); easy to extend |
| Settings | Theme selector, language switch, master password change |
| Session cache | Remember master password for 15 min / 1h / 1 day / 1 week |

---

## Quick Start

1. Open **Connections** → create a master password → add a server
2. Double-click a saved connection to connect
3. Browse remote files; drag and drop to upload or download
4. Right-click a file → **Edit** to open it in the built-in editor
5. Use the **Terminal** tab for interactive SSH commands
6. Open **Settings** to change the theme, language, or master password

---

## Requirements

- Python 3.9+
- PyQt6
- paramiko (includes `cryptography`)

---

## Installation & Running

### 1. Clone the repository

```bash
git clone https://github.com/your-user/OpenSCP.git
cd OpenSCP
```

### 2. Install dependencies

```bash
pip install PyQt6 paramiko
```

### 3. Run

```bash
python3 main.py
```

---

## Building a Standalone Executable

Use [PyInstaller](https://pyinstaller.org) to create a platform-specific binary.

```bash
pip install pyinstaller
```

### macOS

```bash
pyinstaller --name OpenSCP \
  --windowed \
  --icon=icon.icns \
  --add-data "themes:themes" \
  --add-data "locales:locales" \
  --hidden-import=paramiko \
  --hidden-import=cryptography \
  main.py
```

The application bundle will be placed in `dist/OpenSCP.app`.

**Optional — create a DMG installer:**

```bash
# Requires create-dmg: brew install create-dmg
create-dmg \
  --volname "OpenSCP" \
  --window-size 600 400 \
  --app-drop-link 450 200 \
  "OpenSCP.dmg" \
  "dist/OpenSCP.app"
```

---

### Linux

```bash
pyinstaller --name OpenSCP \
  --onefile \
  --add-data "themes:themes" \
  --add-data "locales:locales" \
  --hidden-import=paramiko \
  --hidden-import=cryptography \
  main.py
```

The binary will be placed in `dist/OpenSCP`.

**System dependencies by distribution:**

| Distribution | Command |
|---|---|
| Debian / Ubuntu | `sudo apt install python3-pyqt6 libxcb-xinerama0` |
| Fedora / RHEL / CentOS Stream | `sudo dnf install python3-pyqt6 libxcb` |
| openSUSE Tumbleweed / Leap | `sudo zypper install python3-qt6 libxcb-xinerama0` |
| Arch Linux / Manjaro | `sudo pacman -S python-pyqt6 libxcb` |
| Void Linux | `sudo xbps-install -S python3-PyQt6 libxcb` |
| Alpine Linux | `sudo apk add py3-pyqt6 libxcb` |
| Gentoo | `sudo emerge dev-python/pyqt6 x11-libs/libxcb` |
| NixOS | Add `python3Packages.pyqt6` and `xorg.libxcb` to your environment |

**Optional — create a `.desktop` entry:**

```ini
# ~/.local/share/applications/openscp.desktop
[Desktop Entry]
Name=OpenSCP
Exec=/path/to/OpenSCP
Icon=/path/to/icon.png
Type=Application
Categories=Network;FileTransfer;
```

---

### Windows

```powershell
pyinstaller --name OpenSCP `
  --windowed `
  --icon=icon.ico `
  --add-data "themes;themes" `
  --add-data "locales;locales" `
  --hidden-import=paramiko `
  --hidden-import=cryptography `
  main.py
```

> **Note:** On Windows, use `;` instead of `:` as the separator in `--add-data` paths.

The executable will be placed in `dist\OpenSCP\OpenSCP.exe`. For a distributable installer, point [NSIS](https://nsis.sourceforge.io) or [Inno Setup](https://jrsoftware.org/isinfo.php) at the `dist\OpenSCP\` folder.

---

## Project Structure

```
OpenSCP/
├── main.py                 # Entry point
├── main_window.py          # Main window (toolbar, panels, editor, terminal)
├── sftp_worker.py          # Background QThread workers (connect, list, transfer)
├── local_panel.py          # Local filesystem panel
├── remote_panel.py         # Remote SFTP panel
├── crypto_store.py         # AES-256-GCM encrypted vault
├── connection_manager.py   # Connection CRUD + import/export
├── theme_manager.py        # JSON → QSS theme engine
├── i18n.py                 # Translation system
├── text_editor.py          # Tabbed text editor with syntax highlighting
├── ssh_terminal.py         # Interactive SSH terminal
├── settings_dialog.py      # Settings (theme, language, password)
├── themes/
│   ├── dark_default.json   # Built-in dark theme
│   └── dracula.json        # Dracula theme
├── locales/
│   ├── en.json             # English
│   └── pt_BR.json          # Português (Brasil)
└── README.md
```

---

## Custom Themes

Create a JSON file with the structure below and import it via **Settings → Import Theme**:

```json
{
  "name": "My Theme",
  "author": "Your Name",
  "colors": {
    "background": "#1e1e2e",
    "background_secondary": "#181825",
    "foreground": "#cdd6f4",
    "accent": "#89b4fa",
    "border": "#45475a",
    "selection": "#45475a",
    "success": "#a6e3a1",
    "error": "#f38ba8",
    "terminal": "#11111b",
    "terminal_foreground": "#cdd6f4"
  }
}
```

Refer to `themes/dark_default.json` for the full list of supported color tokens.

---

## Adding Languages

1. Copy `locales/en.json` to `locales/xx.json` (e.g., `es.json`)
2. Translate all values, keeping the keys unchanged
3. Set `"_language_name": "Español"` at the top of the file
4. The new language will appear automatically in **Settings → Language**

---

## Security

- Connections are encrypted with **AES-256-GCM**
- Encryption key derived via **PBKDF2-HMAC-SHA256** (600,000 iterations) from the master password
- Private keys are stored as Base64 inside the encrypted vault
- Exported `.openscp` files are independently encrypted
- The vault is stored at `~/.openscp/connections.enc`

---

## License

MIT License — free for personal and commercial use.
