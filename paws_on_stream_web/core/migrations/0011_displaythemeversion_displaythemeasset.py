import core.models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0010_use_east13_display_theme"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="settings",
            name="overlay_theme",
            field=models.CharField(default="east13", max_length=32),
        ),
        migrations.CreateModel(
            name="DisplayThemeVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=32)),
                ("name", models.CharField(max_length=128)),
                ("version", models.CharField(max_length=32)),
                ("manifest", models.JSONField()),
                ("is_current", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("uploaded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="uploaded_display_themes", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("slug", "-created_at")},
        ),
        migrations.CreateModel(
            name="DisplayThemeAsset",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("asset_id", models.CharField(max_length=64)),
                ("file", models.FileField(upload_to=core.models.display_theme_asset_upload_to)),
                ("content_type", models.CharField(default="image/png", max_length=64)),
                ("sha256", models.CharField(max_length=64)),
                ("size", models.PositiveIntegerField()),
                ("theme_version", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assets", to="core.displaythemeversion")),
            ],
            options={"ordering": ("asset_id",)},
        ),
        migrations.AddConstraint(
            model_name="displaythemeversion",
            constraint=models.UniqueConstraint(fields=("slug", "version"), name="unique_display_theme_version"),
        ),
        migrations.AddConstraint(
            model_name="displaythemeversion",
            constraint=models.UniqueConstraint(condition=models.Q(("is_current", True)), fields=("slug",), name="unique_current_display_theme_version"),
        ),
        migrations.AddConstraint(
            model_name="displaythemeasset",
            constraint=models.UniqueConstraint(fields=("theme_version", "asset_id"), name="unique_display_theme_asset"),
        ),
    ]
