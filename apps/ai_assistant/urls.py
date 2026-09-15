from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AICoachFeedbackView, AIRecommendationViewSet, GenerateRecommendationView, AIChatGuidanceView

router = DefaultRouter()
router.register("ai-recommendations", AIRecommendationViewSet, basename="ai-recommendation")

urlpatterns = [
    path("scores/<uuid:score_id>/generate-ai-recommendation/", GenerateRecommendationView.as_view(),
         name="generate-ai-recommendation"),
    path("ai-coach/", AICoachFeedbackView.as_view(), name="ai-coach"),
    path("ai-assistant/chat/", AIChatGuidanceView.as_view(), name="ai-assistant-chat"),
] + router.urls
