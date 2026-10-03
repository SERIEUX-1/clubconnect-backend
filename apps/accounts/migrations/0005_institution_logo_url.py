from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_student_staff_roles"),
    ]

    operations = [
        migrations.AddField(
            model_name="institution",
            name="logo_url",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Campus mark shown after sign-in (never on the public ClubConnect landing).",
                max_length=255,
            ),
        ),
    ]
