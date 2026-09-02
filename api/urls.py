"""
Aggregates every domain app's urls.py under /api/. This is the single file
that changes when a new module is added — each app owns its own routes,
keeping the system modular per PRS Section 18 (Extensibility).
"""
from django.urls import include, path

urlpatterns = [
    path("", include("apps.accounts.urls")),
    path("", include("apps.clubs.urls")),
    path("", include("apps.activities.urls")),
    path("", include("apps.events.urls")),
    path("", include("apps.attendance.urls")),
    path("", include("apps.evidence.urls")),
    path("", include("apps.collaborations.urls")),
    path("", include("apps.impact.urls")),
    path("", include("apps.reporting.urls")),
    path("", include("apps.evaluation.urls")),
    path("", include("apps.ai_assistant.urls")),
    path("", include("apps.notifications.urls")),
    path("", include("apps.awards.urls")),
    path("", include("apps.resources.urls")),
    path("", include("apps.audit.urls")),
]
