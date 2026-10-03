"""Institution scoping helpers.

Every list of clubs, reports, awards, and evaluations belongs to the
institution the signed-in user belongs to. System administrators without
an institution assignment may operate across tenants (platform operator).
"""


def user_institution_id(user):
    if not getattr(user, "is_authenticated", False):
        return None
    return getattr(user, "institution_id", None)


def is_platform_operator(user) -> bool:
    from apps.accounts.models import User

    return bool(
        getattr(user, "is_authenticated", False)
        and user.role == User.Role.SYSTEM_ADMIN
        and not user.institution_id
    )


def scope_queryset(qs, user, institution_field="institution"):
    """Filter a queryset that has a direct FK to Institution."""
    if is_platform_operator(user):
        return qs
    inst_id = user_institution_id(user)
    if not inst_id:
        return qs.none()
    return qs.filter(**{institution_field: inst_id})


def scope_club_owned(qs, user, club_field="club"):
    """Filter a queryset that belongs to a Club (and therefore an institution)."""
    if is_platform_operator(user):
        return qs
    inst_id = user_institution_id(user)
    if not inst_id:
        return qs.none()
    return qs.filter(**{f"{club_field}__institution_id": inst_id})
