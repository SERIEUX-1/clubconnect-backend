from django.db import migrations, models


def remap_roles_and_domains(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Institution = apps.get_model("accounts", "Institution")
    User.objects.filter(role="committee_member").update(role="student")
    User.objects.filter(role="dean_admin").update(role="staff")
    for institution in Institution.objects.all():
        allowed = list(institution.allowed_email_domains or [])
        if not institution.student_email_domains:
            institution.student_email_domains = allowed
        if institution.slug == "alche":
            institution.student_email_domains = ["student.alche.ac.mu", "campus.edu"]
            institution.staff_email_domains = ["alche.ac.mu"]
            institution.allowed_email_domains = [
                "student.alche.ac.mu",
                "campus.edu",
                "alche.ac.mu",
            ]
        institution.save()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_institution_user_institution"),
    ]

    operations = [
        migrations.AddField(
            model_name="institution",
            name="staff_email_domains",
            field=models.JSONField(
                default=list,
                help_text='Staff and lecturer mail, e.g. ["alche.ac.mu"]',
            ),
        ),
        migrations.AddField(
            model_name="institution",
            name="student_email_domains",
            field=models.JSONField(
                default=list,
                help_text='Student school mail, e.g. ["student.alche.ac.mu"]',
            ),
        ),
        migrations.RunPython(remap_roles_and_domains, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="institution",
            name="allowed_email_domains",
            field=models.JSONField(
                default=list,
                help_text="Legacy combined list. Prefer student_email_domains and staff_email_domains.",
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("student", "Student"),
                    ("club_leader", "Club Leader"),
                    ("committee_head", "Committee Head"),
                    ("staff", "Staff / Lecturer"),
                    ("system_admin", "System Administrator"),
                ],
                default="student",
                max_length=32,
            ),
        ),
    ]
