from django.db import migrations, models


def select_east13(apps, schema_editor):
    settings_model = apps.get_model("core", "Settings")
    settings_model.objects.filter(overlay_theme="default").update(
        overlay_theme="east13"
    )


class Migration(migrations.Migration):
    dependencies = [("core", "0009_settings_web_display_theme")]

    operations = [
        migrations.AlterField(
            model_name="settings",
            name="overlay_theme",
            field=models.CharField(
                choices=[
                    ("east13", "EAST 13"),
                    ("east-readable", "EAST Readable (Legacy)"),
                ],
                default="east13",
                max_length=32,
            ),
        ),
        migrations.RunPython(select_east13, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="settings",
            name="web_display_theme",
        ),
    ]
