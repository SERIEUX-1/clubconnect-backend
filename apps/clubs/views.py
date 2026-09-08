from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.core.permissions import IsCommitteeHead, IsOwnClubLeader

from .models import Club, ClubMembership
from .serializers import ClubManageSerializer, ClubMembershipSerializer, ClubPublicSerializer


class ClubViewSet(viewsets.ModelViewSet):
    """
    GET  /api/clubs/            -> Discover Clubs directory (public serializer, any authenticated user)
    POST /api/clubs/            -> Committee Head only (club recognition workflow)
    PATCH/api/clubs/{id}/       -> Club Leader (own club) or Committee
    """

    queryset = Club.objects.filter(is_archived=False)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["category", "status"]
    search_fields = ["name", "category", "description"]

    def get_serializer_class(self):
        if self.action in ("list", "retrieve") and not self._acting_as_manager():
            return ClubPublicSerializer
        return ClubManageSerializer

    def _acting_as_manager(self) -> bool:
        user = self.request.user
        return user.is_authenticated and (
            user.role in (User.Role.COMMITTEE_HEAD, User.Role.COMMITTEE_MEMBER, User.Role.DEAN_ADMIN)
            or (self.kwargs.get("pk") and Club.objects.filter(pk=self.kwargs["pk"], memberships__user=user,
                                                                memberships__role=ClubMembership.MembershipRole.LEADER).exists())
        )

    def get_permissions(self):
        if self.action == "create":
            return [permissions.IsAuthenticated(), IsCommitteeHead()]
        if self.action in ("update", "partial_update", "destroy"):
            return [permissions.IsAuthenticated(), IsOwnClubLeader()]
        if self.action in ("list", "retrieve", "portfolio"):
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    @action(detail=True, methods=["get"])
    def portfolio(self, request, pk=None):
        """Public/approved storytelling view (PRS Section 6): Problem ->
        Objective -> What we did -> Who participated -> Who benefited ->
        Evidence -> Results -> Lessons -> Next steps. Aggregates verified
        activities + impact projects; never surfaces unverified evidence
        or confidential scores to non-committee viewers."""
        club = self.get_object()
        data = ClubPublicSerializer(club).data
        data["verified_activities"] = list(
            club.activities.filter(status="verified").values("title", "objective", "date_time", "report_text")
        )
        data["impact_projects"] = list(
            club.impact_projects.values(
                "title", "problem_statement", "objective", "beneficiaries_description", "outcomes", "next_steps"
            )
        )
        return Response(data)


class ClubMembershipViewSet(viewsets.ModelViewSet):
    queryset = ClubMembership.objects.all()
    serializer_class = ClubMembershipSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in (User.Role.COMMITTEE_HEAD, User.Role.DEAN_ADMIN):
            return ClubMembership.objects.all()
        # Students see their own memberships; leaders see their club's roster.
        return ClubMembership.objects.filter(user=user) | ClubMembership.objects.filter(
            club__memberships__user=user, club__memberships__role=ClubMembership.MembershipRole.LEADER
        )

    def perform_create(self, serializer):
        # A join request always starts as REQUESTED — approval is a
        # separate authorized action, never implicit on creation.
        serializer.save(user=self.request.user, status=ClubMembership.Status.REQUESTED)
