import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0007_telegramaccess")]

    operations = [
        migrations.CreateModel(
            name="WebDisplayAccess",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("token_digest", models.CharField(blank=True, max_length=64)),
                ("generation", models.UUIDField(default=uuid.uuid4, editable=False)),
                ("is_active", models.BooleanField(default=False)),
                ("rotated_at", models.DateTimeField(auto_now=True)),
            ],
        )
    ]
