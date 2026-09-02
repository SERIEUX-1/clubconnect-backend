from rest_framework.routers import DefaultRouter

from .views import AppealViewSet, EvaluationCriterionViewSet, EvaluationCycleViewSet, ScoreViewSet

router = DefaultRouter()
router.register("evaluation-cycles", EvaluationCycleViewSet, basename="evaluation-cycle")
router.register("evaluation-criteria", EvaluationCriterionViewSet, basename="evaluation-criterion")
router.register("scores", ScoreViewSet, basename="score")
router.register("appeals", AppealViewSet, basename="appeal")

urlpatterns = router.urls
