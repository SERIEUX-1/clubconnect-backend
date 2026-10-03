"""
Deterministic monthly club evaluation.

This is not an LLM. It reads reports, attendance, collaborations, and
evidence that already exist in ClubConnect and produces a scored
assessment plus explicit lackings a committee can act on.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime

from django.db.models import Q
from django.utils import timezone

from apps.attendance.models import AttendanceRecord
from apps.clubs.models import Club, ClubMembership
from apps.collaborations.models import Collaboration
from apps.evidence.models import Evidence
from apps.events.models import Event
from apps.reporting.models import MonthlyReport


def month_bounds(year: int, month: int):
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return start, end


def evaluate_club_month(club: Club, year: int, month: int) -> dict:
    start, end = month_bounds(year, month)

    report = MonthlyReport.objects.filter(
        club=club, period_year=year, period_month=month
    ).first()

    events = Event.objects.filter(club=club, starts_at__date__gte=start, starts_at__date__lte=end)
    event_count = events.count()
    attendance_qs = AttendanceRecord.objects.filter(
        event__club=club, checked_in_at__date__gte=start, checked_in_at__date__lte=end
    )
    attendance_count = attendance_qs.count()
    unique_attendees = attendance_qs.values("user_id").distinct().count()

    approved_members = ClubMembership.objects.filter(
        club=club, status=ClubMembership.Status.APPROVED, is_active=True
    ).count()

    club_q = Q(initiating_club=club) | Q(partner_club=club)
    collab_count = Collaboration.objects.filter(
        club_q,
        status=Collaboration.Status.CONFIRMED,
        confirmed_at__date__gte=start,
        confirmed_at__date__lte=end,
    ).count()
    pending_collabs = Collaboration.objects.filter(
        club_q,
        status=Collaboration.Status.PENDING,
    ).count()

    evidence_qs = Evidence.objects.filter(club=club, created_at__date__gte=start, created_at__date__lte=end)
    evidence_total = evidence_qs.count()
    evidence_verified = evidence_qs.filter(status=Evidence.Status.VERIFIED).count()

    lackings: list[dict] = []
    score = 100
    strengths: list[str] = []

    if not report or report.status in (MonthlyReport.Status.MISSING, MonthlyReport.Status.DRAFT):
        lackings.append({
            "code": "missing_report",
            "severity": "critical",
            "title": "Monthly report not submitted",
            "detail": "Committee cannot evaluate narrative impact, challenges, or next steps without a submitted monthly report.",
        })
        score -= 30
    elif report.status == MonthlyReport.Status.LATE:
        lackings.append({
            "code": "late_report",
            "severity": "watch",
            "title": "Monthly report was late",
            "detail": "The report arrived after the deadline. Completeness is credited; punctuality is not.",
        })
        score -= 10
        strengths.append("Report is on file (submitted late).")
    else:
        strengths.append("Monthly report submitted.")
        if report.challenges:
            strengths.append("Challenges were documented honestly.")
        else:
            lackings.append({
                "code": "thin_report",
                "severity": "watch",
                "title": "Report is missing challenges",
                "detail": "A complete report names what did not go well so the committee can help, not only celebrate.",
            })
            score -= 5

    if event_count == 0:
        lackings.append({
            "code": "no_events",
            "severity": "critical",
            "title": "No events scheduled this month",
            "detail": "A recognised club should run or host at least one member-facing activity per evaluation month.",
        })
        score -= 20
    else:
        strengths.append(f"{event_count} event(s) scheduled.")

    if event_count and attendance_count == 0:
        lackings.append({
            "code": "no_attendance",
            "severity": "critical",
            "title": "Events had no verified attendance",
            "detail": "QR check-in was not used, or no members scanned. Attendance is the proof that the event happened.",
        })
        score -= 20
    elif event_count:
        strengths.append(f"{attendance_count} verified check-ins ({unique_attendees} unique members).")
        if approved_members and unique_attendees / max(approved_members, 1) < 0.25:
            lackings.append({
                "code": "low_participation",
                "severity": "watch",
                "title": "Low member participation",
                "detail": f"Only {unique_attendees} of {approved_members} approved members checked in this month.",
            })
            score -= 10

    if collab_count == 0:
        lackings.append({
            "code": "no_collaboration",
            "severity": "watch",
            "title": "No confirmed collaboration this month",
            "detail": "Cross-club work is optional each month, but it is a CCEA bonus criterion. Pending proposals do not count until the partner club confirms.",
        })
        score -= 8
    else:
        strengths.append(f"{collab_count} confirmed collaboration(s).")

    if pending_collabs:
        lackings.append({
            "code": "pending_collaboration",
            "severity": "info",
            "title": "Unconfirmed collaboration proposals",
            "detail": f"{pending_collabs} proposal(s) are still waiting for the partner club. They award no points until confirmed.",
        })

    if evidence_total == 0:
        lackings.append({
            "code": "no_evidence",
            "severity": "critical",
            "title": "No evidence uploaded this month",
            "detail": "Photos, rosters, and minutes are what the committee verifies. Activity without evidence cannot be scored.",
        })
        score -= 15
    elif evidence_verified == 0:
        lackings.append({
            "code": "unverified_evidence",
            "severity": "watch",
            "title": "Evidence is still waiting for committee review",
            "detail": f"{evidence_total} item(s) uploaded; none verified yet.",
        })
        score -= 8
    else:
        strengths.append(f"{evidence_verified}/{evidence_total} evidence items verified.")

    score = max(0, min(100, score))
    if score >= 75:
        band = "healthy"
    elif score >= 50:
        band = "needs_attention"
    else:
        band = "at_risk"

    return {
        "club_id": str(club.id),
        "club_name": club.name,
        "category": club.category,
        "period_year": year,
        "period_month": month,
        "score": score,
        "band": band,
        "signals": {
            "report_status": report.status if report else "missing",
            "events": event_count,
            "attendance_checkins": attendance_count,
            "unique_attendees": unique_attendees,
            "approved_members": approved_members,
            "confirmed_collaborations": collab_count,
            "pending_collaborations": pending_collabs,
            "evidence_uploaded": evidence_total,
            "evidence_verified": evidence_verified,
        },
        "lackings": lackings,
        "strengths": strengths,
        "evaluated_at": timezone.now().isoformat(),
        "engine": "clubconnect-monthly-rules-v1",
    }


def evaluate_institution_month(institution, year: int, month: int) -> dict:
    clubs = Club.objects.filter(
        is_archived=False,
        institution=institution,
        status=Club.Status.RECOGNIZED,
    ).order_by("name")
    results = [evaluate_club_month(club, year, month) for club in clubs]
    results.sort(key=lambda r: r["score"])
    return {
        "institution": institution.short_name if institution else None,
        "period_year": year,
        "period_month": month,
        "club_count": len(results),
        "at_risk": [r for r in results if r["band"] == "at_risk"],
        "needs_attention": [r for r in results if r["band"] == "needs_attention"],
        "healthy": [r for r in results if r["band"] == "healthy"],
        "clubs": results,
        "engine": "clubconnect-monthly-rules-v1",
    }


def campus_analytics(institution) -> dict:
    """Live staff/lecturer dashboard numbers for one licensed campus."""
    from calendar import month_abbr

    from django.db.models import Count, Sum
    from django.db.models.functions import TruncMonth

    from apps.activities.models import Activity
    from apps.clubs.models import Club, ClubMembership
    from apps.evidence.models import Evidence
    from apps.events.models import Event
    from apps.impact.models import ImpactProject

    clubs = Club.objects.filter(institution=institution, is_archived=False)
    recognized = clubs.filter(status=Club.Status.RECOGNIZED)
    pending = clubs.filter(status=Club.Status.PENDING).count()
    recognized_count = recognized.count()

    members = (
        ClubMembership.objects.filter(
            club__institution=institution,
            status=ClubMembership.Status.APPROVED,
            is_active=True,
        )
        .values("user_id")
        .distinct()
        .count()
    )

    now = timezone.now()
    start, end = month_bounds(now.year, now.month)
    month_checkins = AttendanceRecord.objects.filter(
        event__club__institution=institution,
        checked_in_at__date__gte=start,
        checked_in_at__date__lte=end,
    )
    unique_month = month_checkins.values("user_id").distinct().count()
    attendance_rate = round((unique_month / members) * 100, 1) if members else 0

    verified_activities = Activity.objects.filter(
        club__institution=institution, status=Activity.Status.VERIFIED
    ).count()
    verified_evidence = Evidence.objects.filter(
        club__institution=institution, status=Evidence.Status.VERIFIED
    ).count()
    beneficiaries = (
        ImpactProject.objects.filter(club__institution=institution).aggregate(
            total=Sum("estimated_beneficiaries_count")
        ).get("total")
        or 0
    )
    if not beneficiaries:
        beneficiaries = (
            Activity.objects.filter(club__institution=institution).aggregate(
                total=Sum("actual_participation")
            ).get("total")
            or 0
        )

    cat_rows = list(
        recognized.values("category").annotate(count=Count("id")).order_by("category")
    )
    total_cat = sum(row["count"] for row in cat_rows) or 1
    category_distribution = [
        {
            "category": row["category"] or "General",
            "count": row["count"],
            "percentage": round((row["count"] / total_cat) * 100),
        }
        for row in cat_rows
    ]

    trend_qs = (
        Event.objects.filter(club__institution=institution)
        .annotate(bucket=TruncMonth("starts_at"))
        .values("bucket")
        .annotate(count=Count("id"))
        .order_by("bucket")
    )
    monthly_activity_trend = []
    for row in trend_qs:
        bucket = row["bucket"]
        if not bucket:
            continue
        monthly_activity_trend.append(
            {"month": month_abbr[bucket.month], "count": row["count"]}
        )
    monthly_activity_trend = monthly_activity_trend[-5:]

    return {
        "institution": institution.short_name,
        "academic_year": institution.current_academic_year() if institution else None,
        "ceremony_year": institution.current_ceremony_year() if institution else None,
        "report_deadline_day": institution.report_deadline_day if institution else None,
        "total_active_clubs": recognized_count + pending,
        "recognized_clubs": recognized_count,
        "pending_clubs": pending,
        "total_students_engaged": members,
        "average_attendance_rate": attendance_rate,
        "total_verified_activities": verified_activities,
        "total_beneficiaries_reached": beneficiaries,
        "verified_evidence_count": verified_evidence,
        "category_distribution": category_distribution,
        "monthly_activity_trend": monthly_activity_trend,
        "period_year": now.year,
        "period_month": now.month,
    }
