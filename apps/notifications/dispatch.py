"""
Notification delivery abstraction (PRS §18: "Pluggable notification
providers"). This module answers "how does a Notification row actually
reach the person" — email, push, SMS, in-app-only — without any calling
code (evidence review, deadline reminders, Club Health alerts) needing to
know which channel is active. Same shape as apps.ai_assistant.providers,
deliberately, so the codebase only has one abstraction pattern to learn.

Usage:
    from apps.notifications.dispatch import notify

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

from django.conf import settings

from .models import Notification

logger = logging.getLogger(__name__)


class NotificationChannel(abc.ABC):
    """A delivery channel. `send` is called AFTER the Notification row is
    already persisted — delivery failure should never lose the in-app
    record, only the external ping."""

    @abc.abstractmethod
    def send(self, notification: Notification) -> None:
        ...


class InAppOnlyChannel(NotificationChannel):
    """Default/no-op channel: the Notification row itself IS the delivery.
    Safe default for local dev and for institutions without email/push
    configured yet."""

    def send(self, notification: Notification) -> None:
        logger.debug("In-app notification created for %s: %s", notification.recipient_id, notification.title)


class EmailChannel(NotificationChannel):
    """Reference implementation using Django's email backend. Configure
    EMAIL_BACKEND / EMAIL_HOST in settings to activate for real; falls
    back to console output in dev."""

    def send(self, notification: Notification) -> None:
        from django.core.mail import send_mail

        send_mail(
            subject=notification.title,
            message=notification.body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@clubconnect.local"),
            recipient_list=[notification.recipient.email],
            fail_silently=True,
        )


# Register additional channels here (push via FCM/APNs, SMS via Twilio,
# Slack/Teams webhook, etc.) following the same NotificationChannel shape.
_CHANNEL_REGISTRY: dict[str, type[NotificationChannel]] = {
    "in_app": InAppOnlyChannel,
    "email": EmailChannel,
}


def get_active_channels() -> list[NotificationChannel]:
    names = getattr(settings, "NOTIFICATION_CHANNELS", ["in_app"])
    return [_CHANNEL_REGISTRY[name]() for name in names if name in _CHANNEL_REGISTRY]


def notify(*, recipient, category: str, title: str, body: str = "", link_url: str = "") -> Notification:
    """The single entry point every app should call to notify a user.
    Always creates the durable in-app Notification row first, then best-
    effort pushes it through whatever external channels are configured."""
    notification = Notification.objects.create(
        recipient=recipient, category=category, title=title, body=body, link_url=link_url,
    )
    for channel in get_active_channels():
        try:
            channel.send(notification)
        except Exception:  # noqa: BLE001 - a broken channel must never break the caller's workflow
            logger.exception("Notification channel %s failed for notification %s", channel, notification.id)
    return notification
