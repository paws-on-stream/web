from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0012_normalize_spam_threshold")]

    operations = [
        migrations.AddField(model_name="settings", name="theme_reload_generation", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="displaydevice", name="theme_cache_theme", field=models.CharField(blank=True, default="", max_length=32)),
        migrations.AddField(model_name="displaydevice", name="theme_cache_version", field=models.CharField(blank=True, default="", max_length=32)),
        migrations.AddField(model_name="displaydevice", name="theme_reload_generation", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="displaydevice", name="theme_cache_updated_at", field=models.DateTimeField(blank=True, null=True)),
    ]
