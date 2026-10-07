"""Morning desk for the Student Life office.

Leaders file the record. The student committee scores awards.
Student Life only sees charters, paused clubs, and clubs that have gone quiet.
"""

from apps.clubs.models import Club


def student_life_desk(institution) -> dict:
    from apps.ai_assistant.copilot import health_scan

    pending = Club.objects.filter(
        institution=institution,
        status=Club.Status.PENDING,
        is_archived=False,
    ).order_by("name")
    paused = Club.objects.filter(
        institution=institution,
        status=Club.Status.SUSPENDED,
        is_archived=False,
    ).order_by("name")

    waiting = [
        {
            "id": str(club.id),
            "name": club.name,
            "category": club.category,
            "kind": "charter",
            "detail": (club.description or club.mission or "A student asked for this club to be recognised.")[:240],
        }
        for club in pending
    ]
    waiting += [
        {
            "id": str(club.id),
            "name": club.name,
            "category": club.category,
            "kind": "paused",
            "detail": "This club is paused. Restore it when the office is satisfied.",
        }
        for club in paused
    ]

    quiet = []
    fine_count = 0
    try:
        scan = health_scan(institution)
    except Exception:
        scan = {}

    seen = set()
    for row in (scan.get("at_risk") or []) + (scan.get("needs_attention") or []):
        club_id = str(row.get("club_id") or "")
        if not club_id or club_id in seen:
            continue
        seen.add(club_id)
        lackings = row.get("lackings") or []
        detail = "; ".join(item.get("title", "") for item in lackings if item.get("title")) or "This club has gone quiet."
        quiet.append(
            {
                "id": club_id,
                "name": row.get("club_name") or "Club",
                "band": row.get("band") or "",
                "score": row.get("score"),
                "detail": detail,
            }
        )
    quiet.sort(key=lambda row: row.get("score") if row.get("score") is not None else 101)
    quiet_more = max(0, len(quiet) - 5)
    fine_count = len(scan.get("healthy") or [])

    return {
        "waiting": waiting,
        "quiet": quiet[:5],
        "quiet_more": quiet_more,
        "fine_count": fine_count,
        "membership_open": bool(institution.membership_census_open),
        "grant_amount": str(institution.member_grant_amount),
        "grant_currency": institution.member_grant_currency or "USD",
    }
