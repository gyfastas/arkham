"""User options, persisted to saves/settings.json.

Currently supported:
- save_dir: custom directory for campaign saves (default: <repo>/saves/campaigns)
"""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = PROJECT_ROOT / "saves" / "settings.json"
DEFAULT_SAVE_DIR = PROJECT_ROOT / "saves" / "campaigns"

_cache: dict | None = None


def load_options() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except Exception:
            _cache = {}
    return _cache


def save_options(opts: dict) -> None:
    global _cache
    _cache = dict(opts)
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(
        json.dumps(_cache, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def custom_save_dir() -> Path | None:
    """User-configured save dir, or None when using the default."""
    raw = (load_options().get("save_dir") or "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def effective_save_dir(fallback: Path) -> Path:
    """Custom save dir if set and valid, else the given fallback."""
    custom = custom_save_dir()
    if custom is not None:
        return custom
    return fallback


def set_save_dir(path_str: str) -> tuple[bool, str]:
    """Configure a custom save dir. Empty string resets to default."""
    path_str = (path_str or "").strip()
    opts = load_options()
    if not path_str:
        opts.pop("save_dir", None)
        save_options(opts)
        return True, str(DEFAULT_SAVE_DIR)
    p = Path(path_str).expanduser()
    try:
        p.mkdir(parents=True, exist_ok=True)
        probe = p / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except Exception as e:
        return False, f"目录不可用: {e}"
    opts["save_dir"] = str(p)
    save_options(opts)
    return True, str(p)


def options_payload(save_count: int = 0) -> dict:
    custom = custom_save_dir()
    return {
        "save_dir": str(custom) if custom else str(DEFAULT_SAVE_DIR),
        "default_save_dir": str(DEFAULT_SAVE_DIR),
        "is_custom": custom is not None,
        "save_count": save_count,
    }
