from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ClubBudgetSpendViewSet,
    ClubConceptNoteViewSet,
    ClubMembershipViewSet,
    ClubViewSet,
    LeadershipHandoverViewSet,
    MembershipCensusConfirmView,
    MembershipCensusDeclareView,
    MembershipCensusWindowView,
    MembershipLedgerMineView,
    MembershipLedgerView,
)

router = DefaultRouter()
router.register("clubs", ClubViewSet, basename="club")
router.register("club-memberships", ClubMembershipViewSet, basename="club-membership")
router.register("leadership-handovers", LeadershipHandoverViewSet, basename="leadership-handover")
router.register("club-concept-notes", ClubConceptNoteViewSet, basename="club-concept-note")
router.register("club-budget-spends", ClubBudgetSpendViewSet, basename="club-budget-spend")

urlpatterns = [
    path("membership-census/window/", MembershipCensusWindowView.as_view(), name="membership_census_window"),
    path("membership-census/declare/", MembershipCensusDeclareView.as_view(), name="membership_census_declare"),
    path("membership-census/confirm/", MembershipCensusConfirmView.as_view(), name="membership_census_confirm"),
    path("membership-ledger/", MembershipLedgerView.as_view(), name="membership_ledger"),
    path("membership-ledger/mine/", MembershipLedgerMineView.as_view(), name="membership_ledger_mine"),
] + router.urls
