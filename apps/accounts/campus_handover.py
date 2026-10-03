"""Campus Clubs & Societies Committee Head handover."""

from apps.clubs.handover import parse_committee
from apps.clubs.models import ClubMembership
from apps.core.tenancy import is_platform_operator

from .models import User

HEAD_POSITION_KEYS = {
    "committee head",
    "committee_head",
    "chair",
    "chairperson",
    "chair person",
    "head",
    "c&s chair",
    "clubs and societies committee head",
}


def is_head_position(position: str) -> bool:
    key = " ".join(str(position or "").lower().replace("_", " ").split())
    if "deputy" in key or key.startswith("vice "):
        return False
    return key in HEAD_POSITION_KEYS or key.endswith(" committee head")


def incoming_heads(seats):
    return [seat for seat in seats if is_head_position(seat["position"])]


def current_campus_committee(institution):
    seats = []
    qs = User.objects.filter(
        institution=institution,
        role=User.Role.COMMITTEE_HEAD,
        is_active=True,
    ).order_by("last_name", "first_name")
    for user in qs:
        seats.append(
            {
                "name": user.get_full_name() or user.username,
                "email": user.email,
                "position": "Committee Head",
            }
        )
    return seats


def _campus_user(institution, email: str):
    return User.objects.filter(email__iexact=email, institution=institution).first()


def _fallback_after_head(user):
    if user.role in (User.Role.STAFF, User.Role.SYSTEM_ADMIN):
        return
    still_leads = ClubMembership.objects.filter(
        user=user,
        role=ClubMembership.MembershipRole.LEADER,
        status=ClubMembership.Status.APPROVED,
        is_active=True,
    ).exists()
    user.role = User.Role.CLUB_LEADER if still_leads else User.Role.STUDENT
    user.save(update_fields=["role", "updated_at"])


def apply_campus_committee_handover(handover):
    institution = handover.institution
    outgoing = parse_committee(handover.outgoing_committee or [], label="outgoing")
    incoming = parse_committee(handover.incoming_committee or [], label="incoming")
    heads = incoming_heads(incoming)
    if not heads:
        raise ValueError("Name at least one incoming Committee Head.")

    missing = []
    incoming_users = {}
    for seat in incoming:
        if not institution.accepts_email(seat["email"]):
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

    incoming_head_emails = {seat["email"] for seat in heads}

    current_heads = User.objects.filter(
        institution=institution,
        role=User.Role.COMMITTEE_HEAD,
        is_active=True,
    )
    for person in current_heads:
        if person.email.lower() not in incoming_head_emails:
            _fallback_after_head(person)

    for seat in outgoing:
        person = _campus_user(institution, seat["email"])
        if person and person.email.lower() not in incoming_head_emails and person.role == User.Role.COMMITTEE_HEAD:
            _fallback_after_head(person)

    primary = None
    for seat in heads:
        person = incoming_users[seat["email"]]
        if person.role in (User.Role.STAFF, User.Role.SYSTEM_ADMIN):
            raise ValueError(f"{seat['email']} is staff or campus admin and cannot become Committee Head.")
        person.role = User.Role.COMMITTEE_HEAD
        person.save(update_fields=["role", "updated_at"])
        if primary is None:
            primary = person

    if primary:
        handover.incoming = primary
        handover.incoming_email = primary.email
    return handover


def can_confirm_campus_handover(user, handover):
    if not user or not user.is_authenticated:
        return False
    if is_platform_operator(user):
        return True
    return (
        user.role == User.Role.SYSTEM_ADMIN
        and user.institution_id
        and user.institution_id == handover.institution_id
    )
