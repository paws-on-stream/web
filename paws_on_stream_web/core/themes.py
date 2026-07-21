import json
import re
from functools import lru_cache
from pathlib import Path

THEME_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
THEME_ROOT = Path(__file__).resolve().parent / "themes"
DEFAULT_WEB_THEME = "east-readable"


@lru_cache(maxsize=16)
def get_display_theme(name, *, fallback=True):
    normalized = str(name or "").strip().lower()
    if not THEME_NAME_PATTERN.fullmatch(normalized):
        if not fallback:
            raise ValueError("Invalid theme name.")
        normalized = DEFAULT_WEB_THEME
    path = THEME_ROOT / f"{normalized}.json"
    if not path.is_file():
        if not fallback:
            raise FileNotFoundError(normalized)
        path = THEME_ROOT / f"{DEFAULT_WEB_THEME}.json"
    with path.open(encoding="utf-8") as handle:
        theme = json.load(handle)
    if theme.get("schema_version") != 2 or theme.get("name") != path.stem:
        raise ValueError("Invalid display theme schema.")
    return theme
