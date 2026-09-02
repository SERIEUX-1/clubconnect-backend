from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class Resource(BaseModel):
    class ResourceType(models.TextChoices):
        TEMPLATE = "template", "Template"
        POLICY = "policy", "Policy"
        GUIDE = "guide", "Guide"
        OTHER = "other", "Other"

    title = models.CharField(max_length=200)
    resource_type = models.CharField(max_length=20, choices=ResourceType.choices)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to="resources/", null=True, blank=True)
    external_link = models.URLField(blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    is_published = models.BooleanField(default=True)
