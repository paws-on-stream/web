from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("participants", "0002_participant_participant_checked_279020_idx_and_more")]

    operations = [
        migrations.AddField(
            model_name="participant",
            name="checked_in_override",
            field=models.BooleanField(
                blank=True,
                choices=[
                    (None, "Automatisch (Reg-System)"),
                    (True, "Immer eingecheckt"),
                    (False, "Immer ausgecheckt"),
                ],
                default=None,
                null=True,
            ),
        )
    ]
