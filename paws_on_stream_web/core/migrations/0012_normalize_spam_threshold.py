from django.db import migrations, models
import django.core.validators


def normalize_threshold(apps, schema_editor):
    Settings = apps.get_model("core", "Settings")
    for settings in Settings.objects.all():
        old = float(settings.spam_threshold)
        settings.spam_threshold = 0.7 if old == 5 else min(max(old / 10, 0.1), 1.0)
        settings.save(update_fields=["spam_threshold"])


class Migration(migrations.Migration):
    dependencies = [("core", "0011_displaythemeversion_displaythemeasset")]

    operations = [
        migrations.AlterField(
            model_name="settings",
            name="spam_threshold",
            field=models.FloatField(
                default=0.7,
                validators=[
                    django.core.validators.MinValueValidator(0.1),
                    django.core.validators.MaxValueValidator(1.0),
                ],
            ),
        ),
        migrations.RunPython(normalize_threshold, migrations.RunPython.noop),
    ]
