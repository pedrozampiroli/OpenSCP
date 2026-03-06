"""Internationalization — simple JSON-based translation system."""
from __future__ import annotations

import json
from pathlib import Path

from openscp.utils.theme_manager import _load_settings, _save_settings

LOCALES_DIR = Path(__file__).parent.parent.parent / "resources" / "locales"
_current_locale: str = "en"
_translations: dict[str, str] = {}
_callbacks: list = []  # functions to call when language changes


def get_current_language() -> str:
    return _load_settings().get("language", "en")


def set_language(code: str):
    global _current_locale, _translations
    _current_locale = code
    _translations = _load_locale(code)
    s = _load_settings()
    s["language"] = code
    _save_settings(s)
    for cb in _callbacks:
        try:
            cb()
        except Exception:
            pass


def on_language_changed(callback):
    """Register a callback for language changes."""
    _callbacks.append(callback)


def _load_locale(code: str) -> dict[str, str]:
    path = LOCALES_DIR / f"{code}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    # fallback to English
    en_path = LOCALES_DIR / "en.json"
    if en_path.exists():
        try:
            return json.loads(en_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def tr(key: str, **kwargs) -> str:
    """Translate a key. Supports {var} placeholders."""
    text = _translations.get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


def list_languages() -> list[tuple[str, str]]:
    """Return list of (code, display_name) for available locales."""
    result = []
    if LOCALES_DIR.exists():
        for f in sorted(LOCALES_DIR.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                name = data.get("_language_name", f.stem)
                result.append((f.stem, name))
            except Exception:
                result.append((f.stem, f.stem))
    return result


def init():
    """Initialize i18n with saved language preference."""
    code = get_current_language()
    global _current_locale, _translations
    _current_locale = code
    _translations = _load_locale(code)
