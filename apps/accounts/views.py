from django.conf import settings
from django.utils import timezone
from rest_framework import generics, permissions, status, throttling
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.permissions import IsPlatformOperator, IsStaffOrAdmin, IsSystemAdmin
from apps.core.tenancy import is_platform_operator

from .models import CampusCommitteeHandover, Institution, LicenceInquiry, SupportTicket, User
from .campus_handover import (
    apply_campus_committee_handover,
    can_confirm_campus_handover,
    current_campus_committee,
    incoming_heads,
)
from .records import campus_onboarding, student_transcript
from .sso import issue_session, sso_status, user_from_verified_email, verify_google_id_token
from .serializers import (
    CampusCommitteeHandoverSerializer,
    CampusInstitutionSerializer,
    CampusUserSerializer,
    CustomTokenObtainPairSerializer,
    InstitutionPublicSerializer,
    LicenceInquirySerializer,
    LicenceInquiryStatusSerializer,
    RegisterSerializer,
    SupportTicketSerializer,
    SupportTicketStatusSerializer,
    UserProfileSerializer,
)

ALCHE_DEMO = [
    {
        "role": "student",
        "label": "Student",
        "name": "Alex Mercer",
        "email": "alex.student@alustudent.com",
        "password": "Pass1234!",
        "description": "Browse ALCHE clubs, request to join, check in with QR, ask the Copilot what you can do.",
        "badge": "ALCHE Student",
    },
    {
        "role": "club_leader",
        "label": "Club Leader",
        "name": "Sarah Chen",
        "email": "sarah.leader@alustudent.com",
        "password": "Pass1234!",
        "club_name": "Robotics club",
        "description": "Submit monthly reports, schedule events, upload evidence, approve join requests.",
        "badge": "Robotics Lead",
    },
    {
        "role": "committee_head",
        "label": "Committee Head",
        "name": "Dr. Elena Rostova",
        "email": "dr.elena.head@alustudent.com",
        "password": "Pass1234!",
        "description": "Student email (@alustudent.com). Only this role sees CCEA marks and rankings, then publishes them to the Hall of Excellence at the ceremony.",
        "badge": "Governance Head",
    },
    {
        "role": "staff",
        "label": "Staff / Lecturer",
        "name": "Arthur Harrison",
        "email": "arthur.harrison@alueducation.com",
        "password": "Pass1234!",
        "description": "Any ALCHE staff email (@alueducation.com). Campus analytics, notices, published club films, and the Hall of Excellence after publication. No unpublished CCEA marks.",
        "badge": "ALCHE Staff",
    },
    {
        "role": "student_life",
        "label": "Student Life",
        "name": "Amara Diallo",
        "email": "amara.diallo@alueducation.com",
        "password": "Pass1234!",
        "description": "Staff email. Morning desk for charters, quiet clubs, the membership window, and campus notices. Award scores stay with the Committee Head.",
        "badge": "Student Life",
    },
    {
        "role": "system_admin",
        "label": "System Administrator",
        "name": "Admin Root",
        "email": "admin@alueducation.com",
        "password": "Pass1234!",
        "description": "Campus IT for this licensed institution: people, sign-in domains, audit, and help tickets. Same idea as Google Workspace Super Admin or Canvas Account Admin — not CCEA marking, and not licensing other universities.",
        "badge": "Platform Admin",
    },
]


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": user.public_identity(),
            },
            status=status.HTTP_201_CREATED,
        )


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def retrieve(self, request, *args, **kwargs):
        return Response(request.user.public_identity())

    def update(self, request, *args, **kwargs):
        super().update(request, *args, **kwargs)
        return Response(request.user.public_identity())

    def partial_update(self, request, *args, **kwargs):
        super().partial_update(request, *args, **kwargs)
        return Response(request.user.public_identity())


