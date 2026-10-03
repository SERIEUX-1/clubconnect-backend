from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken


class RelaxedJWTAuthentication(JWTAuthentication):
    """Invalid or demo tokens are treated as anonymous instead of 401 on public views."""

    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except (InvalidToken, AuthenticationFailed):
            return None
