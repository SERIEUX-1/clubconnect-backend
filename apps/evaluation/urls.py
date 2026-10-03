from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AppealViewSet,
    CampusAnalyticsView,
    CampusBriefView,
    EvaluationCriterionViewSet,
    EvaluationCycleViewSet,
    MonthlyEvaluationView,
    ScoreViewSet,
)

router = DefaultRouter()
router.register("evaluation-cycles", EvaluationCycleViewSet, basename="evaluation-cycle")
router.register("evaluation-criteria", EvaluationCriterionViewSet, basename="evaluation-criterion")
router.register("scores", ScoreViewSet, basename="score")
router.register("appeals", AppealViewSet, basename="appeal")

urlpatterns = [
    path("monthly-evaluations/", MonthlyEvaluationView.as_view(), name="monthly-evaluations"),
    path("campus-analytics/", CampusAnalyticsView.as_view(), name="campus-analytics"),
    path("campus-brief/", CampusBriefView.as_view(), name="campus-brief"),
] + router.urls
