"""
Notification delivery abstraction (PRS §18: "Pluggable notification
providers"). This module answers "how does a Notification row actually
reach the person" — email, push, SMS, in-app-only — without any calling
code needing to know which channel is active.

Usage:
    from apps.notifications.dispatch import notify, notify_people

    notify(
        recipient=user,
        category=Notification.Category.DEADLINE,
        title="Monthly report due in 3 days",
        body="Submit your December report before the 5th.",
        link_url="/reports/december",
    )
"""
from __future__ import annotations

import abc
import logging
from collections.abc import Iterable
from contextlib import contextmanager
from contextvars import ContextVar

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q

from .models import Notification

logger = logging.getLogger(__name__)

_MUTED = ContextVar("clubconnect_notify_muted", default=False)


def notifications_muted() -> bool:
    return bool(_MUTED.get())


@contextmanager
def mute_notifications():
    """Seed and bulk imports must not email every demo account."""
    token = _MUTED.set(True)
    try:
        yield
    finally:
        _MUTED.reset(token)


def looks_like_email(value: str) -> bool:
    text = (value or "").strip()
    if not text or " " in text or "@" not in text:
        return False
    local, _, domain = text.partition("@")
    return bool(local) and "." in domain


def person_label(user) -> str:
    if user is None:
        return ""
    return (user.get_full_name() or "").strip() or user.email or user.username


def dashboard_path(user) -> str:
    role = getattr(user, "role", "") or ""
    return {
        "student": "/student-dashboard",
        "club_leader": "/club-leader-dashboard",
        "committee_head": "/committee-dashboard",
        "staff": "/staff-dashboard",
        "student_life": "/student-life",
        "system_admin": "/admin-dashboard",
    }.get(role, "/")


def from_email() -> str:
    return getattr(settings, "DEFAULT_FROM_EMAIL", "ClubConnect <noreply@clubconnect.local>")


def app_url(path: str = "") -> str:
    base = str(getattr(settings, "PUBLIC_APP_URL", "") or "").rstrip("/")
    if not path:
        return base
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{base}{path if path.startswith('/') else '/' + path}"


def email_channel_on() -> bool:
    names = getattr(settings, "NOTIFICATION_CHANNELS", ["in_app"])
    return "email" in names


def mail_address(to_email: str, *, subject: str, body: str) -> bool:
    """Send to an address the person themselves gave (licence form, help ticket).
    Never invent an address — skip anything that is empty or not an email."""
    email = (to_email or "").strip()
    if not looks_like_email(email) or not email_channel_on() or notifications_muted():
        return False
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=from_email(),
            recipient_list=[email],
            fail_silently=True,
        )
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Direct email to %s failed", email)
        return False


class NotificationChannel(abc.ABC):
    """A delivery channel. `send` is called AFTER the Notification row is
    already persisted — delivery failure should never lose the in-app
    record, only the external ping."""

    @abc.abstractmethod
    def send(self, notification: Notification) -> None:
        ...


class InAppOnlyChannel(NotificationChannel):
    """The Notification row itself IS the delivery."""

    def send(self, notification: Notification) -> None:
        logger.debug("In-app notification created for %s: %s", notification.recipient_id, notification.title)


class EmailChannel(NotificationChannel):
    """Mails the recipient's licensed ClubConnect account email only."""

    def send(self, notification: Notification) -> None:
        recipient = notification.recipient
        email = (getattr(recipient, "email", None) or "").strip()
        if not looks_like_email(email):
            logger.info("Skipped email for notification %s — account has no usable address", notification.id)
            return
        campus = ""
        institution = getattr(recipient, "institution", None)
        if institution:
            campus = institution.short_name or institution.name
        prefix = f"[{campus} · ClubConnect] " if campus else "[ClubConnect] "
        link = app_url(notification.link_url or dashboard_path(recipient))
        lines = [notification.body.strip() or notification.title]
        lines.append("")
        lines.append(f"Open in ClubConnect: {link}" if link else "Sign in to ClubConnect to continue.")
        lines.append("")
        lines.append(f"This was sent to {email} because this action concerns your account.")
        send_mail(
            subject=f"{prefix}{notification.title}"[:200],
            message="\n".join(lines),
            from_email=from_email(),
            recipient_list=[email],
            fail_silently=True,
        )


_CHANNEL_REGISTRY: dict[str, type[NotificationChannel]] = {
    "in_app": InAppOnlyChannel,
    "email": EmailChannel,
}


def get_active_channels() -> list[NotificationChannel]:
    names = getattr(settings, "NOTIFICATION_CHANNELS", ["in_app"])
    return [_CHANNEL_REGISTRY[name]() for name in names if name in _CHANNEL_REGISTRY]


def notify(*, recipient, category: str, title: str, body: str = "", link_url: str = "") -> Notification | None:
    """The single entry point every app should call to notify a user.
    Always creates the durable in-app Notification row first, then best-
    effort pushes it through whatever external channels are configured."""
    if recipient is None or not getattr(recipient, "is_active", True):
        return None
    if notifications_muted():
        return None
    path = link_url or dashboard_path(recipient)
    notification = Notification.objects.create(
        recipient=recipient, category=category, title=title, body=body, link_url=path,
    )
    for channel in get_active_channels():
        try:
            channel.send(notification)
        except Exception:  # noqa: BLE001 - a broken channel must never break the caller's workflow
            logger.exception("Notification channel %s failed for notification %s", channel, notification.id)
    return notification


def notify_people(
    recipients: Iterable,
    *,
    category: str,
    title: str,
    body: str = "",
    link_url: str = "",
    exclude=None,
) -> list[Notification]:
    """Notify each distinct active person. Skips the actor (`exclude`)."""
    exclude_id = getattr(exclude, "pk", exclude)
    seen: set = set()
    created: list[Notification] = []
    for person in recipients or []:
        if person is None:
            continue
        pk = getattr(person, "pk", None)
        if pk is None or pk in seen:
            continue
        if exclude_id is not None and pk == exclude_id:
            continue
        if not getattr(person, "is_active", True):
            continue
        seen.add(pk)
        row = notify(recipient=person, category=category, title=title, body=body, link_url=link_url)
        if row:
            created.append(row)
    return created


def committee_heads(institution):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    if not institution:
        return User.objects.none()
    return User.objects.filter(institution=institution, role=User.Role.COMMITTEE_HEAD, is_active=True)


def campus_admins(institution):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    if not institution:
        return User.objects.none()
    return User.objects.filter(institution=institution, role=User.Role.SYSTEM_ADMIN, is_active=True)


def accounts_for_emails(institution, emails: Iterable[str]):
    """Existing campus accounts whose licensed email matches. No invented addresses."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    cleaned = []
    seen = set()
    for raw in emails or []:
        email = (raw or "").strip()
        if not looks_like_email(email):
            continue
        key = email.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(email)
    if not cleaned:
        return User.objects.none()
    query = Q()
    for email in cleaned:
        query |= Q(email__iexact=email)
    qs = User.objects.filter(query, is_active=True)
    if institution is not None:
        qs = qs.filter(institution=institution)
    return qs
