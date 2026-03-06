"""Theme manager — loads JSON color themes and generates QSS stylesheets."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

THEMES_SYSTEM_DIR = Path(__file__).parent / "themes"
THEMES_USER_DIR = Path.home() / ".openscp" / "themes"
SETTINGS_FILE = Path.home() / ".openscp" / "settings.json"


def _load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_settings(settings: dict):
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2))


def get_current_theme_name() -> str:
    return _load_settings().get("theme", "dark_default")


def set_current_theme_name(name: str):
    s = _load_settings()
    s["theme"] = name
    _save_settings(s)


def list_themes() -> list[str]:
    """Return sorted list of available theme names."""
    names = set()
    for d in (THEMES_SYSTEM_DIR, THEMES_USER_DIR):
        if d.exists():
            for f in d.glob("*.json"):
                names.add(f.stem)
    return sorted(names)


def load_theme(name: str) -> dict:
    """Load a theme by name, checking user dir first, then system dir."""
    for d in (THEMES_USER_DIR, THEMES_SYSTEM_DIR):
        path = d / f"{name}.json"
        if path.exists():
            return json.loads(path.read_text())
    return load_theme("dark_default")


def import_theme(file_path: str) -> str:
    """Copy a theme JSON file to the user themes dir. Returns the theme name."""
    THEMES_USER_DIR.mkdir(parents=True, exist_ok=True)
    src = Path(file_path)
    dest = THEMES_USER_DIR / src.name
    shutil.copy2(src, dest)
    return dest.stem


def export_theme(name: str, dest_path: str):
    """Export a theme file to the given path."""
    theme_data = load_theme(name)
    with open(dest_path, "w") as f:
        json.dump(theme_data, f, indent=2)


def theme_to_qss(theme: dict) -> str:
    """Convert a theme dict to a global QSS stylesheet."""
    c = theme.get("colors", {})

    # Map theme tokens to concrete values with fallbacks
    bg = c.get("background", "#0f1923")
    bg_secondary = c.get("background_secondary", "#1a2332")
    bg_tertiary = c.get("background_tertiary", "#212d3d")
    fg = c.get("foreground", "#dce6f0")
    fg_dim = c.get("foreground_dim", "#78909c")
    fg_muted = c.get("foreground_muted", "#546e7a")
    accent = c.get("accent", "#1565c0")
    accent_hover = c.get("accent_hover", "#1976d2")
    accent2 = c.get("accent_secondary", "#6a1b9a")
    border = c.get("border", "#2a3a4a")
    border_active = c.get("border_active", "#42a5f5")
    selection = c.get("selection", "#1565c0")
    success = c.get("success", "#81c784")
    warning = c.get("warning", "#ffb74d")
    error = c.get("error", "#e57373")
    button_bg = c.get("button", "#263238")
    button_hover = c.get("button_hover", "#37474f")
    header_bg = c.get("header", "#212d3d")
    header_fg = c.get("header_foreground", "#90a4ae")
    input_bg = c.get("input", "#1a2332")
    statusbar_bg = c.get("statusbar", "#0d1520")
    scrollbar_bg = c.get("scrollbar", "#1a2332")
    scrollbar_handle = c.get("scrollbar_handle", "#37474f")
    tab_active = c.get("tab_active", bg_secondary)
    tab_inactive = c.get("tab_inactive", bg)
    terminal_bg = c.get("terminal", "#0a0e14")
    terminal_fg = c.get("terminal_foreground", "#b3b1ad")
    local_accent = c.get("local_accent", "#90caf9")
    remote_accent = c.get("remote_accent", "#ce93d8")

    return f"""
/* ── Global ── */
QMainWindow, QDialog {{
    background: {bg};
}}
QWidget {{
    font-family: 'Helvetica Neue', 'Segoe UI', 'Roboto', sans-serif;
    color: {fg};
}}
QSplitter::handle {{
    background: {border};
    width: 3px;
}}

/* ── Status bar ── */
QStatusBar {{
    background: {statusbar_bg};
    color: {fg_dim};
    border-top: 1px solid {border};
    font-size: 11px;
}}

