from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AIChatGuidanceView,
    AICoachFeedbackView,
    AIRecommendationViewSet,
    CopilotBriefView,
    CopilotChatView,
    CopilotCommitteeBriefingView,
    CopilotHealthScanView,
    GenerateRecommendationView,
)

router = DefaultRouter()
router.register("ai-recommendations", AIRecommendationViewSet, basename="ai-recommendation")

urlpatterns = [
    path("scores/<uuid:score_id>/generate-ai-recommendation/", GenerateRecommendationView.as_view(),
         name="generate-ai-recommendation"),
    path("ai-coach/", AICoachFeedbackView.as_view(), name="ai-coach"),
    path("copilot/brief/", CopilotBriefView.as_view(), name="copilot-brief"),
    path("copilot/health-scan/", CopilotHealthScanView.as_view(), name="copilot-health-scan"),
    path("copilot/committee-briefing/", CopilotCommitteeBriefingView.as_view(), name="copilot-committee-briefing"),
    path("ai-assistant/chat/", AIChatGuidanceView.as_view(), name="ai-assistant-chat"),
    path("copilot/chat/", CopilotChatView.as_view(), name="copilot-chat"),
] + router.urls
