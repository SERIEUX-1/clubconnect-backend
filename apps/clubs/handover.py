"""Club committee handover: one form, committee-head confirm, automatic office switch."""

from django.utils import timezone

from apps.accounts.models import User

from .models import ClubMembership, LeadershipTerm

LEADER_POSITION_KEYS = {
    "president",
    "club leader",
    "club_leader",
    "leader",
    "chair",
    "chairperson",
    "chair person",
    "co-president",
    "co president",
}


def is_leader_position(position: str) -> bool:
    key = " ".join(str(position or "").lower().replace("_", " ").split())
    return key in LEADER_POSITION_KEYS or key.endswith(" president")


def membership_role_for_position(position: str) -> str:
    if is_leader_position(position):
        return ClubMembership.MembershipRole.LEADER
    return ClubMembership.MembershipRole.OFFICER


def _clean_seat(raw, required=True):
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name") or raw.get("full_name") or "").strip()
    email = str(raw.get("email") or "").strip().lower()
    position = str(raw.get("position") or raw.get("position_title") or "").strip()
    if not email or "@" not in email:
        if required:
            return None
        return None
    if not name or not position:
        return None
    return {"name": name, "email": email, "position": position}


def parse_committee(rows, *, label: str):
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"List every {label} person with name, licensed email, and position.")
    seats = []
    seen = set()
    for raw in rows:
        seat = _clean_seat(raw)
        if not seat:
            raise ValueError(f"Each {label} row needs a name, campus email, and position.")
        if seat["email"] in seen:
            raise ValueError(f"{seat['email']} appears twice on the {label} list.")
        seen.add(seat["email"])
        seats.append(seat)
    return seats


def incoming_leaders(seats):
    return [seat for seat in seats if is_leader_position(seat["position"])]


def current_office_seats(club):
    seats = []
    qs = club.memberships.filter(
        is_active=True,
        status=ClubMembership.Status.APPROVED,
        role__in=(ClubMembership.MembershipRole.LEADER, ClubMembership.MembershipRole.OFFICER),
    ).select_related("user")
    for row in qs:
        user = row.user
        position = "Club leader" if row.role == ClubMembership.MembershipRole.LEADER else "Officer"
        seats.append(
            {
                "name": user.get_full_name() or user.username,
                "email": user.email,
                "position": position,
            }
        )
    return seats


def _campus_user(institution, email: str):
    qs = User.objects.filter(email__iexact=email)
    if institution:
        qs = qs.filter(institution=institution)
    return qs.first()


def sync_campus_role(user):
    if user.role not in (User.Role.STUDENT, User.Role.CLUB_LEADER):
        return
    still_leads = ClubMembership.objects.filter(
        user=user,
        role=ClubMembership.MembershipRole.LEADER,
        status=ClubMembership.Status.APPROVED,
        is_active=True,
    ).exists()
    if still_leads and user.role != User.Role.CLUB_LEADER:
        user.role = User.Role.CLUB_LEADER
        user.save(update_fields=["role", "updated_at"])
    elif not still_leads and user.role == User.Role.CLUB_LEADER:
        user.role = User.Role.STUDENT
        user.save(update_fields=["role", "updated_at"])


def _set_office(club, user, membership_role, today):
    membership, _ = ClubMembership.objects.get_or_create(
        club=club,
        user=user,
        defaults={
            "role": membership_role,
            "status": ClubMembership.Status.APPROVED,
            "is_active": True,
            "joined_at": today,
        },
    )
    membership.role = membership_role
    membership.status = ClubMembership.Status.APPROVED
    membership.is_active = True
    membership.left_at = None
    if not membership.joined_at:
        membership.joined_at = today
    membership.save()
    return membership


def _leave_office(club, user, today):
    membership = ClubMembership.objects.filter(club=club, user=user).first()
    if not membership:
        return
    membership.role = ClubMembership.MembershipRole.MEMBER
    membership.status = ClubMembership.Status.APPROVED
    membership.is_active = True
    membership.save(update_fields=["role", "status", "is_active", "updated_at"])


def apply_committee_handover(handover):
    club = handover.club
    institution = club.institution
    today = timezone.now().date()
    year = (handover.academic_year or (institution.current_academic_year() if institution else "") or " ")[:9]
    outgoing = parse_committee(handover.outgoing_committee or [], label="outgoing")
    incoming = parse_committee(handover.incoming_committee or [], label="incoming")
    if not incoming_leaders(incoming):
        raise ValueError("Name at least one incoming club leader (President or Club leader).")

    missing = []
    incoming_users = {}
    for seat in incoming:
        if institution and not institution.accepts_email(seat["email"]):
            raise ValueError(f"{seat['email']} is not on this campus's licensed student or staff domains.")
        person = _campus_user(institution, seat["email"])
        if not person:
            missing.append(seat["email"])
        else:
            incoming_users[seat["email"]] = person
    if missing:
        raise ValueError(
            "These incoming people must already have a ClubConnect account on this campus: "
            + ", ".join(missing)
        )

    incoming_emails = {seat["email"] for seat in incoming}
    touched = set()

    current_officers = club.memberships.filter(
        is_active=True,
        role__in=(ClubMembership.MembershipRole.LEADER, ClubMembership.MembershipRole.OFFICER),
    ).select_related("user")
    for row in current_officers:
        email = row.user.email.lower()
        if email not in incoming_emails:
            _leave_office(club, row.user, today)
            touched.add(row.user.id)

    for seat in outgoing:
        person = _campus_user(institution, seat["email"])
        if not person:
            continue
        LeadershipTerm.objects.create(
            club=club,
            user=person,
            position_title=seat["position"][:100],
            academic_year=year,
            start_date=today,
            end_date=today,
            achievements_summary=handover.achievements_summary,
            lessons_learned=handover.notes,
        )
        if seat["email"] not in incoming_emails:
            _leave_office(club, person, today)
            touched.add(person.id)

    primary = None
    for seat in incoming:
        person = incoming_users[seat["email"]]
        _set_office(club, person, membership_role_for_position(seat["position"]), today)
        touched.add(person.id)
        if primary is None and is_leader_position(seat["position"]):
            primary = person

    for user_id in touched:
        person = User.objects.filter(id=user_id).first()
        if person:
            sync_campus_role(person)

    if primary:
        handover.incoming = primary
        handover.incoming_email = primary.email
    return handover
