from rest_framework.routers import DefaultRouter
from .views import CollaborationViewSet
router = DefaultRouter()
router.register("collaborations", CollaborationViewSet, basename="collaboration")
urlpatterns = router.urls
