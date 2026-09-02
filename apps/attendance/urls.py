from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AttendanceRecordViewSet, QRCheckInView

router = DefaultRouter()
router.register("attendance-records", AttendanceRecordViewSet, basename="attendance-record")

urlpatterns = [
    path("events/<uuid:event_id>/check-in/", QRCheckInView.as_view(), name="event-check-in"),
] + router.urls
