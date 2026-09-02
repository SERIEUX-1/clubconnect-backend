from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AIRecommendationViewSet, GenerateRecommendationView

router = DefaultRouter()
router.register("ai-recommendations", AIRecommendationViewSet, basename="ai-recommendation")

urlpatterns = [
    path("scores/<uuid:score_id>/generate-ai-recommendation/", GenerateRecommendationView.as_view(),
         name="generate-ai-recommendation"),
] + router.urls
