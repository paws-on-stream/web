from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("streaming", "0003_event_streaming_e_is_acti_20e2e9_idx_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="MediaAsset",
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
                ("file", models.FileField(upload_to="media_assets/%Y/%m/")),
                (
                    "media_type",
                    models.CharField(
                        choices=[
                            ("photo", "Photo"),
                            ("gif", "GIF"),
                            ("sticker", "Sticker"),
                        ],
                        max_length=16,
                    ),
                ),
                ("telegram_file_id", models.CharField(max_length=255)),
                (
                    "telegram_file_unique_id",
                    models.CharField(blank=True, max_length=255, unique=True),
                ),
                ("sticker_emoji", models.CharField(blank=True, default="", max_length=64)),
                ("source_filename", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="mediaasset",
            index=models.Index(
                fields=["media_type", "created_at"],
                name="streaming_media_mt_idx",
            ),
        ),
        migrations.AddField(
            model_name="message",
            name="media_asset",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="messages",
                to="streaming.mediaasset",
            ),
        ),
    ]
