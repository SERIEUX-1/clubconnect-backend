"""Monthly report deadline mail — only to leaders of clubs that still owe a report."""
from calendar import monthrange
from datetime import datetime, timedelta

from django.utils import timezone

from apps.accounts.models import Institution, User
from apps.clubs.models import Club, ClubMembership
from apps.notifications.dispatch import notify
from apps.notifications.models import Notification
from apps.reporting.models import MonthlyReport


def period_deadline(institution, year: int, month: int):
    day = min(int(institution.report_deadline_day or 5), monthrange(year, month)[1])
    naive = datetime(year, month, day, 23, 59)
    tz = timezone.get_current_timezone()
    return timezone.make_aware(naive, tz) if timezone.is_naive(naive) else naive


def send_deadline_reminders(*, today=None) -> int:
    today = today or timezone.localdate()
    sent = 0
    for institution in Institution.objects.filter(is_active=True):
        deadline = period_deadline(institution, today.year, today.month).date()
        if today not in (deadline, deadline - timedelta(days=3)):
            continue
        when = "today" if today == deadline else "in 3 days"
        clubs = Club.objects.filter(
            institution=institution,
            status=Club.Status.RECOGNIZED,
            is_archived=False,
        )
        for club in clubs:
            already = MonthlyReport.objects.filter(
                club=club,
                period_year=today.year,
                period_month=today.month,
                status__in=(MonthlyReport.Status.SUBMITTED, MonthlyReport.Status.LATE),
            ).exists()
            if already:
                continue
            title = f"Monthly report due {when}: {club.name}"
            leader_ids = club.memberships.filter(
                role=ClubMembership.MembershipRole.LEADER,
                status=ClubMembership.Status.APPROVED,
                is_active=True,
            ).values_list("user_id", flat=True)
            leaders = User.objects.filter(id__in=leader_ids, is_active=True)
            for leader in leaders:
                if Notification.objects.filter(recipient=leader, title=title).exists():
                    continue
                notify(
                    recipient=leader,
                    category=Notification.Category.DEADLINE,
                    title=title,
                    body=(
                        f"The Clubs & Societies Committee expects {club.name}'s "
                        f"{today.strftime('%B %Y')} report by {deadline.isoformat()}."
                    ),
                    link_url="/club-leader-dashboard",
                )
                sent += 1
    return sent
