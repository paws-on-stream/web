import copy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import TestCase
from PIL import Image

from core import themes


class ThemeValidationTest(TestCase):
    def tearDown(self):
        themes._load_display_theme.cache_clear()

    def _package(self, root, *, mutate=None):
        package = Path(root) / "test-theme"
        package.mkdir()
        image_path = package / "frame.png"
        Image.new("RGBA", (4, 3), (1, 2, 3, 128)).save(image_path, format="PNG")
        digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
        manifest = {
            "schema_version": 3,
            "theme": {"id": "test-theme", "name": "Test Theme", "version": "1.0.0"},
            "assets": {
                "frame": {
                    "type": "image",
                    "file": "frame.png",
                    "format": "png",
                    "required": True,
                    "width": 4,
                    "height": 3,
                    "alpha": True,
                    "sha256": digest,
                }
            },
            "display_profile": {},
            "canvas": {},
            "fonts": {},
            "chat": {
                "background": {
                    "frame": {
                        "type": "segmented_vertical",
                        "top": "frame",
                        "middle": "frame",
                        "bottom": "frame",
                    }
                },
                "template": {"elements": [{"field": "content", "style": "text"}]},
                "styles": {"text": {"type": "text"}},
            },
            "ticker": {},
            "media": {},
            "luma": {},
            "rendering": {},
        }
        if mutate:
            mutate(manifest)
        (package / "theme.json").write_text(json.dumps(manifest), encoding="utf-8")
        return copy.deepcopy(manifest)

    def test_v3_theme_and_asset_are_validated(self):
        with TemporaryDirectory() as root:
            expected = self._package(root)
            with patch.object(themes, "THEME_ROOT", Path(root)):
                result = themes.get_display_theme("test-theme", fallback=False)
                asset = themes.get_theme_asset("test-theme", "frame")
        assert result == expected
        assert asset.file_name == "frame.png"

    def test_path_traversal_asset_is_rejected(self):
        with TemporaryDirectory() as root:
            self._package(
                root,
                mutate=lambda manifest: manifest["assets"]["frame"].update(
                    {"file": "../frame.png"}
                ),
            )
            with (
                patch.object(themes, "THEME_ROOT", Path(root)),
                self.assertRaisesRegex(ValueError, "asset path"),
            ):
                themes.get_display_theme("test-theme", fallback=False)

    def test_digest_mismatch_is_rejected(self):
        with TemporaryDirectory() as root:
            self._package(
                root,
                mutate=lambda manifest: manifest["assets"]["frame"].update(
                    {"sha256": "0" * 64}
                ),
            )
            with (
                patch.object(themes, "THEME_ROOT", Path(root)),
                self.assertRaisesRegex(ValueError, "digest does not match"),
            ):
                themes.get_display_theme("test-theme", fallback=False)

    def test_unknown_template_field_is_rejected(self):
        with TemporaryDirectory() as root:
            self._package(
                root,
                mutate=lambda manifest: manifest["chat"]["template"]["elements"][
                    0
                ].update({"field": "python_expression"}),
            )
            with (
                patch.object(themes, "THEME_ROOT", Path(root)),
                self.assertRaisesRegex(ValueError, "template field"),
            ):
                themes.get_display_theme("test-theme", fallback=False)
