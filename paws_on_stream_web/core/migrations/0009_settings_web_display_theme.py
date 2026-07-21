from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0008_webdisplayaccess")]

    operations = [
        migrations.AddField(
            model_name="settings",
            name="web_display_theme",
            field=models.CharField(
                choices=[("east-readable", "EAST Readable")],
                default="east-readable",
                max_length=32,
            ),
        )
    ]
