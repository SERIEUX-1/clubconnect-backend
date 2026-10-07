from django.db.models import Count, Q
from django.utils import timezone
from django.utils.text import slugify
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.core.permissions import IsCommitteeHead, IsCommitteeOrDean, IsOwnClubLeader, IsStudentLife
from apps.core.tenancy import is_platform_operator, scope_queryset
from apps.evidence.models import Evidence

from .census import build_membership_ledger, membership_window_payload, money
from .gallery import GALLERY_TYPES, club_gallery_items, looks_like_video, serialize_gallery_item
from .handover import (
    apply_committee_handover,
    current_office_seats,
    incoming_leaders,
    parse_committee,
)
from .models import Club, ClubBudgetSpend, ClubConceptNote, ClubMembership, LeadershipHandover
from .serializers import (
    ClubBudgetSpendSerializer,
    ClubConceptNoteSerializer,
    ClubManageSerializer,
    ClubMembershipSerializer,
    ClubPublicSerializer,
    LeadershipHandoverSerializer,
)


class ClubViewSet(viewsets.ModelViewSet):
    queryset = Club.objects.filter(is_archived=False)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["category", "status"]
    search_fields = ["name", "category", "description"]

    def get_serializer_class(self):
        if self.action == "list":
            return ClubPublicSerializer
        if self.action == "retrieve" and not self._acting_as_manager():
            return ClubPublicSerializer
        return ClubManageSerializer

    def _acting_as_manager(self) -> bool:
        user = self.request.user
        return user.is_authenticated and (
            user.role in (
                User.Role.COMMITTEE_HEAD,
                User.Role.STAFF,
                User.Role.STUDENT_LIFE,
                User.Role.SYSTEM_ADMIN,
            )
            or (
                self.kwargs.get("pk")
                and Club.objects.filter(
                    pk=self.kwargs["pk"],
                    memberships__user=user,
                    memberships__role=ClubMembership.MembershipRole.LEADER,
                ).exists()
            )
        )

    def get_queryset(self):
        qs = Club.objects.filter(is_archived=False).annotate(
            published_watch_count=Count(
                "evidence_items",
                filter=Q(
                    evidence_items__status=Evidence.Status.VERIFIED,
                    evidence_items__evidence_type__in=[
                        Evidence.EvidenceType.VIDEO,
                        Evidence.EvidenceType.IMAGE,
                        Evidence.EvidenceType.POSTER,
                        Evidence.EvidenceType.PROJECT_DOCUMENTATION,
                    ],
                ),
                distinct=True,
            )
        )
        user = self.request.user
        if user.is_authenticated and (user.institution_id or is_platform_operator(user)):
            qs = scope_queryset(qs, user)
            if user.role == User.Role.STUDENT:
                return qs.filter(Q(status=Club.Status.RECOGNIZED) | Q(requested_by=user))
            return qs
        slug = self.request.query_params.get("institution", "alche")
        return qs.filter(institution__slug=slug, status=Club.Status.RECOGNIZED)

    def get_permissions(self):
        if self.action == "create":
            return [permissions.IsAuthenticated(), IsCommitteeHead()]
        if self.action in ("update", "partial_update", "destroy"):
            return [permissions.IsAuthenticated(), IsOwnClubLeader()]
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        if self.action == "portfolio":
            return [permissions.IsAuthenticated()]
        if self.action == "publish_watch":
            return [permissions.IsAuthenticated()]
        if self.action == "request_charter":
            return [permissions.IsAuthenticated()]
        if self.action in ("recognize", "reject_charter"):
            return [permissions.IsAuthenticated(), IsCommitteeOrDean()]
        if self.action in ("pause", "restore"):
            return [permissions.IsAuthenticated(), IsStudentLife()]
        return [permissions.IsAuthenticated()]

    @action(detail=True, methods=["get"])
    def portfolio(self, request, pk=None):
        club = self.get_object()
        if club.status != Club.Status.RECOGNIZED:
            is_manager = request.user.is_authenticated and request.user.role in (
                User.Role.COMMITTEE_HEAD,
                User.Role.STAFF,
                User.Role.STUDENT_LIFE,
                User.Role.SYSTEM_ADMIN,
            )
            is_owner = request.user.is_authenticated and (
                club.requested_by_id == request.user.id or request.user.is_leader_of(club)
            )
            if not (is_manager or is_owner):
                return Response(
                    {"error": "This club is not published on the campus directory yet."},
                    status=404,
                )

        gallery = club_gallery_items(club, request)
        by_activity = {}
        by_project = {}
        for item in gallery:
            if item["activity_id"]:
                by_activity.setdefault(item["activity_id"], []).append(item)
            if item["impact_project_id"]:
                by_project.setdefault(item["impact_project_id"], []).append(item)

        activities = []
        for activity in club.activities.filter(status="verified").order_by("-date_time"):
            aid = str(activity.id)
            activities.append(
                {
                    "id": aid,
                    "title": activity.title,
                    "activity_type": activity.activity_type,
                    "objective": activity.objective,
                    "description": activity.description,
                    "date_time": activity.date_time,
                    "location": activity.location,
                    "report_text": activity.report_text,
                    "actual_participation": activity.actual_participation,
                    "media": by_activity.get(aid, []),
                }
            )

        projects = []
        for project in club.impact_projects.order_by("-start_date"):
            pid = str(project.id)
            projects.append(
                {
                    "id": pid,
                    "title": project.title,
                    "problem_statement": project.problem_statement,
                    "objective": project.objective,
                    "activities_summary": project.activities_summary,
                    "beneficiaries_description": project.beneficiaries_description,
                    "estimated_beneficiaries_count": project.estimated_beneficiaries_count,
                    "outcomes": project.outcomes,
                    "next_steps": project.next_steps,
                    "start_date": project.start_date,
                    "media": by_project.get(pid, []),
                }
            )

        data = ClubPublicSerializer(club).data
        data["verified_activities"] = activities
        data["impact_projects"] = projects
        data["published_media"] = gallery
        data["published_watch_count"] = len(gallery)
        return Response(data)

    @action(detail=True, methods=["post"], url_path="publish-watch")
    def publish_watch(self, request, pk=None):
        """A club leader publishes a video, photo, or project film on the campus club page."""
        club = self.get_object()
        if not request.user.is_authenticated or not request.user.is_leader_of(club):
            return Response(
                {"error": "Only this club's leaders can publish work for the campus to watch."},
                status=status.HTTP_403_FORBIDDEN,
            )
        caption = (request.data.get("caption") or "").strip()
        if not caption:
            return Response({"error": "A caption is required."}, status=status.HTTP_400_BAD_REQUEST)
        kind = (request.data.get("evidence_type") or Evidence.EvidenceType.VIDEO).strip()
        allowed = {choice[0] for choice in Evidence.EvidenceType.choices}
        if kind not in allowed:
            kind = Evidence.EvidenceType.VIDEO
        link = (request.data.get("external_link") or "").strip()
        upload = request.FILES.get("file")
        if not link and not upload:
            return Response(
                {"error": "Add a watch link or attach a file."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if looks_like_video(link):
            kind = Evidence.EvidenceType.VIDEO
        elif kind not in GALLERY_TYPES:
            kind = Evidence.EvidenceType.IMAGE if upload else Evidence.EvidenceType.VIDEO
        activity = None
        activity_id = request.data.get("activity") or request.data.get("activity_id")
        if activity_id:
            activity = club.activities.filter(pk=activity_id).first()
        item = Evidence.objects.create(
            club=club,
            activity=activity,
            evidence_type=kind,
            caption=caption[:300],
            external_link=link[:200] if link else "",
            file=upload,
            status=Evidence.Status.VERIFIED,
            uploaded_by=request.user,
        )
        return Response(serialize_gallery_item(item, request), status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="request-charter")
    def request_charter(self, request):
        """A student (or any member) requests official recognition of a new club."""
        user = request.user
        if not user.institution_id:
            return Response(
                {"error": "You must belong to a licensed institution to register a club."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        name = (request.data.get("name") or "").strip()
        category = (request.data.get("category") or "General").strip()
        if not name:
            return Response({"error": "Club name is required."}, status=status.HTTP_400_BAD_REQUEST)
        slug = slugify(name)[:220]
        if Club.objects.filter(institution=user.institution, slug=slug).exists():
            return Response(
                {"error": "A club with this name already exists at your institution."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        club = Club.objects.create(
            institution=user.institution,
            name=name,
            slug=slug,
            category=category,
            description=request.data.get("description") or "",
            mission=request.data.get("mission") or "",
            vision=request.data.get("vision") or "",
            objectives=request.data.get("objectives") or "",
            charter_statement=request.data.get("charter_statement") or "",
            status=Club.Status.PENDING,
            requested_by=user,
            public_contact_email=user.email,
        )
        ClubMembership.objects.create(
            club=club,
            user=user,
            role=ClubMembership.MembershipRole.LEADER,
            status=ClubMembership.Status.APPROVED,
            is_active=True,
            joined_at=timezone.now().date(),
        )
        return Response(ClubManageSerializer(club).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def recognize(self, request, pk=None):
        club = self.get_object()
        club.status = Club.Status.RECOGNIZED
        club.save(update_fields=["status", "updated_at"])
        if club.requested_by_id and club.requested_by.role == User.Role.STUDENT:
            club.requested_by.role = User.Role.CLUB_LEADER
            club.requested_by.save(update_fields=["role", "updated_at"])
        return Response(ClubManageSerializer(club).data)

    @action(detail=True, methods=["post"], url_path="reject-charter")
    def reject_charter(self, request, pk=None):
        club = self.get_object()
        club.status = Club.Status.DORMANT
        club.save(update_fields=["status", "updated_at"])
        return Response(ClubManageSerializer(club).data)

    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        club = self.get_object()
        reason = (request.data.get("reason") or "").strip()
        if len(reason) < 8:
            return Response({"error": "Write a short reason before pausing a club."}, status=400)
        club.status = Club.Status.SUSPENDED
        club.save(update_fields=["status", "updated_at"])
        AuditLog.objects.create(
            actor=request.user,
            action="club.paused",
            target_model="clubs.Club",
            target_id=str(club.id),
            reason=reason,
            metadata={"name": club.name},
        )
        return Response(ClubManageSerializer(club).data)

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        club = self.get_object()
        reason = (request.data.get("reason") or "").strip()
        if len(reason) < 8:
            return Response({"error": "Write a short reason before restoring a club."}, status=400)
        club.status = Club.Status.RECOGNIZED
        club.save(update_fields=["status", "updated_at"])
        AuditLog.objects.create(
            actor=request.user,
            action="club.restored",
            target_model="clubs.Club",
            target_id=str(club.id),
            reason=reason,
            metadata={"name": club.name},
        )
        return Response(ClubManageSerializer(club).data)


class ClubMembershipViewSet(viewsets.ModelViewSet):
    queryset = ClubMembership.objects.all()
    serializer_class = ClubMembershipSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = ClubMembership.objects.select_related("club", "user")
        if not is_platform_operator(user):
            if user.institution_id:
                qs = qs.filter(club__institution_id=user.institution_id)
            else:
                qs = qs.none()
        if user.role in (
            User.Role.COMMITTEE_HEAD,
            User.Role.STAFF,
            User.Role.STUDENT_LIFE,
            User.Role.SYSTEM_ADMIN,
        ):
            return qs
        return qs.filter(
            Q(user=user)
            | Q(
                club__memberships__user=user,
                club__memberships__role=ClubMembership.MembershipRole.LEADER,
            )
        ).distinct()

    def create(self, request, *args, **kwargs):
        if request.user.role in (User.Role.STUDENT, User.Role.CLUB_LEADER):
            institution = request.user.institution
            if not institution or not institution.membership_census_open:
                return Response(
                    {
                        "error": (
                            "The Clubs & Societies Committee Head has closed membership requests. "
                            "You can send the clubs you belong to when they open the window again."
                        )
                    },
                    status=403,
                )
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(
            user=self.request.user,
            status=ClubMembership.Status.REQUESTED,
            role=ClubMembership.MembershipRole.MEMBER,
            source=ClubMembership.Source.JOIN,
        )

    def _can_moderate(self, membership, user) -> bool:
        if user.role in (
            User.Role.COMMITTEE_HEAD,
            User.Role.STAFF,
            User.Role.SYSTEM_ADMIN,
        ):
            return True
        return membership.club.leaders.filter(id=user.id).exists()

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        membership = self.get_object()
        if not self._can_moderate(membership, request.user):
            return Response({"error": "Only club leadership or committee can approve members."}, status=403)
        membership.status = ClubMembership.Status.APPROVED
        membership.is_active = True
        membership.joined_at = timezone.now().date()
        membership.save(update_fields=["status", "is_active", "joined_at", "updated_at"])
        return Response(ClubMembershipSerializer(membership).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        membership = self.get_object()
        if not self._can_moderate(membership, request.user):
            return Response({"error": "Only club leadership or committee can reject members."}, status=403)
        membership.status = ClubMembership.Status.REJECTED
        membership.is_active = False
        membership.save(update_fields=["status", "is_active", "updated_at"])
        return Response(ClubMembershipSerializer(membership).data)


class LeadershipHandoverViewSet(viewsets.ModelViewSet):
    serializer_class = LeadershipHandoverSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        qs = LeadershipHandover.objects.select_related("club", "outgoing", "incoming", "confirmed_by")
        if is_platform_operator(user):
            return qs
        if not user.institution_id:
            return qs.none()
        qs = qs.filter(club__institution_id=user.institution_id)
        if user.role in (User.Role.COMMITTEE_HEAD, User.Role.STAFF, User.Role.STUDENT_LIFE, User.Role.SYSTEM_ADMIN):
            return qs
        return qs.filter(Q(outgoing=user) | Q(incoming=user) | Q(incoming_email__iexact=user.email))

    @action(detail=False, methods=["get"], url_path="current-committee")
    def current_committee(self, request):
        club_id = request.query_params.get("club")
        club = Club.objects.filter(id=club_id).first()
        if not club:
            return Response({"error": "Club not found."}, status=404)
        if not (
            request.user.is_leader_of(club)
            or request.user.role in (User.Role.COMMITTEE_HEAD, User.Role.STAFF, User.Role.SYSTEM_ADMIN)
        ):
            return Response({"error": "Only this club's leaders or the Committee Head can see the office slate."}, status=403)
        return Response({"club": str(club.id), "outgoing_committee": current_office_seats(club)})

    def create(self, request):
        club_id = request.data.get("club")
        club = Club.objects.filter(id=club_id).first()
        if not club:
            return Response({"error": "Club not found."}, status=404)
        if not request.user.is_leader_of(club):
            return Response({"error": "Only this club's current leader can submit a committee handover."}, status=403)
        if LeadershipHandover.objects.filter(
            club=club,
            status__in=(LeadershipHandover.Status.NOMINATED, LeadershipHandover.Status.ACCEPTED),
        ).exists():
            return Response(
                {"error": "This club already has a handover waiting for the Committee Head."},
                status=400,
            )
        try:
            outgoing = parse_committee(
                request.data.get("outgoing_committee") or current_office_seats(club),
                label="outgoing",
            )
            incoming = parse_committee(request.data.get("incoming_committee") or [], label="incoming")
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)
        leaders = incoming_leaders(incoming)
        if not leaders:
            return Response(
                {"error": "Name at least one incoming club leader with position President or Club leader."},
                status=400,
            )
        if club.institution_id:
            for seat in outgoing + incoming:
                if not club.institution.accepts_email(seat["email"]):
                    return Response(
                        {"error": f"{seat['email']} is not on this campus's licensed student or staff domains."},
                        status=400,
                    )
        incoming_user = User.objects.filter(
            email__iexact=leaders[0]["email"],
            institution=club.institution,
        ).first()
        year = club.institution.current_academic_year() if club.institution_id else ""
        handover = LeadershipHandover.objects.create(
            club=club,
            outgoing=request.user,
            incoming=incoming_user,
            incoming_email=leaders[0]["email"],
            outgoing_committee=outgoing,
            incoming_committee=incoming,
            academic_year=year,
            notes=(request.data.get("notes") or "").strip(),
            achievements_summary=(request.data.get("achievements_summary") or "").strip(),
        )
        club.handover_notes_private = handover.notes
        club.save(update_fields=["handover_notes_private", "updated_at"])
        return Response(LeadershipHandoverSerializer(handover).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        return Response(
            {"error": "The outgoing club leader submits this form. Only the Committee Head confirms it."},
            status=400,
        )

    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None):
        handover = self.get_object()
        if request.user.role != User.Role.COMMITTEE_HEAD and handover.outgoing_id != request.user.id:
            return Response({"error": "Only the Committee Head or the submitting leader can decline this handover."}, status=403)
        handover.status = LeadershipHandover.Status.DECLINED
        handover.save(update_fields=["status", "updated_at"])
        return Response(LeadershipHandoverSerializer(handover).data)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        handover = self.get_object()
        if request.user.role != User.Role.COMMITTEE_HEAD:
            return Response({"error": "The Committee Head confirms committee handover."}, status=403)
        if handover.status not in (LeadershipHandover.Status.NOMINATED, LeadershipHandover.Status.ACCEPTED):
            return Response({"error": "This handover is not waiting for confirmation."}, status=400)
        try:
            apply_committee_handover(handover)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)
        handover.status = LeadershipHandover.Status.CONFIRMED
        handover.confirmed_by = request.user
        handover.confirmed_at = timezone.now()
        handover.save()
        return Response(LeadershipHandoverSerializer(handover).data)


def _committee_or_staff(user):
    return user.role in (
        User.Role.COMMITTEE_HEAD,
        User.Role.STAFF,
        User.Role.STUDENT_LIFE,
        User.Role.SYSTEM_ADMIN,
    )


class MembershipCensusWindowView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not request.user.institution_id:
            return Response({"error": "No campus is attached to this account."}, status=400)
        return Response(membership_window_payload(request.user.institution, request.user))

    def patch(self, request):
        user = request.user
        if user.role not in (User.Role.COMMITTEE_HEAD, User.Role.STUDENT_LIFE) or not user.institution_id:
            return Response(
                {"error": "Only this campus's Committee Head or Student Life office can open or close membership requests."},
                status=403,
            )
        institution = user.institution
        if "open" in request.data:
            raw = request.data.get("open")
            if isinstance(raw, bool):
                opening = raw
            else:
                opening = str(raw).strip().lower() in ("1", "true", "yes", "on")
            institution.membership_census_open = opening
            if opening:
                institution.membership_census_opened_at = timezone.now()
                institution.membership_census_opened_by = user
            institution.save(
                update_fields=[
                    "membership_census_open",
                    "membership_census_opened_at",
                    "membership_census_opened_by",
                    "updated_at",
                ]
            )
        if "member_grant_amount" in request.data:
            institution.member_grant_amount = money(request.data.get("member_grant_amount"))
            institution.save(update_fields=["member_grant_amount", "updated_at"])
        if "member_grant_currency" in request.data:
            code = str(request.data.get("member_grant_currency") or "USD").strip().upper()[:8]
            institution.member_grant_currency = code or "USD"
            institution.save(update_fields=["member_grant_currency", "updated_at"])
        return Response(membership_window_payload(institution, user))


class MembershipCensusDeclareView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.role not in (User.Role.STUDENT, User.Role.CLUB_LEADER):
            return Response({"error": "Students and club leaders declare the clubs they belong to."}, status=403)
        institution = user.institution
        if not institution:
            return Response({"error": "No campus is attached to this account."}, status=400)
        if not institution.membership_census_open:
            return Response(
                {
                    "error": (
                        "Membership requests are closed. The Committee Head turns this window on when "
                        "the campus is collecting who belongs to which club."
                    )
                },
                status=403,
            )
        raw_ids = request.data.get("club_ids") or []
        if not isinstance(raw_ids, list) or not raw_ids:
            return Response({"error": "Select at least one recognised club you belong to."}, status=400)
        created = []
        for cid in raw_ids:
            club = Club.objects.filter(
                id=cid,
                institution=institution,
                status=Club.Status.RECOGNIZED,
                is_archived=False,
            ).first()
            if not club:
                continue
            membership, made = ClubMembership.objects.get_or_create(
                club=club,
                user=user,
                defaults={
                    "role": ClubMembership.MembershipRole.MEMBER,
                    "status": ClubMembership.Status.REQUESTED,
                    "source": ClubMembership.Source.CENSUS,
                    "is_active": True,
                },
            )
            if membership.status == ClubMembership.Status.APPROVED:
                continue
            if membership.status in (ClubMembership.Status.REJECTED, ClubMembership.Status.LEFT) or made:
                membership.status = ClubMembership.Status.REQUESTED
                membership.source = ClubMembership.Source.CENSUS
                membership.is_active = True
                membership.save(update_fields=["status", "source", "is_active", "updated_at"])
            created.append(ClubMembershipSerializer(membership).data)
        return Response({"requested": created, "count": len(created)}, status=201)


class MembershipCensusConfirmView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        ids = request.data.get("ids") or []
        if not isinstance(ids, list) or not ids:
            return Response({"error": "Send membership ids to confirm."}, status=400)
        updated = []
        for mid in ids:
            membership = ClubMembership.objects.filter(id=mid).select_related("club").first()
            if not membership:
                continue
            can = user.role in (User.Role.COMMITTEE_HEAD, User.Role.STAFF, User.Role.SYSTEM_ADMIN)
            if not can:
                can = membership.club.leaders.filter(id=user.id).exists()
            if not can:
                continue
            if user.institution_id and membership.club.institution_id != user.institution_id:
                continue
            membership.status = ClubMembership.Status.APPROVED
            membership.is_active = True
            membership.joined_at = membership.joined_at or timezone.now().date()
            membership.save(update_fields=["status", "is_active", "joined_at", "updated_at"])
            updated.append(str(membership.id))
        return Response({"confirmed": updated, "count": len(updated)})


class MembershipLedgerView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        if not user.institution_id:
            return Response({"error": "No campus is attached to this account."}, status=400)
        if not _committee_or_staff(user):
            return Response({"error": "The Committee Head membership database is for campus governance."}, status=403)
        return Response(build_membership_ledger(user.institution))


class MembershipLedgerMineView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        if not user.institution_id:
            return Response({"error": "No campus is attached to this account."}, status=400)
        return Response(build_membership_ledger(user.institution, mine_user=user))


class ClubConceptNoteViewSet(viewsets.ModelViewSet):
    serializer_class = ClubConceptNoteSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        qs = ClubConceptNote.objects.select_related("club", "submitted_by")
        if is_platform_operator(user):
            return qs
        if not user.institution_id:
            return qs.none()
        qs = qs.filter(club__institution_id=user.institution_id)
        if _committee_or_staff(user):
            return qs
        return qs.filter(
            Q(submitted_by=user)
            | Q(
                club__memberships__user=user,
                club__memberships__role=ClubMembership.MembershipRole.LEADER,
                club__memberships__status=ClubMembership.Status.APPROVED,
            )
        ).distinct()

    def create(self, request):
        user = request.user
        club = Club.objects.filter(id=request.data.get("club"), institution=user.institution).first()
        if not club:
            return Response({"error": "Club not found on this campus."}, status=404)
        if not (user.is_leader_of(club) or _committee_or_staff(user)):
            return Response({"error": "Only this club's leaders can submit a concept note."}, status=403)
        try:
            amount = money(request.data.get("amount_requested"))
        except Exception:
            return Response({"error": "Enter a requested amount."}, status=400)
        if amount <= 0:
            return Response({"error": "The requested amount must be greater than zero."}, status=400)
        title = (request.data.get("title") or "").strip()
        purpose = (request.data.get("purpose") or "").strip()
        if len(title) < 3 or len(purpose) < 10:
            return Response({"error": "Add a title and explain what the money will be used for."}, status=400)
        note = ClubConceptNote.objects.create(
            club=club,
            submitted_by=user,
            academic_year=user.institution.current_academic_year(),
            title=title,
            purpose=purpose,
            amount_requested=amount,
        )
        return Response(ClubConceptNoteSerializer(note).data, status=201)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        note = self.get_object()
        if request.user.role != User.Role.COMMITTEE_HEAD:
            return Response({"error": "The Committee Head approves concept notes."}, status=403)
        note.status = ClubConceptNote.Status.APPROVED
        note.committee_comment = (request.data.get("committee_comment") or "").strip()
        note.decided_by = request.user
        note.decided_at = timezone.now()
        note.save()
        return Response(ClubConceptNoteSerializer(note).data)

    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None):
        note = self.get_object()
        if request.user.role != User.Role.COMMITTEE_HEAD:
            return Response({"error": "The Committee Head declines concept notes."}, status=403)
        note.status = ClubConceptNote.Status.DECLINED
        note.committee_comment = (request.data.get("committee_comment") or "").strip()
        note.decided_by = request.user
        note.decided_at = timezone.now()
        note.save()
        return Response(ClubConceptNoteSerializer(note).data)


class ClubBudgetSpendViewSet(viewsets.ModelViewSet):
    serializer_class = ClubBudgetSpendSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        qs = ClubBudgetSpend.objects.select_related("club")
        if not user.institution_id:
            return qs.none()
        qs = qs.filter(club__institution_id=user.institution_id)
        if _committee_or_staff(user):
            return qs
        return qs.filter(
            club__memberships__user=user,
            club__memberships__role=ClubMembership.MembershipRole.LEADER,
            club__memberships__status=ClubMembership.Status.APPROVED,
        ).distinct()

    def create(self, request):
        user = request.user
        if user.role != User.Role.COMMITTEE_HEAD:
            return Response({"error": "The Committee Head records what of a club's grant has been used."}, status=403)
        club = Club.objects.filter(id=request.data.get("club"), institution=user.institution).first()
        if not club:
            return Response({"error": "Club not found on this campus."}, status=404)
        comment = (request.data.get("comment") or "").strip()
        if len(comment) < 8:
            return Response({"error": "Say what this amount was used to do."}, status=400)
        try:
            amount = money(request.data.get("amount"))
        except Exception:
            return Response({"error": "Enter the amount used."}, status=400)
        if amount <= 0:
            return Response({"error": "Amount must be greater than zero."}, status=400)
        note = None
        if request.data.get("concept_note"):
            note = ClubConceptNote.objects.filter(id=request.data.get("concept_note"), club=club).first()
        spend = ClubBudgetSpend.objects.create(
            club=club,
            concept_note=note,
            recorded_by=user,
            academic_year=user.institution.current_academic_year(),
            amount=amount,
            comment=comment,
            spent_on=timezone.now().date(),
        )
        return Response(ClubBudgetSpendSerializer(spend).data, status=201)


class StudentLifeDeskView(APIView):
    """The three piles Student Life opens in the morning."""

    permission_classes = [permissions.IsAuthenticated, IsStudentLife]

    def get(self, request):
        user = request.user
        if not user.institution_id:
            return Response({"error": "No campus is attached to this account."}, status=400)
        from .student_life import student_life_desk

        return Response(student_life_desk(user.institution))


