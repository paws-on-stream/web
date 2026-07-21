import copy
import hashlib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, UnidentifiedImageError

THEME_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
ASSET_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
THEME_ROOT = Path(__file__).resolve().parent / "themes"
DEFAULT_WEB_THEME = "east13"
MAX_THEME_BYTES = 256 * 1024
MAX_THEME_ASSETS = 32
MAX_ASSET_BYTES = 5 * 1024 * 1024
MAX_JSON_DEPTH = 20


@dataclass(frozen=True, slots=True)
class ThemeAsset:
    theme_name: str
    asset_id: str
    file: object
    file_name: str
    size: int
    content_type: str
    sha256: str


def _normalize_theme_name(name):
    normalized = str(name or "").strip().lower()
    if not THEME_NAME_PATTERN.fullmatch(normalized):
        raise ValueError("Invalid theme name.")
    return normalized


def _theme_path(name):
    package_path = THEME_ROOT / name / "theme.json"
    if package_path.is_file():
        return package_path
    legacy_path = THEME_ROOT / f"{name}.json"
    if legacy_path.is_file():
        return legacy_path
    raise FileNotFoundError(name)


def _read_json(path):
    if path.stat().st_size > MAX_THEME_BYTES:
        raise ValueError("Theme manifest is too large.")
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("Theme manifest must be an object.")
    if _json_depth(value) > MAX_JSON_DEPTH:
        raise ValueError("Theme manifest is nested too deeply.")
    return value


def _json_depth(value):
    if isinstance(value, dict):
        return 1 + max((_json_depth(item) for item in value.values()), default=0)
    if isinstance(value, list):
        return 1 + max((_json_depth(item) for item in value), default=0)
    return 0


def _validate_v2_theme(theme, *, name):
    if theme.get("name") != name:
        raise ValueError("Theme name does not match its package.")


def _validate_v3_theme(theme, *, name, base_dir):
    metadata = theme.get("theme")
    if not isinstance(metadata, dict) or metadata.get("id") != name:
        raise ValueError("Theme id does not match its package.")
    if not isinstance(metadata.get("name"), str) or not metadata["name"].strip():
        raise ValueError("Theme name is required.")
    if len(metadata["name"]) > 128:
        raise ValueError("Theme name is too long.")
    if not VERSION_PATTERN.fullmatch(str(metadata.get("version", ""))):
        raise ValueError("Invalid theme version.")

    required_objects = (
        "display_profile",
        "canvas",
        "fonts",
        "chat",
        "ticker",
        "media",
        "luma",
        "rendering",
    )
    if any(not isinstance(theme.get(key), dict) for key in required_objects):
        raise ValueError("Theme is missing a required object.")

    assets = theme.get("assets")
    if not isinstance(assets, dict) or len(assets) > MAX_THEME_ASSETS:
        raise ValueError("Invalid theme asset manifest.")
    for asset_id, asset in assets.items():
        if not ASSET_ID_PATTERN.fullmatch(str(asset_id)) or not isinstance(asset, dict):
            raise ValueError("Invalid theme asset id.")
        _validate_asset(asset, base_dir=base_dir)

    chat = theme["chat"]
    template = chat.get("template", {})
    elements = template.get("elements", []) if isinstance(template, dict) else []
    if not isinstance(elements, list) or len(elements) > 16:
        raise ValueError("Invalid chat template.")
    allowed_fields = {"display_name", "content", "media", "sticker_emoji"}
    styles = chat.get("styles", {})
    if not isinstance(styles, dict):
        raise ValueError("Invalid chat styles.")
    for element in elements:
        if not isinstance(element, dict) or element.get("field") not in allowed_fields:
            raise ValueError("Unsupported chat template field.")
        if element.get("style") not in styles:
            raise ValueError("Unknown chat template style.")

    background = chat.get("background")
    frame = background.get("frame") if isinstance(background, dict) else None
    if not isinstance(frame, dict) or frame.get("type") != "segmented_vertical":
        raise ValueError("Invalid chat frame configuration.")
    for segment in ("top", "middle", "bottom"):
        if frame.get(segment) not in assets:
            raise ValueError("Chat frame references an unknown asset.")


def _validate_asset(asset, *, base_dir):
    file_name = asset.get("file")
    if not isinstance(file_name, str) or Path(file_name).name != file_name:
        raise ValueError("Invalid theme asset path.")
    if asset.get("format") != "png":
        raise ValueError("Only PNG theme images are supported.")
    if asset.get("type") != "image" or not isinstance(asset.get("required"), bool):
        raise ValueError("Invalid theme asset metadata.")
    digest = str(asset.get("sha256", ""))
    if not SHA256_PATTERN.fullmatch(digest):
        raise ValueError("Invalid theme asset digest.")
    path = base_dir / file_name
    if not path.is_file() or path.stat().st_size > MAX_ASSET_BYTES:
        raise ValueError("Theme asset is missing or too large.")
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != digest:
        raise ValueError("Theme asset digest does not match.")
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            if image.format != "PNG":
                raise ValueError("Theme asset content is not PNG.")
            if [image.width, image.height] != [asset.get("width"), asset.get("height")]:
                raise ValueError("Theme asset dimensions do not match.")
            has_alpha = image.mode in {"RGBA", "LA"} or "transparency" in image.info
            if bool(asset.get("alpha")) != has_alpha:
                raise ValueError("Theme asset alpha metadata does not match.")
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError("Invalid theme asset image.") from exc


