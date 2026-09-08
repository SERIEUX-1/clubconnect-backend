from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import CustomTokenObtainPairView, DemoPersonasView, MeView, RegisterView, SwitchRoleView

urlpatterns = [
    path("auth/token/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/demo-personas/", DemoPersonasView.as_view(), name="demo_personas"),
    path("auth/switch-role/", SwitchRoleView.as_view(), name="switch_role"),
    path("me/", MeView.as_view(), name="me"),
]
