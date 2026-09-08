"""
Club Health scoring (PRS §16). Pure computation, same pattern as
apps.evaluation.services: no HTTP, no scheduler coupling, so it's callable
from a Celery task, a `manage.py` command, or a test with equal ease.

Indicators are computed from data that already exists elsewhere in the
system (Activity, MonthlyReport, AttendanceRecord, Evidence) — nothing new
needs to be entered by club leaders just to power this.
"""
from dataclasses import dataclass
from datetime import date, timedelta

from django.db.models import Avg
from django.utils import timezone

from apps.activities.models import Activity
from apps.reporting.models import MonthlyReport
from .models import ClubHealthSnapshot


@dataclass
class HealthIndicators:
    days_since_last_activity: int | None
    report_completion_rate: float  # last 3 expected reports: fraction submitted on time
    evidence_completeness_rate: float  # verified evidence / total evidence, last 90 days


# Configurable thresholds. In a later iteration these should move to a
# SystemSetting row (PRS §16: "Committee should be able to configure which
# indicators contribute to health status") rather than living as constants
# here — this is the seam where that config would plug in.
DEFAULT_THRESHOLDS = {
    "at_risk_days_inactive": 60,
    "needs_attention_days_inactive": 30,
    "at_risk_report_completion": 0.34,       # missed 2 of last 3
    "needs_attention_report_completion": 0.67,  # missed 1 of last 3
}


def compute_indicators(club, as_of: date) -> HealthIndicators:
    last_activity = (
        Activity.objects.filter(club=club, status=Activity.Status.VERIFIED, date_time__date__lte=as_of)
        .order_by("-date_time")
        .first()
    )
    days_since_last_activity = (as_of - last_activity.date_time.date()).days if last_activity else None

    recent_reports = MonthlyReport.objects.filter(club=club, deadline__date__lte=as_of).order_by("-deadline")[:3]
    if recent_reports:
        on_time = sum(1 for r in recent_reports if r.status in (MonthlyReport.Status.SUBMITTED,))
        report_completion_rate = on_time / len(recent_reports)
    else:
        report_completion_rate = 1.0  # no reports expected yet -- don't penalize a brand-new club

    ninety_days_ago = as_of - timedelta(days=90)
    evidence_qs = club.evidence_items.filter(created_at__date__gte=ninety_days_ago)
    total_evidence = evidence_qs.count()
    verified_evidence = evidence_qs.filter(status="verified").count()
    evidence_completeness_rate = (verified_evidence / total_evidence) if total_evidence else 1.0

    return HealthIndicators(
        days_since_last_activity=days_since_last_activity,
        report_completion_rate=report_completion_rate,
        evidence_completeness_rate=evidence_completeness_rate,
    )


def determine_status(indicators: HealthIndicators, thresholds: dict = DEFAULT_THRESHOLDS) -> str:
    """
    Deliberately conservative: a club is AT_RISK if ANY single indicator
    crosses the at-risk line, not only on an aggregate score. The PRS
    frames health as an early-warning tool -- a false "healthy" is worse
    than an over-cautious "needs attention", so this favors sensitivity.
    """
    inactive = indicators.days_since_last_activity

    if (inactive is not None and inactive >= thresholds["at_risk_days_inactive"]) or \
       indicators.report_completion_rate <= thresholds["at_risk_report_completion"]:
        return ClubHealthSnapshot.Status.AT_RISK

    if (inactive is not None and inactive >= thresholds["needs_attention_days_inactive"]) or \
       indicators.report_completion_rate <= thresholds["needs_attention_report_completion"]:
        return ClubHealthSnapshot.Status.NEEDS_ATTENTION

    return ClubHealthSnapshot.Status.HEALTHY


def compute_and_store_snapshot(club, as_of: date | None = None) -> ClubHealthSnapshot:
    as_of = as_of or timezone.now().date()
    indicators = compute_indicators(club, as_of)
    status = determine_status(indicators)

    snapshot, _created = ClubHealthSnapshot.objects.update_or_create(
        club=club, computed_for_date=as_of,
        defaults={
            "status": status,
            "indicators": {
                "days_since_last_activity": indicators.days_since_last_activity,
                "report_completion_rate": round(indicators.report_completion_rate, 3),
                "evidence_completeness_rate": round(indicators.evidence_completeness_rate, 3),
            },
        },
    )
    return snapshot


def compute_for_all_clubs(as_of: date | None = None) -> int:
    """Entry point for the scheduled job (Celery Beat or a nightly
    `manage.py compute_club_health` cron). Returns the number of clubs
    processed."""
    from apps.clubs.models import Club

    count = 0
    for club in Club.objects.filter(is_archived=False, status=Club.Status.RECOGNIZED):
        compute_and_store_snapshot(club, as_of=as_of)
        count += 1
    return count
