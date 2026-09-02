from rest_framework.routers import DefaultRouter
from .views import ImpactProjectViewSet
router = DefaultRouter()
router.register("impact-projects", ImpactProjectViewSet, basename="impact-project")
urlpatterns = router.urls
