from django.conf import settings
from django.db import models

from apps.activities.models import Activity
from apps.clubs.models import Club
from apps.core.models import BaseModel

ALLOWED_EXTENSIONS = ["jpg", "jpeg", "png", "webp", "mp4", "mov", "pdf"]
MAX_FILE_SIZE_MB = 200


def evidence_upload_path(instance, filename):
    return f"evidence/{instance.club_id}/{instance.activity_id or 'general'}/{filename}"


class Evidence(BaseModel):
    class EvidenceType(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"
        PDF_REPORT = "pdf_report", "PDF Report"
        CERTIFICATE = "certificate", "Certificate"
        POSTER = "poster", "Poster"
        ATTENDANCE_RECORD = "attendance_record", "Attendance Record"
        TESTIMONIAL = "testimonial", "Testimonial"
        PROJECT_DOCUMENTATION = "project_documentation", "Project Documentation"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under Review"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"

    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="evidence_items")
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, null=True, blank=True, related_name="evidence_items")

    evidence_type = models.CharField(max_length=30, choices=EvidenceType.choices)
    # In production this FileField's storage backend should point to
    # object/cloud storage (see settings.DEFAULT_FILE_STORAGE), per PRS
    # Section 7: "use object/cloud storage rather than the primary
    # relational database" for large media.
    file = models.FileField(upload_to=evidence_upload_path, blank=True)
    external_link = models.URLField(blank=True)
    caption = models.CharField(max_length=300, blank=True)
    impact_project = models.ForeignKey(
        "impact.ImpactProject",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evidence_items",
    )

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ["-created_at"]


class EvidenceReview(BaseModel):
    """Preserves full verification history — original + every re-review,
    never overwritten (PRS Section 7)."""

    evidence = models.ForeignKey(Evidence, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=Evidence.Status.choices)
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
