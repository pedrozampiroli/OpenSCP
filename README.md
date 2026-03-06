# ⬡ OpenSCP

**A modern, secure SFTP client with dual-pane interface, built-in text editor, SSH terminal, and encrypted connection vault.**

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## ✨ Features

| Feature | Description |
|---|---|
| 📁 **Dual-pane file manager** | Local panel (left) + Remote SFTP panel (right) |
| 🔄 **Drag & drop** | Drag files between panels or from Finder/Explorer; drop onto folders for direct upload |
| 🔐 **Encrypted vault** | AES-256-GCM encrypted connection storage with PBKDF2 key derivation |
| 🔑 **Private key auth** | Attach RSA, Ed25519, ECDSA, or DSS keys to connections |
| 📤 **Import / Export** | Encrypted `.openscp` files for sharing connections securely |
| ✏️ **Text editor** | Tabbed editor with line numbers and syntax highlighting (Python, JSON, YAML, Shell) |
| 🖥 **SSH Terminal** | Interactive shell via `invoke_shell()` with Ctrl+C support |
| 🎨 **Themes** | JSON-based theme engine; ships with Dark Default + Dracula |
| 🌍 **i18n** | Multi-language support (English, Português BR); easy to add more |
| ⚙ **Settings** | Theme selector, language switch, master password change |
| 🕐 **Session cache** | Remember master password for 15 min / 1h / 1 day / 1 week |

---

## 📸 Quick Overview

1. Click **📋 Connections** → create master password → add a server
2. Double-click a saved connection to connect
3. Browse remote files, drag & drop to upload/download
4. Right-click a file → **✏️ Edit** to open in the built-in editor
5. Use the **🖥 Terminal** tab for SSH commands
6. Click **⚙ Settings** to change theme, language, or master password

---

## 🛠 Requirements

- **Python 3.9+**
- **PyQt6**
- **paramiko** (includes `cryptography`)

---

## 🚀 Installation & Running

### 1. Clone / Download

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

## 📦 Deploy / Build Executable

Use **PyInstaller** to create a standalone executable for any platform.

### Install PyInstaller

```bash
pip install pyinstaller
```

---

### 🍎 macOS

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

The `.app` bundle will be in `dist/OpenSCP.app`.

**Create a DMG (optional):**
```bash
# Install create-dmg: brew install create-dmg
create-dmg \
  --volname "OpenSCP" \
  --window-size 600 400 \
  --app-drop-link 450 200 \
  "OpenSCP.dmg" \
  "dist/OpenSCP.app"
```

---

### 🐧 Linux

```bash
pyinstaller --name OpenSCP \
  --onefile \
  --add-data "themes:themes" \
  --add-data "locales:locales" \
  --hidden-import=paramiko \
  --hidden-import=cryptography \
  main.py
```

The binary will be in `dist/OpenSCP`.

**Create a .desktop entry:**
```ini
# ~/.local/share/applications/openscp.desktop
[Desktop Entry]
Name=OpenSCP
Exec=/path/to/OpenSCP
Icon=/path/to/icon.png
Type=Application
Categories=Network;FileTransfer;
```

**System dependencies (Debian/Ubuntu):**
```bash
sudo apt install python3-pyqt6 libxcb-xinerama0
```

---

### 🪟 Windows

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

> ⚠️ On Windows, use `;` instead of `:` in `--add-data` paths.

The `.exe` will be in `dist\OpenSCP\OpenSCP.exe`.

**Create installer with NSIS or Inno Setup (optional):**  
Point the installer to the `dist\OpenSCP\` folder.

---

## 📂 Project Structure

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

## 🎨 Custom Themes

Create a JSON file with the following structure and import it via **⚙ Settings → Import Theme**:

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

See `themes/dark_default.json` for the full list of supported color tokens.

---

## 🌍 Adding Languages

1. Copy `locales/en.json` to `locales/xx.json` (e.g., `es.json`)
2. Translate all values (keep keys unchanged)
3. Set `"_language_name": "Español"` at the top
4. The new language will appear automatically in **⚙ Settings → Language**

---

## 🔒 Security

- Connections encrypted with **AES-256-GCM**
- Key derived via **PBKDF2-HMAC-SHA256** (600,000 iterations) from master password
- Private keys stored as base64 inside the encrypted vault
- Exported `.openscp` files are independently encrypted
- Vault stored at `~/.openscp/connections.enc`

---

## 📄 License

MIT License — free for personal and commercial use.
