from rest_framework.routers import DefaultRouter

from .views import ClubMembershipViewSet, ClubViewSet

router = DefaultRouter()
router.register("clubs", ClubViewSet, basename="club")
router.register("club-memberships", ClubMembershipViewSet, basename="club-membership")

urlpatterns = router.urls
