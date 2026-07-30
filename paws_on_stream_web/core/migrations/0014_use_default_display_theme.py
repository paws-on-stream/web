from django.db import migrations, models


def use_default_theme(apps, schema_editor):
    Settings = apps.get_model("core", "Settings")
    Settings.objects.filter(overlay_theme__in=("east13", "east-readable")).update(
        overlay_theme="default"
    )


class Migration(migrations.Migration):
    dependencies = [("core", "0013_theme_reload_status")]

    operations = [
        migrations.AlterField(
            model_name="settings",
            name="overlay_theme",
            field=models.CharField(default="default", max_length=32),
        ),
        migrations.RunPython(use_default_theme, migrations.RunPython.noop),
    ]
