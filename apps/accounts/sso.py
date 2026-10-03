"""Campus SSO. Tokens are verified against a real IdP; licensed email still gates access."""

from urllib.parse import urlencode
from urllib.request import urlopen
import json

from django.conf import settings

from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, institution_for_email


def sso_status():
    google_id = (getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "") or "").strip()
    microsoft_id = (getattr(settings, "MICROSOFT_OAUTH_CLIENT_ID", "") or "").strip()
    return {
        "google": bool(google_id),
        "microsoft": bool(microsoft_id),
        "licensed_email_required": True,
        "google_client_id": google_id if google_id else "",
        "note": (
            "Campus SSO only opens an account whose email is on a licensed student or staff domain. "
            "Google Workspace and Microsoft buttons appear after the campus gives ClubConnect a client ID. "
            "Until then, people sign in with that licensed email."
        ),
    }


def verify_google_id_token(id_token: str, client_id: str) -> str | None:
    if not id_token or not client_id:
        return None
    url = "https://oauth2.googleapis.com/tokeninfo?" + urlencode({"id_token": id_token})
    try:
        with urlopen(url, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    if payload.get("aud") != client_id:
        return None
    if payload.get("email_verified") in (False, "false", "False"):
        return None
    email = (payload.get("email") or "").strip().lower()
    return email or None


def issue_session(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    identity = user.public_identity()
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
        "user": identity,
    }


def user_from_verified_email(email: str, first_name="", last_name=""):
    institution = institution_for_email(email)
    if not institution:
        return None, "This email is not from an institution licensed to use ClubConnect."
    user = User.objects.filter(email__iexact=email).first()
    if user:
        if user.institution_id and not user.institution.is_active:
            return None, "This institution no longer has access to ClubConnect."
        return user, None
    username = email.split("@")[0].replace(".", "_")[:140]
    base = username
    n = 1
    while User.objects.filter(username__iexact=username).exists():
        username = f"{base}{n}"
        n += 1
    user = User(
        username=username,
        email=email,
        first_name=first_name or email.split("@")[0],
        last_name=last_name,
        role=institution.role_for_new_account(email),
        institution=institution,
    )
    user.set_unusable_password()
    user.save()
    return user, None
