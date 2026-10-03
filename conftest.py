import pytest


@pytest.fixture(autouse=True)
def _email_locmem(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.NOTIFICATION_CHANNELS = ["in_app", "email"]
    settings.PUBLIC_APP_URL = "http://127.0.0.1:5173"
