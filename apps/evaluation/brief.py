from django.utils import timezone

from apps.awards.models import HallOfExcellenceEntry

from .monthly import campus_analytics


def institutional_brief(institution) -> dict:
    analytics = campus_analytics(institution)
    year = institution.current_academic_year() if institution else analytics.get("period_year")
    honours = []
    if institution:
        honours = list(
            HallOfExcellenceEntry.objects.filter(
                club__institution=institution,
                award__is_revealed=True,
            )
            .select_related("club", "award")
            .order_by("-academic_year")[:12]
        )
    honour_lines = [
        f"- {row.academic_year} · {row.club.name} · {row.award.category_name}"
        for row in honours
    ] or ["- None published to the Hall of Excellence yet."]
    generated = timezone.now()
    text = "\n".join(
        [
            "CLUBCONNECT INSTITUTIONAL BRIEF",
            f"Campus: {institution.name if institution else analytics.get('institution')}",
            f"Academic year: {year}",
            f"Generated: {generated.isoformat()}",
            "",
            "This brief is built from live campus records. Unpublished awards marks are not included.",
            "",
            f"Recognised clubs: {analytics.get('recognized_clubs')}",
            f"Pending clubs: {analytics.get('pending_clubs')}",
            f"Students engaged (approved memberships): {analytics.get('total_students_engaged')}",
            f"Verified activities: {analytics.get('total_verified_activities')}",
            f"Verified evidence items: {analytics.get('verified_evidence_count')}",
            f"Average attendance rate (this calendar month): {analytics.get('average_attendance_rate')}%",
            "",
            "PUBLISHED HALL OF EXCELLENCE",
            *honour_lines,
            "",
        ]
    )
    return {
        **analytics,
        "academic_year": year,
        "ceremony_year": institution.current_ceremony_year() if institution else None,
        "generated_at": generated.isoformat(),
        "published_honours": [
            {
                "year": row.academic_year,
                "club": row.club.name,
                "award": row.award.category_name,
            }
            for row in honours
        ],
        "text": text,
        "engine": "clubconnect-brief-v1",
    }
