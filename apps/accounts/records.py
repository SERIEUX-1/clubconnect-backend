"""Portable student record and campus admin onboarding — live data, no paid AI."""

from django.utils import timezone

from apps.attendance.models import AttendanceRecord
from apps.clubs.models import Club, ClubMembership, LeadershipTerm
from apps.core.tenancy import is_platform_operator

from .models import User


def student_transcript(user) -> dict:
    memberships = (
        ClubMembership.objects.filter(user=user)
        .select_related("club")
        .order_by("-joined_at", "-created_at")
    )
    terms = LeadershipTerm.objects.filter(user=user).select_related("club").order_by("-start_date")
    checkins = AttendanceRecord.objects.filter(user=user).select_related("event", "event__club")
    institution = user.institution
    year = institution.current_academic_year() if institution else ""
    lines = [
        "CLUBCONNECT STUDENT LEADERSHIP TRANSCRIPT",
        f"Person: {user.get_full_name() or user.username}",
        f"Email: {user.email}",
        f"Student ID: {user.student_id or '—'}",
        f"Campus: {institution.name if institution else '—'}",
        f"Academic year: {year or '—'}",
        f"Issued: {timezone.now().date().isoformat()}",
        "",
        "This is a campus activity and leadership record from ClubConnect.",
        "It is not a degree transcript. Marks from unpublished awards are not included.",
        "",
        "MEMBERSHIPS",
    ]
    club_rows = []
    for row in memberships:
        club_rows.append(
            {
                "club": row.club.name,
                "role": row.role,
                "status": row.status,
                "joined_at": row.joined_at.isoformat() if row.joined_at else None,
                "left_at": row.left_at.isoformat() if row.left_at else None,
            }
        )
        lines.append(
            f"- {row.club.name}: {row.role} ({row.status})"
            + (f", joined {row.joined_at}" if row.joined_at else "")
        )
    if not club_rows:
        lines.append("- None recorded")

    term_rows = []
    lines.append("")
    lines.append("LEADERSHIP TERMS")
    for term in terms:
        term_rows.append(
            {
                "club": term.club.name,
                "position_title": term.position_title,
                "academic_year": term.academic_year,
                "start_date": term.start_date.isoformat() if term.start_date else None,
                "end_date": term.end_date.isoformat() if term.end_date else None,
                "achievements_summary": term.achievements_summary,
            }
        )
        lines.append(
            f"- {term.club.name} · {term.position_title} · {term.academic_year}"
        )
    if not term_rows:
        lines.append("- None recorded")

    attendance_rows = []
    lines.append("")
    lines.append("VERIFIED EVENT CHECK-INS")
    for record in checkins.order_by("-checked_in_at")[:200]:
        event = record.event
        club_name = event.club.name if event and event.club_id else "—"
        title = event.title if event else "Event"
        when = record.checked_in_at.date().isoformat() if record.checked_in_at else ""
        attendance_rows.append(
            {
                "event": title,
                "club": club_name,
                "checked_in_at": record.checked_in_at.isoformat() if record.checked_in_at else None,
            }
        )
        lines.append(f"- {when} · {club_name} · {title}")
    if not attendance_rows:
        lines.append("- None recorded")

    text = "\n".join(lines) + "\n"
    return {
        "person": user.get_full_name() or user.username,
        "email": user.email,
        "student_id": user.student_id,
        "institution": institution.short_name if institution else None,
        "academic_year": year,
        "issued_at": timezone.now().isoformat(),
        "memberships": club_rows,
        "leadership_terms": term_rows,
        "attendance": attendance_rows,
        "text": text,
        "engine": "clubconnect-transcript-v1",
    }


def campus_onboarding(user) -> dict:
    if is_platform_operator(user):
        return {
            "scope": "platform",
            "items": [
                {
                    "key": "operator",
                    "label": "Licence campuses; do not bind this account to one institution.",
                    "done": True,
                }
            ],
            "complete": True,
            "academic_year": None,
        }
    institution = user.institution
    if not institution:
        return {"error": "This administrator is not attached to a campus.", "items": [], "complete": False}

    has_head = User.objects.filter(
        institution=institution, role=User.Role.COMMITTEE_HEAD, is_active=True
    ).exists()
    has_club = Club.objects.filter(institution=institution, is_archived=False).exists()
    items = [
        {
            "key": "student_domains",
            "label": "Student email domains are listed",
            "done": bool(institution.student_email_domains),
        },
        {
            "key": "staff_domains",
            "label": "Staff / lecturer email domains are listed",
            "done": bool(institution.staff_email_domains),
        },
        {
            "key": "academic_year",
            "label": "Academic year start month is set for this campus",
            "done": bool(institution.academic_year_start_month),
        },
        {
            "key": "privacy_contact",
            "label": "Campus data-protection contact email is on file",
            "done": bool(institution.privacy_contact_email),
        },
        {
            "key": "committee_head",
            "label": "A committee head is appointed",
            "done": has_head,
        },
        {
            "key": "first_club",
            "label": "At least one club record exists",
            "done": has_club,
        },
        {
            "key": "logo",
            "label": "Campus mark is uploaded for the signed-in product",
            "done": bool(institution.logo_url),
        },
    ]
    return {
        "scope": "campus",
        "institution": institution.short_name,
        "academic_year": institution.current_academic_year(),
        "items": items,
        "complete": all(item["done"] for item in items),
        "report_deadline_day": institution.report_deadline_day,
    }
