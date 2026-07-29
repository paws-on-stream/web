import hashlib
import io
import json
import zipfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from core.models import DisplayThemeVersion, Settings
from core.themes import clear_theme_cache


def theme_package(*, slug="uploaded-east", version="1.0.0", digest=None, extra=None):
    image = (
        Path(__file__).resolve().parent / "themes" / "east13" / "chat-middle.png"
    ).read_bytes()
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
        self.assertContains(page, "EAST 13")

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
        assert b"".join(asset.streaming_content).startswith(b"\x89PNG")

        blocked = self.client.post(
            "/core/themes/", {"action": "delete-version", "version_id": version.pk}
        )
        assert blocked.status_code == 302
        assert DisplayThemeVersion.objects.filter(pk=version.pk).exists()

        self.client.post(
            "/core/themes/", {"action": "activate-builtin", "slug": "east13"}
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

        response = self.client.post(
            editor_url,
            {"action": "save-manifest", "manifest": json.dumps(version.manifest)},
        )
        assert response.status_code == 302
        version.refresh_from_db()
        assert version.manifest["theme"]["id"] == "uploaded-east"

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
        asset = self.client.get(
            f"/core/themes/{version.pk}/preview/assets/frame/"
        )
        assert asset.status_code == 200