/* ── Progress bar ── */
QProgressBar {{
    background: {bg_secondary};
    border: 1px solid {border};
    border-radius: 4px;
    text-align: center;
    color: {fg_dim};
    font-size: 10px;
    max-height: 16px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {accent}, stop:1 {accent_hover});
    border-radius: 3px;
}}

/* ── Inputs ── */
QLineEdit, QSpinBox, QComboBox {{
    background: {input_bg};
    color: {fg};
    border: 1px solid {border};
    border-radius: 4px;
    padding: 5px 8px;
    font-size: 12px;
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border-color: {border_active};
}}
QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: {input_bg};
    color: {fg};
    border: 1px solid {border};
    selection-background-color: {selection};
}}

/* ── Buttons ── */
QPushButton {{
    background: {button_bg};
    color: {fg};
    border: 1px solid {border};
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 500;
}}
QPushButton:hover {{
    background: {button_hover};
}}
QPushButton:disabled {{
    background: {bg_secondary};
    color: {fg_muted};
    border-color: {border};
}}

/* ── Tree views ── */
QTreeView {{
    background: {bg_secondary};
    color: {fg};
    border: 1px solid {border};
    border-radius: 4px;
    font-size: 12px;
    selection-background-color: {selection};
}}
QTreeView::item:hover {{
    background: {bg_tertiary};
}}
QTreeView::branch {{
    background: {bg_secondary};
}}
QHeaderView::section {{
    background: {header_bg};
    color: {header_fg};
    border: none;
    padding: 4px 6px;
    font-size: 11px;
    font-weight: 600;
}}

/* ── Lists ── */
QListWidget {{
    background: {bg_secondary};
    color: {fg};
    border: 1px solid {border};
    border-radius: 4px;
    font-size: 12px;
    padding: 4px;
}}
QListWidget::item {{
    padding: 8px 10px;
    border-radius: 3px;
}}
QListWidget::item:selected {{
    background: {selection};
}}
QListWidget::item:hover {{
    background: {bg_tertiary};
}}

/* ── Tabs ── */
QTabWidget::pane {{
    border: 1px solid {border};
    background: {bg_secondary};
    border-radius: 4px;
}}
QTabBar::tab {{
    background: {tab_inactive};
    color: {fg_dim};
    border: 1px solid {border};
    border-bottom: none;
    padding: 6px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    font-size: 11px;
}}
QTabBar::tab:selected {{
    background: {tab_active};
    color: {fg};
}}
QTabBar::tab:hover {{
    background: {bg_tertiary};
}}

/* ── Menus ── */
QMenu {{
    background: {button_bg};
    color: {fg};
    border: 1px solid {border};
    border-radius: 4px;
}}
QMenu::item:selected {{
    background: {accent};
}}

/* ── Message Box / Input Dialog ── */
QMessageBox, QInputDialog {{
    background: {bg_secondary};
    color: {fg};
}}
QMessageBox QLabel {{ color: {fg}; }}
QMessageBox QPushButton {{
    background: {button_bg}; color: {fg}; border: 1px solid {border};
    border-radius: 4px; padding: 5px 14px; min-width: 60px;
}}
QMessageBox QPushButton:hover {{ background: {button_hover}; }}

/* ── Group Box ── */
QGroupBox {{
    color: {local_accent};
    border: 1px solid {border};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: 600;
    font-size: 11px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}}

/* ── Scroll bars ── */
QScrollBar:vertical {{
    background: {scrollbar_bg};
    width: 10px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical {{
    background: {scrollbar_handle};
    border-radius: 5px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {scrollbar_bg};
    height: 10px;
    border-radius: 5px;
}}
QScrollBar::handle:horizontal {{
    background: {scrollbar_handle};
    border-radius: 5px;
    min-width: 20px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── Plain text edit (editor/terminal) ── */
QPlainTextEdit, QTextEdit {{
    background: {terminal_bg};
    color: {terminal_fg};
    border: 1px solid {border};
    border-radius: 4px;
    font-family: 'Menlo', 'Consolas', 'Courier New', monospace;
    font-size: 13px;
    selection-background-color: {selection};
}}
"""
