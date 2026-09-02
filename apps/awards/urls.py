from rest_framework.routers import DefaultRouter
from .views import AwardViewSet
router = DefaultRouter()
router.register("awards", AwardViewSet, basename="award")
urlpatterns = router.urls

from .views import HallOfExcellenceEntryViewSet
router.register("hall-of-excellence", HallOfExcellenceEntryViewSet, basename="hall-of-excellence")
urlpatterns = router.urls
