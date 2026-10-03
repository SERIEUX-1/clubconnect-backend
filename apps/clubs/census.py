"""Share-weighted membership census and campus grant ledger.

Each unique student contributes the campus per-member grant once per year.
If they belong to N recognised clubs, each of those clubs receives grant / N.
Changing a membership immediately changes every club those people sit on.
"""

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum

from apps.accounts.models import User
from .models import Club, ClubBudgetSpend, ClubConceptNote, ClubMembership

TWOPLACE = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value) -> Decimal:
    return Decimal(value or 0).quantize(TWOPLACE, rounding=ROUND_HALF_UP)


def as_amount(value) -> str:
    return f"{money(value):.2f}"


def _year(institution):
    return institution.current_academic_year() if institution else ""


def approved_memberships(institution):
    return ClubMembership.objects.filter(
        club__institution=institution,
        club__status=Club.Status.RECOGNIZED,
        club__is_archived=False,
        status=ClubMembership.Status.APPROVED,
        is_active=True,
        is_archived=False,
    ).select_related("club", "user")


def member_club_counts(institution):
    counts = defaultdict(int)
    names = defaultdict(list)
    for row in approved_memberships(institution):
        counts[row.user_id] += 1
        names[row.user_id].append(row.club.name)
    return counts, names


def membership_window_payload(institution, user=None):
    if not institution:
        return {"open": False, "error": "No campus is attached to this account."}
    pending = ClubMembership.objects.filter(
        club__institution=institution,
        status=ClubMembership.Status.REQUESTED,
        is_archived=False,
    ).count()
    payload = {
        "open": bool(institution.membership_census_open),
        "opened_at": institution.membership_census_opened_at,
        "grant_per_member": as_amount(institution.member_grant_amount),
        "currency": institution.member_grant_currency or "USD",
        "academic_year": _year(institution),
        "pending_requests": pending,
        "rule": (
            "Each student is funded once at the campus grant. If they belong to several "
            "clubs, those clubs share that student's grant equally. Exclusive members "
            "bring the full grant to one club."
        ),
    }
    if user and user.institution_id == institution.id:
        payload["my_club_ids"] = list(
            ClubMembership.objects.filter(
                user=user,
                club__institution=institution,
                status__in=[ClubMembership.Status.APPROVED, ClubMembership.Status.REQUESTED],
                is_archived=False,
            ).values_list("club_id", flat=True)
        )
        payload["recognised_clubs"] = [
            {"id": str(c.id), "name": c.name, "category": c.category}
            for c in Club.objects.filter(
                institution=institution, status=Club.Status.RECOGNIZED, is_archived=False
            ).order_by("name")
        ]
    return payload


def _overlap_bucket(n: int) -> str:
    if n <= 1:
        return "exclusive"
    if n == 2:
        return "in_2"
    if n == 3:
        return "in_3"
    if n == 4:
        return "in_4"
    return "in_5_plus"


