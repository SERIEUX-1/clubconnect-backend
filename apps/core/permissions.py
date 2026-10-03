"""
Central role-based access control.

PRS Section 4 is explicit: "permissions must be enforced on the
server/API/database access layer. Hiding a button in the frontend is not a
security control." Every viewset in this codebase must declare its
permission_classes from here (or compose with them) — never rely on the
frontend to decide what a role can see.
"""
from rest_framework import permissions

from apps.accounts.models import User


class IsRole(permissions.BasePermission):
    """Base class: subclass and set `allowed_roles`."""

    allowed_roles: tuple[str, ...] = ()

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in self.allowed_roles
        )


class IsStudent(IsRole):
    allowed_roles = (User.Role.STUDENT,)


class IsClubLeader(IsRole):
    allowed_roles = (User.Role.CLUB_LEADER,)


class IsCommitteeMember(IsRole):
    """Committee Head reviews evidence and scores. There is no committee-member role."""

    allowed_roles = (User.Role.COMMITTEE_HEAD,)


class IsCommitteeHead(IsRole):
    allowed_roles = (User.Role.COMMITTEE_HEAD,)


class IsDeanOrAdmin(IsRole):
    """Staff/lecturers inherit former dean access; system admin remains platform-level."""

    allowed_roles = (User.Role.STAFF, User.Role.SYSTEM_ADMIN)


class IsStaffOrAdmin(IsDeanOrAdmin):
    pass


class IsSystemAdmin(IsRole):
    allowed_roles = (User.Role.SYSTEM_ADMIN,)


class IsPlatformOperator(permissions.BasePermission):
    """ClubConnect operator with no campus attachment — licences other institutions."""

    def has_permission(self, request, view):
        from apps.core.tenancy import is_platform_operator

        return is_platform_operator(getattr(request, "user", None))


class IsCommitteeOrDean(IsRole):
    allowed_roles = (
        User.Role.COMMITTEE_HEAD,
        User.Role.STAFF,
        User.Role.SYSTEM_ADMIN,
    )


class IsClubLeaderOrCommittee(IsRole):
    allowed_roles = (
        User.Role.CLUB_LEADER,
        User.Role.COMMITTEE_HEAD,
        User.Role.STAFF,
        User.Role.SYSTEM_ADMIN,
    )


class IsOwnClubLeader(permissions.BasePermission):
    """
    Object-level check: a Club Leader may only operate on data that belongs
    to a club they lead. This is the enforcement point for PRS Section 12's
    confidentiality matrix ("Club A cannot retrieve Club B's private
    evidence, score or ranking").
    """

    def has_object_permission(self, request, view, obj):
        club = getattr(obj, "club", obj)
        if request.user.role in (
            User.Role.COMMITTEE_HEAD,
            User.Role.STAFF,
            User.Role.SYSTEM_ADMIN,
        ):
            return True
        return club.leaders.filter(id=request.user.id).exists()


class ReadOnlyOrIsCommittee(permissions.BasePermission):
    """Public/approved data: anyone authenticated can read; only committee head writes."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated and request.user.role == User.Role.COMMITTEE_HEAD