@lru_cache(maxsize=16)
def _load_display_theme(name):
    normalized = _normalize_theme_name(name)
    uploaded = _load_uploaded_theme(normalized)
    if uploaded is not None:
        return uploaded
    path = _theme_path(normalized)
    theme = _read_json(path)
    schema_version = theme.get("schema_version")
    if schema_version == 2:
        _validate_v2_theme(theme, name=normalized)
    elif schema_version == 3:
        _validate_v3_theme(theme, name=normalized, base_dir=path.parent)
    else:
        raise ValueError("Unsupported display theme schema.")
    return theme


def _load_uploaded_theme(name):
    from core.models import DisplayThemeVersion

    version = (
        DisplayThemeVersion.objects.filter(slug=name, is_current=True)
        .only("manifest")
        .first()
    )
    return version.manifest if version else None


def get_display_theme(name, *, fallback=True):
    try:
        return copy.deepcopy(_load_display_theme(_normalize_theme_name(name)))
    except (FileNotFoundError, ValueError):
        if not fallback:
            raise
        return copy.deepcopy(_load_display_theme(DEFAULT_WEB_THEME))


def get_theme_asset(theme_name, asset_id):
    normalized_name = _normalize_theme_name(theme_name)
    normalized_asset_id = str(asset_id or "").strip().lower()
    if not ASSET_ID_PATTERN.fullmatch(normalized_asset_id):
        raise ValueError("Invalid theme asset id.")
    theme = _load_display_theme(normalized_name)
    if theme.get("schema_version") != 3:
        raise FileNotFoundError(normalized_asset_id)
    asset = theme["assets"].get(normalized_asset_id)
    if not isinstance(asset, dict):
        raise FileNotFoundError(normalized_asset_id)
    from core.models import DisplayThemeVersion

    uploaded = DisplayThemeVersion.objects.filter(
        slug=normalized_name,
        version=theme["theme"]["version"],
        is_current=True,
    ).first()
    if uploaded:
        stored = uploaded.assets.filter(asset_id=normalized_asset_id).first()
        if stored is None:
            raise FileNotFoundError(normalized_asset_id)
        return ThemeAsset(
            theme_name=normalized_name,
            asset_id=normalized_asset_id,
            file=stored.file,
            file_name=Path(stored.file.name).name,
            size=stored.size,
            content_type=stored.content_type,
            sha256=stored.sha256,
        )
    path = _theme_path(normalized_name).parent / asset["file"]
    return ThemeAsset(
        theme_name=normalized_name,
        asset_id=normalized_asset_id,
        file=path,
        file_name=path.name,
        size=path.stat().st_size,
        content_type="image/png",
        sha256=asset["sha256"],
    )


def clear_theme_cache():
    _load_display_theme.cache_clear()


def available_theme_choices():
    choices = {"east13": "EAST 13", "east-readable": "EAST Readable (Legacy)"}
    try:
        from core.models import DisplayThemeVersion

        for version in DisplayThemeVersion.objects.filter(is_current=True):
            choices[version.slug] = f"{version.name} {version.version}"
    except Exception:
        pass
    return sorted(choices.items())


def builtin_themes():
    result = []
    for path in sorted(THEME_ROOT.glob("*/theme.json")):
        try:
            theme = _read_json(path)
            if theme.get("schema_version") == 3:
                result.append(
                    {
                        "slug": theme["theme"]["id"],
                        "name": theme["theme"]["name"],
                        "version": theme["theme"]["version"],
                        "schema_version": 3,
                        "asset_count": len(theme.get("assets", {})),
                    }
                )
        except (KeyError, OSError, ValueError):
            continue
    legacy = THEME_ROOT / "east-readable.json"
    if legacy.is_file():
        result.append(
            {
                "slug": "east-readable",
                "name": "EAST Readable",
                "version": "legacy-v2",
                "schema_version": 2,
                "asset_count": 0,
            }
        )
    return result


def with_asset_urls(theme, url_for_asset):
    result = copy.deepcopy(theme)
    if result.get("schema_version") != 3:
        return result
    theme_name = result["theme"]["id"]
    version = result["theme"]["version"]
    for asset_id, asset in result["assets"].items():
        asset["url"] = url_for_asset(theme_name, version, asset_id)
    return result
