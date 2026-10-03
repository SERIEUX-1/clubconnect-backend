import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_institution_logo_url"),
    ]

    operations = [
        migrations.CreateModel(
            name="LicenceInquiry",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("institution_name", models.CharField(max_length=255)),
                ("country", models.CharField(blank=True, max_length=80)),
                ("city", models.CharField(blank=True, max_length=80)),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("university", "University / College"),
                            ("high_school", "High School"),
                            ("organization", "Organisation"),
                        ],
                        default="university",
                        max_length=24,
                    ),
                ),
                ("contact_name", models.CharField(max_length=160)),
                ("contact_role", models.CharField(blank=True, max_length=120)),
                ("contact_email", models.EmailField(max_length=254)),
                ("contact_phone", models.CharField(blank=True, max_length=40)),
                ("student_email_domain", models.CharField(blank=True, max_length=120)),
                ("staff_email_domain", models.CharField(blank=True, max_length=120)),
                ("message", models.TextField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("new", "New"),
                            ("contacted", "Contacted"),
                            ("licensed", "Licensed"),
                            ("declined", "Declined"),
                        ],
                        default="new",
                        max_length=20,
                    ),
                ),
                ("operator_notes", models.TextField(blank=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
