from django.db import migrations, models
import django.core.validators


def normalize_scores(apps, schema_editor):
    Message = apps.get_model("streaming", "Message")
    for message in Message.objects.exclude(spam_score=0).iterator():
        message.spam_score = min(max(float(message.spam_score) / 10, 0.0), 1.0)
        message.save(update_fields=["spam_score"])


class Migration(migrations.Migration):
    dependencies = [("streaming", "0009_alter_message_status")]

    operations = [
        migrations.AlterField(
            model_name="message",
            name="spam_score",
            field=models.FloatField(
                default=0.0,
                validators=[
                    django.core.validators.MinValueValidator(0.0),
                    django.core.validators.MaxValueValidator(1.0),
                ],
            ),
        ),
        migrations.RunPython(normalize_scores, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="message",
            name="rejection_reason",
            field=models.CharField(
                blank=True,
                choices=[
                    ("no_event", "No active event"),
                    ("unknown", "Unknown participant"),
                    ("not_checkedin", "Not checked in"),
                    ("banned", "Banned"),
                    ("rate_limit", "Rate limited"),
                    ("offline", "Bot offline"),
                    ("spam", "Spam"),
                ],
                default="",
                max_length=32,
            ),
        ),
    ]
