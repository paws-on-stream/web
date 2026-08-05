import hashlib
import io
import json
import zipfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from core.models import DisplayThemeVersion, Settings
from core.themes import clear_theme_cache


def theme_package(*, slug="uploaded-east", version="1.0.0", digest=None, extra=None):
    image_file = io.BytesIO()
    Image.new("RGBA", (640, 40), (31, 43, 58, 255)).save(image_file, format="PNG")
    image = image_file.getvalue()
    digest = digest or hashlib.sha256(image).hexdigest()
    manifest = {
        "schema_version": 3,
        "theme": {"id": slug, "name": "Uploaded EAST", "version": version},
        "display_profile": {},
        "assets": {
            "frame": {
                "type": "image",
                "file": "frame.png",
                "format": "png",
                "required": True,
                "width": 640,
                "height": 40,
                "alpha": True,
                "sha256": digest,
            }
        },
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
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("theme.json", json.dumps(manifest))
        archive.writestr("frame.png", image)
        if extra:
            archive.writestr(extra[0], extra[1])
    return SimpleUploadedFile(
        f"{slug}-{version}.zip", stream.getvalue(), content_type="application/zip"
    )


@override_settings(
    MEDIA_ROOT="/private/tmp/east-theme-management-tests",
    API_AUTH_TOKEN="admin-token",
    BOT_API_AUTH_TOKEN="bot-token",
    DISPLAY_API_AUTH_TOKEN="display-token",
)
class ThemeManagementTest(TestCase):
    def setUp(self):
        clear_theme_cache()
        self.admin = get_user_model().objects.create_user(
            "admin", is_staff=True, is_superuser=True
        )
        self.staff = get_user_model().objects.create_user("staff", is_staff=True)

    def tearDown(self):
        for version in DisplayThemeVersion.objects.prefetch_related("assets"):
            for asset in list(version.assets.all()):
                asset.delete()
        clear_theme_cache()

    def test_only_admins_can_manage_themes(self):
        self.client.force_login(self.staff)
        assert self.client.get("/core/themes/").status_code == 403
        assert (
            self.client.post("/core/themes/", {"action": "upload"}).status_code == 403
        )

        self.client.force_login(self.admin)
        page = self.client.get("/core/themes/")
        assert page.status_code == 200
        self.assertContains(page, "Theme-Verwaltung")
        self.assertContains(page, "Default")

    def test_admin_imports_activates_serves_and_deletes_version(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            "/core/themes/", {"action": "upload", "package": theme_package()}
        )
        assert response.status_code == 302
        version = DisplayThemeVersion.objects.get(slug="uploaded-east")
        assert version.assets.count() == 1
        assert not version.is_current

        response = self.client.post(
            "/core/themes/",
            {"action": "activate-version", "version_id": version.pk},
        )
        assert response.status_code == 302
        version.refresh_from_db()
        assert version.is_current
        assert Settings.get_settings().overlay_theme == "uploaded-east"

        settings_response = self.client.get(
            "/api/v1/settings/1/", HTTP_X_API_TOKEN="display-token"
        )
        assert settings_response.status_code == 200
        assert settings_response.json()["overlay_theme_package"] == {
            "version": "1.0.0",
            "manifest_url": "http://testserver/api/v1/themes/uploaded-east/",
        }

        manifest = self.client.get(
            "/api/v1/themes/uploaded-east/", HTTP_X_API_TOKEN="display-token"
        )
        assert manifest.status_code == 200
        assert manifest.json()["assets"]["frame"]["url"].endswith(
            "/api/v1/themes/uploaded-east/1.0.0/assets/frame/"
        )
        asset = self.client.get(
            "/api/v1/themes/uploaded-east/1.0.0/assets/frame/",
            HTTP_X_API_TOKEN="display-token",
        )
        assert asset.status_code == 200
        assert asset["Content-Type"] == "image/png"
        assert b"".join(asset.streaming_content).startswith(b"\x89PNG")
        assert (
            self.client.get(
                "/api/v1/themes/uploaded-east/1.0.0/assets/frame/",
                HTTP_X_API_TOKEN="bot-token",
            ).status_code
            == 403
        )

        blocked = self.client.post(
            "/core/themes/", {"action": "delete-version", "version_id": version.pk}
        )
        assert blocked.status_code == 302
        assert DisplayThemeVersion.objects.filter(pk=version.pk).exists()

        self.client.post(
            "/core/themes/", {"action": "activate-builtin", "slug": "default"}
        )
        deleted = self.client.post(
            "/core/themes/", {"action": "delete-version", "version_id": version.pk}
        )
        assert deleted.status_code == 302
        assert not DisplayThemeVersion.objects.filter(pk=version.pk).exists()

    def test_import_rejects_digest_mismatch_and_path_traversal(self):
        self.client.force_login(self.admin)
        digest_response = self.client.post(
            "/core/themes/",
            {"action": "upload", "package": theme_package(digest="0" * 64)},
        )
        assert digest_response.status_code == 200
        self.assertContains(digest_response, "digest does not match")

        traversal = self.client.post(
            "/core/themes/",
            {"action": "upload", "package": theme_package(extra=("../evil.png", b"x"))},
        )
        assert traversal.status_code == 200
        self.assertContains(traversal, "unsicheren Pfad")
        assert DisplayThemeVersion.objects.count() == 0

    def test_admin_can_open_and_save_uploaded_theme_manifest(self):
        self.client.force_login(self.admin)
        self.client.post(
            "/core/themes/", {"action": "upload", "package": theme_package()}
        )
        version = DisplayThemeVersion.objects.get(slug="uploaded-east")
        editor_url = f"/core/themes/{version.pk}/edit/"
        page = self.client.get(editor_url)
        assert page.status_code == 200
        self.assertContains(page, "theme.json")
        self.assertContains(page, f"/core/themes/{version.pk}/preview/")
        self.assertContains(page, "theme-editor-draft-")

        response = self.client.post(
            editor_url,
            {"action": "save-manifest", "manifest": json.dumps(version.manifest)},
        )
        assert response.status_code == 302
        version.refresh_from_db()
        assert version.manifest["theme"]["id"] == "uploaded-east"
        assert version.version == "1.0.1"
        assert version.manifest["theme"]["version"] == "1.0.1"

    def test_active_theme_save_bumps_package_version_and_reload_generation(self):
        self.client.force_login(self.admin)
        self.client.post(
            "/core/themes/", {"action": "upload", "package": theme_package()}
        )
        version = DisplayThemeVersion.objects.get(slug="uploaded-east")
        editor_url = f"/core/themes/{version.pk}/edit/"

        self.client.post(
            "/core/themes/", {"action": "activate-version", "version_id": version.pk}
        )
        settings = Settings.get_settings()
        initial_generation = settings.theme_reload_generation
        active_response = self.client.post(
            editor_url,
            {"action": "save-manifest", "manifest": json.dumps(version.manifest)},
        )
        assert active_response.status_code == 302
        version.refresh_from_db()
        settings.refresh_from_db()
        assert version.version == "1.0.1"
        assert version.is_current
        assert settings.theme_reload_generation == initial_generation + 1
        package = self.client.get(
            "/api/v1/settings/1/", HTTP_X_API_TOKEN="display-token"
        ).json()["overlay_theme_package"]
        assert package["version"] == "1.0.1"

        self.client.post(
            "/core/themes/", {"action": "activate-builtin", "slug": "default"}
        )
        version.refresh_from_db()
        assert version.is_current
        editable_response = self.client.post(
            editor_url,
            {"action": "save-manifest", "manifest": json.dumps(version.manifest)},
        )
        assert editable_response.status_code == 302
        version.refresh_from_db()
        assert version.version == "1.0.2"

    def test_admin_can_preview_saved_theme_in_both_display_modes(self):
        self.client.force_login(self.admin)
        self.client.post(
            "/core/themes/", {"action": "upload", "package": theme_package()}
        )
        version = DisplayThemeVersion.objects.get(slug="uploaded-east")

        page = self.client.get(f"/core/themes/{version.pk}/preview/")

        assert page.status_code == 200
        self.assertContains(page, "Bubble")
        self.assertContains(page, "Crawling")
        self.assertContains(page, "Grafikrahmen")
        self.assertContains(page, "CSS-Fallback")
        asset = self.client.get(f"/core/themes/{version.pk}/preview/assets/frame/")
        assert asset.status_code == 200

    def test_imports_and_serves_ttf_and_otf_assets(self):
        for font_format, signature, content_type in (
            ("ttf", b"\x00\x01\x00\x00", "font/ttf"),
            ("otf", b"OTTO", "font/otf"),
        ):
            with self.subTest(font_format=font_format):
                self.client.force_login(self.admin)
                font = signature + b"theme-font"
                image_file = io.BytesIO()
                Image.new("RGBA", (640, 40), (31, 43, 58, 255)).save(
                    image_file, format="PNG"
                )
                image = image_file.getvalue()
                manifest = self._font_manifest(
                    font_format=font_format,
                    font=font,
                    image=image,
                    version=f"1.0.{1 if font_format == 'ttf' else 2}",
                )
                package = self._theme_package(
                    manifest, {"frame.png": image, f"font.{font_format}": font}
                )

                response = self.client.post(
                    "/core/themes/", {"action": "upload", "package": package}
                )
                assert response.status_code == 302
                version = DisplayThemeVersion.objects.get(
                    slug="uploaded-east", version=manifest["theme"]["version"]
                )
                asset = version.assets.get(asset_id="open_sans_bold")
                assert asset.content_type == content_type
                assert asset.sha256 == hashlib.sha256(font).hexdigest()

                self.client.post(
                    "/core/themes/",
                    {"action": "activate-version", "version_id": version.pk},
                )
                url = (
                    f"/api/v1/themes/uploaded-east/{version.version}/assets/"
                    "open_sans_bold/"
                )
                fetched = self.client.get(url, HTTP_X_API_TOKEN="display-token")
                assert fetched.status_code == 200
                assert fetched["Content-Type"] == content_type
                assert fetched["ETag"] == f'"{asset.sha256}"'
                assert b"".join(fetched.streaming_content) == font
                assert (
                    self.client.get(url, HTTP_X_API_TOKEN="bot-token").status_code
                    == 403
                )

    def test_import_rejects_invalid_font_assets_and_references(self):
        self.client.force_login(self.admin)
        image_file = io.BytesIO()
        Image.new("RGBA", (640, 40), (31, 43, 58, 255)).save(image_file, format="PNG")
        image = image_file.getvalue()
        valid_font = b"\x00\x01\x00\x00theme-font"
        cases = (
            ("wrong extension", "ttf", valid_font, "font.png", None, "extension"),
            ("bad signature", "ttf", b"not-a-font", "font.ttf", None, "signature"),
            ("bad checksum", "ttf", valid_font, "font.ttf", "0" * 64, "digest"),
            ("missing font asset", "ttf", valid_font, "font.ttf", None, "font asset"),
            ("image as font", "ttf", valid_font, "font.ttf", None, "font asset"),
            ("font as frame", "ttf", valid_font, "font.ttf", None, "frame"),
        )
        for label, font_format, font, font_name, digest, error in cases:
            with self.subTest(label=label):
                manifest = self._font_manifest(
                    font_format=font_format,
                    font=font,
                    image=image,
                    version=f"2.0.{len(label)}",
                    font_file=font_name,
                    font_digest=digest,
                )
                files = {"frame.png": image, font_name: font}
                if label == "missing font asset":
                    manifest["fonts"]["default"]["asset"] = "not_there"
                elif label == "image as font":
                    manifest["fonts"]["default"]["asset"] = "frame"
                elif label == "font as frame":
                    manifest["chat"]["background"]["frame"]["top"] = "open_sans_bold"
                response = self.client.post(
                    "/core/themes/",
                    {
                        "action": "upload",
                        "package": self._theme_package(manifest, files),
                    },
                )
                assert response.status_code == 200
                self.assertContains(response, error)

    def test_editor_adds_font_to_active_package_and_pushes_reload(self):
        self.client.force_login(self.admin)
        self.client.post(
            "/core/themes/", {"action": "upload", "package": theme_package()}
        )
        version = DisplayThemeVersion.objects.get(slug="uploaded-east")
        self.client.post(
            "/core/themes/", {"action": "activate-version", "version_id": version.pk}
        )
        initial_generation = Settings.get_settings().theme_reload_generation
        font = b"\x00\x01\x00\x00theme-font"
        response = self.client.post(
            f"/core/themes/{version.pk}/edit/",
            {
                "action": "upload-asset",
                "asset_key": "open_sans_bold",
                "file": SimpleUploadedFile("OpenSans-Bold.ttf", font),
            },
        )
        assert response.status_code == 302
        asset = version.assets.get(asset_id="open_sans_bold")
        assert asset.content_type == "font/ttf"

        manifest = json.loads(json.dumps(version.manifest))
        manifest["assets"]["open_sans_bold"] = {
            "type": "font",
            "file": "OpenSans-Bold.ttf",
            "format": "ttf",
            "sha256": asset.sha256,
        }
        manifest["fonts"] = {"default": {"asset": "open_sans_bold", "size": 24}}
        saved = self.client.post(
            f"/core/themes/{version.pk}/edit/",
            {"action": "save-manifest", "manifest": json.dumps(manifest)},
        )
        assert saved.status_code == 302
        version.refresh_from_db()
        assert version.version == "1.0.1"
        settings = self.client.get(
            "/api/v1/settings/1/", HTTP_X_API_TOKEN="display-token"
        )
        assert settings.json()["overlay_theme_package"]["version"] == "1.0.1"
        assert Settings.get_settings().theme_reload_generation == initial_generation + 1

    @staticmethod
    def _font_manifest(
        *, font_format, font, image, version, font_file=None, font_digest=None
    ):
        return {
            "schema_version": 3,
            "theme": {
                "id": "uploaded-east",
                "name": "Uploaded EAST",
                "version": version,
            },
            "display_profile": {},
            "assets": {
                "frame": {
                    "type": "image",
                    "file": "frame.png",
                    "format": "png",
                    "required": True,
                    "width": 640,
                    "height": 40,
                    "alpha": True,
                    "sha256": hashlib.sha256(image).hexdigest(),
                },
                "open_sans_bold": {
                    "type": "font",
                    "file": font_file or f"font.{font_format}",
                    "format": font_format,
                    "sha256": font_digest or hashlib.sha256(font).hexdigest(),
                },
            },
            "canvas": {},
            "fonts": {"default": {"asset": "open_sans_bold", "size": 24}},
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

    @staticmethod
    def _theme_package(manifest, files):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("theme.json", json.dumps(manifest))
            for name, payload in files.items():
                archive.writestr(name, payload)
        return SimpleUploadedFile(
            "font-theme.zip", stream.getvalue(), content_type="application/zip"
        )
