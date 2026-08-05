import json
import stat
import tempfile
import zipfile
from pathlib import Path

from django.core.files.base import ContentFile
from django.db import transaction

from core.models import DisplayThemeAsset, DisplayThemeVersion
from core.themes import (
    MAX_ASSET_BYTES,
    MAX_FONT_ASSET_BYTES,
    MAX_THEME_ASSETS,
    MAX_THEME_BYTES,
    _normalize_theme_name,
    _validate_v3_theme,
    clear_theme_cache,
    theme_asset_content_type,
)

MAX_PACKAGE_BYTES = 10 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 24 * 1024 * 1024
MAX_PACKAGE_FILES = MAX_THEME_ASSETS + 1


class ThemeImportError(ValueError):
    pass


def import_theme_package(upload, *, user):
    if upload.size > MAX_PACKAGE_BYTES:
        raise ThemeImportError("Das Theme-Paket ist größer als 10 MB.")
    try:
        archive = zipfile.ZipFile(upload)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ThemeImportError("Das Theme-Paket ist kein gültiges ZIP-Archiv.") from exc

    with archive, tempfile.TemporaryDirectory() as temporary_directory:
        members = _validated_members(archive)
        root = Path(temporary_directory)
        try:
            for member in members:
                target = root / member.filename
                target.write_bytes(archive.read(member))
        except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
            raise ThemeImportError(
                "Das Theme-Paket konnte nicht entpackt werden."
            ) from exc
        manifest_path = root / "theme.json"
        if (
            not manifest_path.is_file()
            or manifest_path.stat().st_size > MAX_THEME_BYTES
        ):
            raise ThemeImportError("theme.json fehlt oder ist zu groß.")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict) or manifest.get("schema_version") != 3:
                raise ThemeImportError(
                    "Es wird ein Theme-Manifest in Schema v3 benötigt."
                )
            slug = str(manifest.get("theme", {}).get("id", ""))
            _normalize_theme_name(slug)
            _validate_v3_theme(manifest, name=slug, base_dir=root)
            expected_files = {"theme.json"} | {
                asset["file"] for asset in manifest["assets"].values()
            }
            if {member.filename for member in members} != expected_files:
                raise ThemeImportError(
                    "Das Theme-Paket enthält fehlende oder nicht deklarierte Dateien."
                )
        except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
            if isinstance(exc, ThemeImportError):
                raise
            raise ThemeImportError(str(exc)) from exc

        metadata = manifest["theme"]
        if DisplayThemeVersion.objects.filter(
            slug=slug, version=metadata["version"]
        ).exists():
            raise ThemeImportError("Diese Theme-Version ist bereits vorhanden.")

        with transaction.atomic():
            version = DisplayThemeVersion.objects.create(
                slug=slug,
                name=str(metadata["name"])[:128],
                version=metadata["version"],
                manifest=manifest,
                uploaded_by=user,
            )
            try:
                for asset_id, asset in manifest["assets"].items():
                    payload = (root / asset["file"]).read_bytes()
                    stored = DisplayThemeAsset(
                        theme_version=version,
                        asset_id=asset_id,
                        sha256=asset["sha256"],
                        size=len(payload),
                        content_type=theme_asset_content_type(asset),
                    )
                    stored.file.save(asset["file"], ContentFile(payload), save=False)
                    stored.save()
            except Exception:
                for stored in version.assets.all():
                    stored.delete()
                raise
    clear_theme_cache()
    return version


def _validated_members(archive):
    members = archive.infolist()
    if not members or len(members) > MAX_PACKAGE_FILES:
        raise ThemeImportError("Das Theme-Paket enthält zu viele Dateien.")
    total_size = 0
    seen = set()
    for member in members:
        path = Path(member.filename)
        mode = member.external_attr >> 16
        if (
            member.is_dir()
            or member.flag_bits & 0x1
            or stat.S_ISLNK(mode)
            or path.name != member.filename
            or member.filename in seen
        ):
            raise ThemeImportError("Das Theme-Paket enthält einen unsicheren Pfad.")
        seen.add(member.filename)
        total_size += member.file_size
        if member.filename != "theme.json":
            size_limit = (
                MAX_FONT_ASSET_BYTES
                if member.filename.lower().endswith((".ttf", ".otf"))
                else MAX_ASSET_BYTES
            )
            if member.file_size > size_limit:
                raise ThemeImportError("Ein Theme-Asset ist zu groß.")
    if total_size > MAX_UNCOMPRESSED_BYTES:
        raise ThemeImportError("Das entpackte Theme-Paket ist zu groß.")
    return members