def build_membership_ledger(institution, *, mine_user=None):
    year = _year(institution)
    grant = money(institution.member_grant_amount)
    currency = institution.member_grant_currency or "USD"
    counts, other_names = member_club_counts(institution)

    clubs = Club.objects.filter(institution=institution, is_archived=False).order_by("name")
    if mine_user and mine_user.role not in (
        User.Role.COMMITTEE_HEAD,
        User.Role.STAFF,
        User.Role.SYSTEM_ADMIN,
    ):
        clubs = clubs.filter(
            memberships__user=mine_user,
            memberships__role=ClubMembership.MembershipRole.LEADER,
            memberships__status=ClubMembership.Status.APPROVED,
            memberships__is_active=True,
        ).distinct()

    memberships = list(approved_memberships(institution))
    by_club = defaultdict(list)
    for row in memberships:
        by_club[row.club_id].append(row)

    notes = list(
        ClubConceptNote.objects.filter(club__institution=institution, academic_year=year).select_related(
            "club", "submitted_by"
        )
    )
    spends = list(
        ClubBudgetSpend.objects.filter(club__institution=institution, academic_year=year).select_related(
            "club", "concept_note"
        )
    )
    notes_by_club = defaultdict(list)
    spends_by_club = defaultdict(list)
    for note in notes:
        notes_by_club[note.club_id].append(note)
    for spend in spends:
        spends_by_club[spend.club_id].append(spend)

    club_rows = []
    unique_ids = set(counts.keys())
    exclusive_people = {uid for uid, n in counts.items() if n == 1}

    for club in clubs:
        rows = by_club.get(club.id, [])
        buckets = {"exclusive": 0, "in_2": 0, "in_3": 0, "in_4": 0, "in_5_plus": 0}
        share_units = ZERO
        entitlement = ZERO
        members = []
        for row in rows:
            n = counts.get(row.user_id, 1) or 1
            share = money(grant / n)
            share_units += money(Decimal(1) / n)
            entitlement += share
            buckets[_overlap_bucket(n)] += 1
            others = [name for name in other_names.get(row.user_id, []) if name != club.name]
            members.append(
                {
                    "user_id": str(row.user_id),
                    "name": row.user.get_full_name() or row.user.username,
                    "email": row.user.email,
                    "role": row.role,
                    "clubs_count": n,
                    "share": as_amount(share),
                    "other_clubs": others,
                }
            )
        members.sort(key=lambda m: (-m["clubs_count"], m["name"]))
        spent = money(sum((s.amount for s in spends_by_club.get(club.id, [])), ZERO))
        reserved = ZERO
        for note in notes_by_club.get(club.id, []):
            if note.status == ClubConceptNote.Status.APPROVED:
                linked = money(
                    sum((s.amount for s in spends_by_club.get(club.id, []) if s.concept_note_id == note.id), ZERO)
                )
                reserved += max(ZERO, money(note.amount_requested) - linked)
        remaining = money(entitlement - spent)
        pct_used = money((spent / entitlement) * 100) if entitlement else ZERO
        pct_remaining = money(Decimal(100) - pct_used) if entitlement else money(100)
        latest = spends_by_club.get(club.id, [])
        comment = latest[0].comment if latest else ""
        club_rows.append(
            {
                "id": str(club.id),
                "name": club.name,
                "category": club.category,
                "status": club.status,
                "member_count": len(rows),
                "exclusive": buckets["exclusive"],
                "in_2": buckets["in_2"],
                "in_3": buckets["in_3"],
                "in_4": buckets["in_4"],
                "in_5_plus": buckets["in_5_plus"],
                "share_units": as_amount(share_units),
                "entitlement": as_amount(entitlement),
                "reserved": as_amount(reserved),
                "spent": as_amount(spent),
                "remaining": as_amount(remaining),
                "pct_used": as_amount(pct_used),
                "pct_remaining": as_amount(pct_remaining),
                "overspent": remaining < ZERO,
                "latest_comment": comment,
                "members": members,
                "concept_notes": [
                    {
                        "id": str(n.id),
                        "title": n.title,
                        "purpose": n.purpose,
                        "amount_requested": as_amount(n.amount_requested),
                        "status": n.status,
                        "submitted_by": n.submitted_by.get_full_name() or n.submitted_by.username,
                        "committee_comment": n.committee_comment,
                        "created_at": n.created_at,
                    }
                    for n in notes_by_club.get(club.id, [])
                ],
                "spends": [
                    {
                        "id": str(s.id),
                        "amount": as_amount(s.amount),
                        "comment": s.comment,
                        "spent_on": s.spent_on,
                        "concept_note_title": s.concept_note.title if s.concept_note_id else "",
                    }
                    for s in spends_by_club.get(club.id, [])
                ],
            }
        )

    pot = money(grant * len(unique_ids))
    spent_all = money(sum((Decimal(c["spent"]) for c in club_rows), ZERO))
    units_all = money(sum((Decimal(c["share_units"]) for c in club_rows), ZERO))
    return {
        "engine": "clubconnect-membership-ledger-v1",
        "academic_year": year,
        "currency": currency,
        "grant_per_member": as_amount(grant),
        "window": membership_window_payload(institution),
        "campus": {
            "recognised_clubs": Club.objects.filter(
                institution=institution, status=Club.Status.RECOGNIZED, is_archived=False
            ).count(),
            "unique_members": len(unique_ids),
            "exclusive_members": len(exclusive_people),
            "sharing_members": len(unique_ids) - len(exclusive_people),
            "share_units": as_amount(units_all),
            "pot": as_amount(pot),
            "spent": as_amount(spent_all),
            "remaining": as_amount(pot - spent_all),
            "identity_ok": abs(units_all - Decimal(len(unique_ids))) < Decimal("0.02"),
        },
        "clubs": club_rows,
        "pending": [
            {
                "id": str(m.id),
                "club_id": str(m.club_id),
                "club_name": m.club.name,
                "user_name": m.user.get_full_name() or m.user.username,
                "user_email": m.user.email,
                "source": m.source,
                "created_at": m.created_at,
            }
            for m in ClubMembership.objects.filter(
                club__institution=institution,
                status=ClubMembership.Status.REQUESTED,
                is_archived=False,
            )
            .select_related("club", "user")
            .order_by("club__name", "user__last_name")
        ],
    }


def spend_totals(club, academic_year):
    total = ClubBudgetSpend.objects.filter(club=club, academic_year=academic_year).aggregate(s=Sum("amount"))["s"]
    return money(total or 0)