class InstitutionListView(APIView):
    """Public directory of licensed institutions (for signup guidance)."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        qs = Institution.objects.filter(is_active=True)
        return Response(InstitutionPublicSerializer(qs, many=True).data)


class DemoPersonasView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response(ALCHE_DEMO)


class SwitchRoleView(APIView):
    """Demonstration-only. Real role changes happen through admin IAM."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not settings.DEBUG:
            return Response(
                {"error": "Role switching is only available in demonstration mode."},
                status=status.HTTP_403_FORBIDDEN,
            )
        target_role = request.data.get("role")
        if target_role not in dict(User.Role.choices):
            return Response({"error": f"Invalid role '{target_role}'"}, status=status.HTTP_400_BAD_REQUEST)

        email_map = {item["role"]: item["email"] for item in ALCHE_DEMO}
        target_email = email_map.get(target_role)
        target = User.objects.filter(email__iexact=target_email).first() if target_email else None
        if not target and target_email:
            persona = next((item for item in ALCHE_DEMO if item["role"] == target_role), None)
            institution = Institution.objects.filter(slug="alche").first() or Institution.objects.filter(is_active=True).first()
            if persona and institution:
                first, _, last = persona["name"].partition(" ")
                username = target_email.split("@")[0].replace(".", "_")
                if User.objects.filter(username=username).exists():
                    username = f"{username}_life"
                target = User(
                    username=username,
                    email=target_email,
                    institution=institution,
                    role=target_role,
                    first_name=first,
                    last_name=last,
                    is_staff=target_role in (User.Role.STAFF, User.Role.STUDENT_LIFE, User.Role.SYSTEM_ADMIN),
                )
                target.set_password(persona["password"])
                target.save()
        if not target:
            user = request.user
            user.role = target_role
            user.save(update_fields=["role", "updated_at"])
            target = user

        refresh = RefreshToken.for_user(target)
        previous_login = target.last_login
        target.last_login = timezone.now()
        target.save(update_fields=["last_login"])
        identity = target.public_identity()
        identity["catch_up_since"] = previous_login.isoformat() if previous_login else None
        return Response({
            "detail": f"Now viewing as {target.get_role_display()}",
            "access": str(refresh.access_token),
            "user": identity,
            "catch_up_since": identity["catch_up_since"],
        })


