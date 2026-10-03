from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import BroadcastNoticeView, NotificationViewSet

router = DefaultRouter()
router.register("notifications", NotificationViewSet, basename="notification")
urlpatterns = [
    path("notices/broadcast/", BroadcastNoticeView.as_view(), name="notice-broadcast"),
] + router.urls

