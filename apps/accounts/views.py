from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import CustomTokenObtainPairSerializer, RegisterSerializer, UserProfileSerializer


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class DemoPersonasView(APIView):
    """Lists available demo personas for instant one-click testing across all roles."""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        personas = [
            {
                "role": "student",
                "label": "Student",
                "name": "Alex Mercer",
                "email": "alex.student@campus.edu",
                "password": "Pass1234!",
                "description": "Discover & join clubs, QR check-in to events, view personal memberships.",
                "badge": "Active Member",
            },
            {
                "role": "club_leader",
                "label": "Club Leader",
                "name": "Sarah Chen",
                "email": "sarah.leader@campus.edu",
                "password": "Pass1234!",
                "club_name": "Robotics & AI Society",
                "description": "Submit monthly reports, schedule events & generate QR, manage evidence & collaborations.",
                "badge": "Robotics Lead",
            },
            {
                "role": "committee_member",
                "label": "Committee Member",
                "name": "Marcus Vance",
                "email": "marcus.member@campus.edu",
                "password": "Pass1234!",
                "description": "Review assigned clubs, inspect evidence queue, evaluate AI scoring recommendations.",
                "badge": "Assigned Reviewer",
            },
            {
                "role": "committee_head",
                "label": "Committee Head",
                "name": "Dr. Elena Rostova",
                "email": "dr.elena.head@campus.edu",
                "password": "Pass1234!",
                "description": "Governance command center, confidential rankings, criteria weights & CCEA Reveal Mode.",
                "badge": "Governance Head",
            },
            {
                "role": "dean_admin",
                "label": "Dean / Institutional Admin",
                "name": "Dean Arthur Harrison",
                "email": "dean.harrison@campus.edu",
                "password": "Pass1234!",
                "description": "Macro institutional analytics, campus engagement trends, strategic CCEA insights.",
                "badge": "Institutional Exec",
            },
            {
                "role": "system_admin",
                "label": "System Administrator",
                "name": "Admin Root",
                "email": "admin@campus.edu",
                "password": "Pass1234!",
                "description": "Full system oversight, audit trails, security configurations & user management.",
                "badge": "Superadmin",
            },
        ]
        return Response(personas)


class SwitchRoleView(APIView):
    """Allows testing different permission roles by updating the active demo user's role or issuing a token."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        target_role = request.data.get("role")
        if target_role not in dict(User.Role.choices):
            return Response({"error": f"Invalid role '{target_role}'"}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        user.role = target_role
        user.save(update_fields=["role", "updated_at"])

        refresh = RefreshToken.for_user(user)
        return Response({
            "detail": f"Role updated to {user.get_role_display()}",
            "access": str(refresh.access_token),
            "user": {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "full_name": user.get_full_name() or user.username,
                "role": user.role,
                "student_id": user.student_id,
                "assigned_clubs": list(user.assigned_club_ids()),
            },
        })