class LicenceInquiryCreateView(APIView):
    """Public. An unlicensed campus reaches ClubConnect from the landing page."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [throttling.ScopedRateThrottle]
    throttle_scope = "licence-inquiry"

    def post(self, request):
        serializer = LicenceInquirySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["contact_email"]
        name = serializer.validated_data["institution_name"]
        existing = (
            LicenceInquiry.objects.filter(contact_email__iexact=email, institution_name__iexact=name)
            .exclude(status=LicenceInquiry.Status.DECLINED)
            .first()
        )
        if existing:
            return Response(
                {
                    "id": str(existing.id),
                    "detail": "We already have this request. ClubConnect will reply to the contact email.",
                    "duplicate": True,
                },
                status=status.HTTP_200_OK,
            )
        inquiry = serializer.save()
        return Response(
            {
                "id": str(inquiry.id),
                "detail": "Request received. ClubConnect will write to the contact email with next steps.",
            },
            status=status.HTTP_201_CREATED,
        )


class LicenceInquiryListView(generics.ListAPIView):
    serializer_class = LicenceInquirySerializer
    permission_classes = [IsPlatformOperator]
    queryset = LicenceInquiry.objects.all()
    pagination_class = None


class LicenceInquiryStatusView(APIView):
    permission_classes = [IsPlatformOperator]

    def patch(self, request, inquiry_id):
        inquiry = LicenceInquiry.objects.filter(id=inquiry_id).first()
        if not inquiry:
            return Response({"error": "Request not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = LicenceInquiryStatusSerializer(inquiry, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(LicenceInquirySerializer(inquiry).data        )


class SupportTicketCreateView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [throttling.ScopedRateThrottle]
    throttle_scope = "help-ticket"

    def post(self, request):
        serializer = SupportTicketSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user if request.user.is_authenticated else None
        name = serializer.validated_data.get("name")
        email = serializer.validated_data.get("email")
        if user:
            name = user.get_full_name() or user.username
            email = user.email
        if not name or not email:
            return Response(
                {"detail": "Name and email are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ticket = serializer.save(
            user=user,
            institution=getattr(user, "institution", None) if user else None,
            name=name,
            email=email,
        )
        return Response(SupportTicketSerializer(ticket).data, status=status.HTTP_201_CREATED)

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({"detail": "Sign in to see your tickets."}, status=status.HTTP_401_UNAUTHORIZED)
        qs = SupportTicket.objects.filter(user=request.user)
        return Response(SupportTicketSerializer(qs, many=True).data)


class SupportTicketStaffView(generics.ListAPIView):
    serializer_class = SupportTicketSerializer
    permission_classes = [IsStaffOrAdmin]
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        if is_platform_operator(user):
            return SupportTicket.objects.all()
        if user.institution_id:
            return SupportTicket.objects.filter(institution_id=user.institution_id)
        return SupportTicket.objects.none()


class SupportTicketStatusView(APIView):
    permission_classes = [IsStaffOrAdmin]

    def patch(self, request, ticket_id):
        ticket = SupportTicket.objects.filter(id=ticket_id).first()
        if not ticket:
            return Response({"error": "Ticket not found."}, status=status.HTTP_404_NOT_FOUND)
        if is_platform_operator(request.user):
            pass
        elif request.user.institution_id and ticket.institution_id == request.user.institution_id:
            pass
        else:
            return Response({"error": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        serializer = SupportTicketStatusSerializer(ticket, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(SupportTicketSerializer(ticket).data)


def _admin_institution(user):
    if is_platform_operator(user):
        return None
    return user.institution


class CampusUserListCreateView(APIView):
    """Google Workspace-style directory for one licensed campus."""

    permission_classes = [permissions.IsAuthenticated, IsSystemAdmin]

    def get(self, request):
        if is_platform_operator(request.user):
            qs = User.objects.all().order_by("email")
        elif request.user.institution_id:
            qs = User.objects.filter(institution_id=request.user.institution_id).order_by("email")
        else:
            return Response({"error": "This administrator is not attached to a campus."}, status=400)
        return Response(CampusUserSerializer(qs, many=True).data)

    def post(self, request):
        institution = _admin_institution(request.user)
        if is_platform_operator(request.user):
            return Response(
                {"error": "Platform operators licence campuses; campus administrators add people."},
                status=400,
            )
        if not institution:
            return Response({"error": "This administrator is not attached to a campus."}, status=400)
        email = str(request.data.get("email") or "").strip().lower()
        if not institution.accepts_email(email):
            return Response(
                {"error": "That email is not on this campus's licensed student or staff domains."},
                status=400,
            )
        if User.objects.filter(email__iexact=email).exists():
            return Response({"error": "An account with this email already exists."}, status=400)
        role = request.data.get("role") or institution.role_for_new_account(email)
        if role not in dict(User.Role.choices):
            return Response({"error": "Invalid role."}, status=400)
        name = str(request.data.get("name") or "").strip()
        first, _, last = name.partition(" ")
        username = email.split("@")[0].replace(".", "_")[:140]
        base = username
        n = 1
        while User.objects.filter(username=username).exists():
            n += 1
            username = f"{base}{n}"
        user = User(
            username=username,
            email=email,
            first_name=first or email.split("@")[0],
            last_name=last.strip(),
            role=role,
            institution=institution,
            student_id=str(request.data.get("student_id") or "").strip(),
        )
        from django.utils.crypto import get_random_string

        temporary_password = get_random_string(12)
        user.set_password(temporary_password)
        user.save()
        payload = CampusUserSerializer(user).data
        payload["temporary_password"] = temporary_password
        return Response(payload, status=201)


class CampusUserDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsSystemAdmin]

    def _get_user(self, request, user_id):
        qs = User.objects.all()
        if not is_platform_operator(request.user):
            if not request.user.institution_id:
                return None
            qs = qs.filter(institution_id=request.user.institution_id)
        return qs.filter(id=user_id).first()

    def patch(self, request, user_id):
        target = self._get_user(request, user_id)
        if not target:
            return Response({"error": "User not found on this campus."}, status=404)
        role = request.data.get("role")
        if role is not None:
            if role not in dict(User.Role.choices):
                return Response({"error": "Invalid role."}, status=400)
            target.role = role
        if "is_active" in request.data or "active" in request.data:
            flag = request.data.get("is_active", request.data.get("active"))
            target.is_active = bool(flag)
        target.save()
        return Response(CampusUserSerializer(target).data)


def _admin_institution(user):
    if is_platform_operator(user):
        return None
    return user.institution


class CampusUserListCreateView(APIView):
    """Google Workspace-style directory for one licensed campus."""

    permission_classes = [permissions.IsAuthenticated, IsSystemAdmin]

    def get(self, request):
        if is_platform_operator(request.user):
            qs = User.objects.all().order_by("email")
        elif request.user.institution_id:
            qs = User.objects.filter(institution_id=request.user.institution_id).order_by("email")
        else:
            return Response({"error": "This administrator is not attached to a campus."}, status=400)
        return Response(CampusUserSerializer(qs, many=True).data)

    def post(self, request):
        institution = _admin_institution(request.user)
        if is_platform_operator(request.user):
            return Response(
                {"error": "Platform operators licence campuses; campus administrators add people."},
                status=400,
            )
        if not institution:
            return Response({"error": "This administrator is not attached to a campus."}, status=400)
        email = str(request.data.get("email") or "").strip().lower()
        if not institution.accepts_email(email):
            return Response(
                {"error": "That email is not on this campus's licensed student or staff domains."},
                status=400,
            )
        if User.objects.filter(email__iexact=email).exists():
            return Response({"error": "An account with this email already exists."}, status=400)
        role = request.data.get("role") or institution.role_for_new_account(email)
        if role not in dict(User.Role.choices):
            return Response({"error": "Invalid role."}, status=400)
        name = str(request.data.get("name") or "").strip()
        first, _, last = name.partition(" ")
        username = email.split("@")[0].replace(".", "_")[:140]
        base = username
        n = 1
        while User.objects.filter(username=username).exists():
            n += 1
            username = f"{base}{n}"
        user = User(
            username=username,
            email=email,
            first_name=first or email.split("@")[0],
            last_name=last.strip(),
            role=role,
            institution=institution,
            student_id=str(request.data.get("student_id") or "").strip(),
        )
        from django.utils.crypto import get_random_string

        temporary_password = get_random_string(12)
        user.set_password(temporary_password)
        user.save()
        payload = CampusUserSerializer(user).data
        payload["temporary_password"] = temporary_password
        return Response(payload, status=201)


class CampusUserDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsSystemAdmin]

    def _get_user(self, request, user_id):
        qs = User.objects.all()
        if not is_platform_operator(request.user):
            if not request.user.institution_id:
                return None
            qs = qs.filter(institution_id=request.user.institution_id)
        return qs.filter(id=user_id).first()

    def patch(self, request, user_id):
        target = self._get_user(request, user_id)
        if not target:
            return Response({"error": "User not found on this campus."}, status=404)
        role = request.data.get("role")
        if role is not None:
            if role not in dict(User.Role.choices):
                return Response({"error": "Invalid role."}, status=400)
            target.role = role
        if "is_active" in request.data or "active" in request.data:
            flag = request.data.get("is_active", request.data.get("active"))
            target.is_active = bool(flag)
        target.save()
        return Response(CampusUserSerializer(target).data)


class CampusInstitutionView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsSystemAdmin]

    def get(self, request):
        if is_platform_operator(request.user):
            return Response({"error": "Select a campus. Platform operators are not bound to one institution."}, status=400)
        if not request.user.institution_id:
            return Response({"error": "This administrator is not attached to a campus."}, status=400)
        return Response(CampusInstitutionSerializer(request.user.institution).data)

    def patch(self, request):
        if is_platform_operator(request.user) or not request.user.institution_id:
            return Response({"error": "Campus settings belong to that campus's system administrator."}, status=403)
        serializer = CampusInstitutionSerializer(request.user.institution, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class MeTranscriptView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(student_transcript(request.user))


class CampusOnboardingView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsSystemAdmin]

    def get(self, request):
        payload = campus_onboarding(request.user)
        if payload.get("error"):
            return Response(payload, status=400)
        return Response(payload)


class SSOStatusView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = []

    def get(self, request):
        return Response(sso_status())


class GoogleSSOView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = []

    def post(self, request):
        client_id = (getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "") or "").strip()
        if not client_id:
            return Response(
                {
                    "error": (
                        "Google campus sign-in is off until this campus gives ClubConnect a Google Workspace client ID. "
                        "Use your licensed school email until then."
                    )
                },
                status=503,
            )
        id_token = (request.data.get("id_token") or "").strip()
        if not id_token:
            return Response({"error": "A Google ID token is required."}, status=400)
        email = verify_google_id_token(id_token, client_id)
        if not email:
            return Response({"error": "Google could not verify that sign-in."}, status=400)
        user, error = user_from_verified_email(
            email,
            first_name=(request.data.get("first_name") or "").strip(),
            last_name=(request.data.get("last_name") or "").strip(),
        )
        if error:
            return Response({"error": error}, status=403)
        return Response(issue_session(user))


class MicrosoftSSOView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = []

    def post(self, request):
        return Response(
            {
                "error": (
                    "Microsoft campus sign-in is listed only after a client ID is configured and tokens are verified. "
                    "Unverified Microsoft tokens cannot open ClubConnect. Use a licensed email for now."
                )
            },
            status=503,
        )


class CampusCommitteeHandoverListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        qs = CampusCommitteeHandover.objects.select_related("outgoing", "incoming", "institution")
        if is_platform_operator(user):
            rows = qs
        elif not user.institution_id:
            return Response([], status=200)
        elif user.role in (User.Role.COMMITTEE_HEAD, User.Role.SYSTEM_ADMIN, User.Role.STAFF):
            rows = qs.filter(institution_id=user.institution_id)
        else:
            rows = qs.filter(institution_id=user.institution_id, outgoing=user)
        return Response(CampusCommitteeHandoverSerializer(rows, many=True).data)

    def post(self, request):
        user = request.user
        if user.role != User.Role.COMMITTEE_HEAD or not user.institution_id:
            return Response(
                {"error": "Only this campus's Committee Head can submit a campus committee handover."},
                status=403,
            )
        institution = user.institution
        if CampusCommitteeHandover.objects.filter(
            institution=institution,
            status=CampusCommitteeHandover.Status.NOMINATED,
        ).exists():
            return Response(
                {"error": "A campus committee handover is already waiting for the campus administrator."},
                status=400,
            )
        from apps.clubs.handover import parse_committee

        try:
            outgoing = parse_committee(
                request.data.get("outgoing_committee") or current_campus_committee(institution),
                label="outgoing",
            )
            incoming = parse_committee(request.data.get("incoming_committee") or [], label="incoming")
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)
        heads = incoming_heads(incoming)
        if not heads:
            return Response({"error": "Name at least one incoming Committee Head."}, status=400)
        for seat in outgoing + incoming:
            if not institution.accepts_email(seat["email"]):
                return Response(
                    {"error": f"{seat['email']} is not on this campus's licensed student or staff domains."},
                    status=400,
                )
        incoming_user = User.objects.filter(
            email__iexact=heads[0]["email"],
            institution=institution,
        ).first()
        handover = CampusCommitteeHandover.objects.create(
            institution=institution,
            outgoing=user,
            incoming=incoming_user,
            incoming_email=heads[0]["email"],
            outgoing_committee=outgoing,
            incoming_committee=incoming,
            academic_year=institution.current_academic_year(),
            notes=(request.data.get("notes") or "").strip(),
            achievements_summary=(request.data.get("achievements_summary") or "").strip(),
        )
        return Response(CampusCommitteeHandoverSerializer(handover).data, status=201)


class CampusCommitteeCurrentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        if not user.institution_id:
            return Response({"error": "No campus is attached to this account."}, status=400)
        if user.role not in (User.Role.COMMITTEE_HEAD, User.Role.SYSTEM_ADMIN, User.Role.STAFF):
            return Response({"error": "Not allowed."}, status=403)
        return Response(
            {
                "institution": user.institution.short_name,
                "outgoing_committee": current_campus_committee(user.institution),
            }
        )


class CampusCommitteeHandoverConfirmView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _get(self, request, handover_id):
        return CampusCommitteeHandover.objects.filter(id=handover_id).first()

    def post(self, request, handover_id):
        handover = self._get(request, handover_id)
        if not handover:
            return Response({"error": "Handover not found."}, status=404)
        if not can_confirm_campus_handover(request.user, handover):
            return Response(
                {"error": "The campus system administrator confirms Committee Head handover."},
                status=403,
            )
        if handover.status != CampusCommitteeHandover.Status.NOMINATED:
            return Response({"error": "This handover is not waiting for confirmation."}, status=400)
        try:
            apply_campus_committee_handover(handover)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)
        handover.status = CampusCommitteeHandover.Status.CONFIRMED
        handover.confirmed_by = request.user
        handover.confirmed_at = timezone.now()
        handover.save()
        return Response(CampusCommitteeHandoverSerializer(handover).data)


class CampusCommitteeHandoverDeclineView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, handover_id):
        handover = CampusCommitteeHandover.objects.filter(id=handover_id).first()
        if not handover:
            return Response({"error": "Handover not found."}, status=404)
        if not (
            can_confirm_campus_handover(request.user, handover) or handover.outgoing_id == request.user.id
        ):
            return Response({"error": "Not allowed to decline this handover."}, status=403)
        handover.status = CampusCommitteeHandover.Status.DECLINED
        handover.save(update_fields=["status", "updated_at"])
        return Response(CampusCommitteeHandoverSerializer(handover).data)
