from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0011_membership_census_grant"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("student", "Student"),
                    ("club_leader", "Club Leader"),
                    ("committee_head", "Committee Head"),
                    ("staff", "Staff / Lecturer"),
                    ("student_life", "Student Life"),
                    ("system_admin", "System Administrator"),
                ],
                default="student",
                max_length=32,
            ),
        ),
    ]
