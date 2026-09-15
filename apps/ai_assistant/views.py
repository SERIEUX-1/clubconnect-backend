from django.utils import timezone
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.clubs.models import Club
from apps.core.permissions import IsCommitteeMember
from apps.evaluation.models import Score

from .models import AIRecommendation
from .providers import RecommendationRequest, get_provider
from .serializers import AIRecommendationSerializer


class AIRecommendationViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only: recommendations are created only by GenerateRecommendationView
    below, never via direct POST, so every one is traceable to a real
    provider call with model metadata attached."""

    serializer_class = AIRecommendationSerializer
    permission_classes = [permissions.IsAuthenticated, IsCommitteeMember]
    queryset = AIRecommendation.objects.all()


class GenerateRecommendationView(APIView):
    """
    POST /api/scores/{score_id}/generate-ai-recommendation/

    Human-governance workflow (PRS Section 11): this endpoint only ever
    WRITES an AIRecommendation + sets Score.ai_recommended_value /
    Score.stage=AI_RECOMMENDED. It never sets Score.final_value — only
    apps.evaluation.views.ScoreViewSet.approve (a Committee action with a
    required reason) can do that.
    """

    permission_classes = [permissions.IsAuthenticated, IsCommitteeMember]

    def post(self, request, score_id):
        score = Score.objects.select_related("criterion", "club").get(id=score_id)
        evidence_summaries = list(
            score.club.evidence_items.filter(activity__isnull=False, status="verified")
            .values_list("caption", flat=True)
        )
        provider = get_provider()
        result = provider.recommend_score(
            RecommendationRequest(
                criterion_label=score.criterion.label,
                criterion_description=score.criterion.description,
                evidence_summaries=evidence_summaries,
                club_context={"club_name": score.club.name},
            )
        )
        recommendation = AIRecommendation.objects.create(
            score=score,
            recommended_value=result.recommended_value,
            explanation=result.explanation,
            flags=result.flags,
            provider="anthropic",
            model_name=result.model_name,
            model_version_metadata=result.raw_metadata,
        )
        score.ai_recommended_value = result.recommended_value
        score.stage = Score.Stage.UNDER_REVIEW
        score.save(update_fields=["ai_recommended_value", "stage", "updated_at"])
        return Response(AIRecommendationSerializer(recommendation).data, status=201)


class AICoachFeedbackView(APIView):
    """Provides practical, actionable club coaching guidance based on actual metrics."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        club_id = request.query_params.get("club")
        user = request.user
        club = None
        if club_id:
            club = Club.objects.filter(id=club_id).first()
        elif user.role == User.Role.CLUB_LEADER:
            membership = user.memberships.filter(role="leader").first()
            if membership:
                club = membership.club
        if not club:
            club = Club.objects.first()

        provider = get_provider()
        club_context = {
            "name": club.name if club else "Your Club",
            "activity_count": club.activities.count() if club else 0,
            "has_collaboration": club.incoming_collaborations.filter(status="confirmed").exists() if club else False,
        }
        feedback = provider.generate_coach_feedback(club_context)
        return Response({
            "club_id": str(club.id) if club else None,
            "club_name": club.name if club else None,
            "feedback": feedback,
            "generated_at": timezone.now().isoformat(),
        })


class AIChatGuidanceView(APIView):
    """
    POST /api/ai-assistant/chat/
    Interactive institutional AI Copilot for all users.
    Answers how-to questions, clarifies workflows based on user role & permissions,
    and returns step-by-step actionable guides with direct execution links.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        user_message = request.data.get("message", "").strip()
        role = request.data.get("role") or (request.user.role if request.user.is_authenticated else "student")
        context = request.data.get("context", {})
        path = context.get("path", "")
        user_name = context.get("user_name") or (request.user.get_full_name() if request.user.is_authenticated else "Campus Member")

        msg_lower = user_message.lower()

        def has_any(words):
            return any(w in msg_lower for w in words)

        def has_all_pairs(pair_list):
            return any(all(w in msg_lower for w in pair) for pair in pair_list)

        # Knowledge Engine / Guidance Resolution
        # 1. REPORT SUBMISSION
        is_report_query = (
            has_all_pairs([["submit", "report"], ["file", "report"], ["send", "report"], ["create", "report"], ["write", "report"]])
            or has_any(["submit report", "activity report", "how to report", "file report", "send report", "reporting"])
        )

        # 2. EVENT SCHEDULING & QR TOKENS
        is_event_query = (
            has_all_pairs([["schedule", "event"], ["create", "event"], ["host", "event"], ["add", "event"], ["new", "event"], ["generate", "qr"]])
            or has_any(["schedule event", "create event", "qr token", "host event", "make event"])
        )

        # 3. QR CHECK-IN (STUDENTS)
        is_checkin_query = (
            has_all_pairs([["check", "in"], ["scan", "qr"], ["mark", "attendance"], ["record", "presence"]])
            or has_any(["check in", "check-in", "scan qr", "attendance", "mark attendance", "attend event"])
        )

        # 4. EVIDENCE UPLOAD & AUDIT
        is_evidence_query = (
            has_all_pairs([["upload", "evidence"], ["submit", "evidence"], ["verify", "evidence"], ["audit", "evidence"], ["upload", "proof"]])
            or has_any(["upload evidence", "evidence", "proof", "verify evidence", "audit evidence", "receipt", "roster"])
        )

        # 5. CROSS-CLUB COLLABORATION
        is_collab_query = (
            has_any(["collab", "collaboration", "partner", "joint", "bonus point", "co-host", "partnering"])
        )

        # 6. AT-RISK CLUBS & HEALTH ADVISORIES
        is_health_query = (
            has_any(["at risk", "at-risk", "health", "advisory", "help club", "intervention", "grace period", "struggling", "probation"])
        )

        # 7. CCEA AWARDS & REVEAL
        is_ccea_query = (
            has_any(["ccea", "award", "ceremony", "reveal", "winner", "trophy", "honors roll", "unveil", "rehearsal"])
        )

        # 8. DEAN NOTICES & SCORECARDS
        is_dean_query = (
            has_any(["dean", "broadcast", "notice", "circular", "executive", "scorecard", "briefing"])
        )

        # 9. ADMIN & USER MANAGEMENT
        is_admin_query = (
            has_all_pairs([["manage", "user"], ["change", "role"], ["pending", "club"], ["system", "setting"]])
            or has_any(["admin", "manage users", "settings", "charter", "pending club", "iam", "permissions"])
        )

        # 10. DISCOVER CLUBS & JOINING
        is_discover_query = (
            has_all_pairs([["join", "club"], ["find", "club"], ["how to join"], ["apply", "club"]])
            or has_any(["discover", "join club", "find club", "passport", "directory"])
        )

        if is_report_query:
            if role in ["club_leader", "system_admin"]:
                reply = (
                    f"Hello {user_name}! As a **Club Leader**, here is how to submit your activity report on ClubConnect "
                    f"following the PRS §6 institutional storytelling framework:"
                )
                steps = [
                    "Go to your **Leader Dashboard** (`/leader-dashboard`).",
                    "Under the **Quick Actions** panel at the top, click the **'Submit Report'** button (or click the button below).",
                    "Fill in the PRS §6 narrative structure: Problem Statement, Objective ('What we set out to do'), and Results ('What happened').",
                    "Enter the verified attendee count to satisfy your club's Quorum requirement.",
                    "Attach any primary evidence artifacts (e.g. sign-in sheets or event photos).",
                    "Click **'Submit for Committee Verification'**. Your report will immediately appear in the Review Committee audit queue.",
                ]
                actions = [
                    {"label": "Open Submit Report Form", "action": "open_submit_report", "path": "/leader-dashboard"},
                    {"label": "Go to Leader Dashboard", "path": "/leader-dashboard"},
                ]
                suggestions = [
                    "How do I upload evidence for this event?",
                    "How do I schedule our next event?",
                    "How do I propose a cross-club collaboration?",
                ]
            else:
                reply = (
                    f"Activity reports are submitted by authorized **Club Leaders**. In your current view as a **{role.replace('_', ' ').title()}**, "
                    f"you can switch to the Club Leader persona in the top navigation bar to test the report submission workflow."
                )
                steps = [
                    "Click the **Persona Switcher** in the top navigation bar.",
                    "Select **Club Leader (Alex Chen)**.",
                    "Navigate to the **Leader Dashboard** and click **Submit Report**.",
                ]
                actions = [
                    {"label": "Go to Leader Dashboard", "path": "/leader-dashboard"},
                ]
                suggestions = [
                    "How do I switch roles?",
                    "What can I do in my current role?",
                ]

        # 2. EVENT SCHEDULING & QR TOKENS
        elif is_event_query:
            reply = (
                f"Here is how event scheduling and automated QR attendance work on ClubConnect:"
            )
            steps = [
                "Open your **Leader Dashboard** (`/leader-dashboard`).",
                "Click **'Schedule Event'** under Quick Actions.",
                "Specify the Event Title, Date & Time, Venue/Location, and Expected Quorum.",
                "Ensure **'Enable QR Check-In'** is toggled ON to generate a secure dynamic token (e.g., `CYBER-SEC-2026`).",
                "Click **'Schedule & Generate QR'**. You can copy the generated token or display the QR code at your venue for instant attendee check-in.",
            ]
            actions = [
                {"label": "Schedule New Event", "action": "open_schedule_event", "path": "/leader-dashboard"},
                {"label": "Go to Leader Dashboard", "path": "/leader-dashboard"},
            ]
            suggestions = [
                "How do students check in with the QR code?",
                "How do I submit an activity report after the event?",
            ]

        # 3. QR CHECK-IN (STUDENTS)
        elif is_checkin_query:
            reply = (
                f"Hi {user_name}! Students can record verified attendance in two simple steps:"
            )
            steps = [
                "Navigate to your **Student Dashboard** (`/student-dashboard`).",
                "Click the **'Scan QR Check-In'** button, or click **'Check In'** on the active event banner.",
                "Point your camera at the event's QR code, or paste the event check-in token (e.g., `CYBER-SEC-2026`).",
                "Click **'Verify & Check In'**. You will see celebratory confetti and your attendance ledger will update instantly!",
            ]
            actions = [
                {"label": "Open QR Check-In Scanner", "action": "open_qr_checkin", "path": "/student-dashboard"},
                {"label": "View My Attendance Ledger", "action": "open_attendance_history", "path": "/student-dashboard"},
            ]
            suggestions = [
                "How do I see my total CCEA points?",
                "How do I join a new club?",
            ]

        # 4. EVIDENCE UPLOAD & VERIFICATION
        elif is_evidence_query:
            if role in ["committee_head", "committee_member"]:
                reply = (
                    f"As a **Review Committee Auditor**, here is how to review and verify club evidence:"
                )
                steps = [
                    "Go to the **Review Queue** at `/committee-dashboard`.",
                    "Filter evidence items by status: **Pending**, **Verified**, or **Rejected**.",
                    "Click on any row to open the **Evidence Detail Inspector**.",
                    "Review the simulated AI 96% confidence score match against the club's stated objective.",
                    "Enter your audit sign-off notes and click **'Verify Evidence'** or **'Reject with Feedback'**.",
                    "You can also use **'Batch Verify Clean Evidence'** to process high-confidence artifacts at once.",
                ]
                actions = [
                    {"label": "Open Review Committee Queue", "path": "/committee-dashboard"},
                ]
                suggestions = [
                    "How does batch verification work?",
                    "How do I export the review audit log?",
                ]
            else:
                reply = (
                    f"Club Leaders upload evidence to prove activity completion and earn CCEA merit points:"
                )
                steps = [
                    "Go to your **Leader Dashboard** (`/leader-dashboard`).",
                    "Click the **'Upload Evidence'** action button.",
                    "Select the artifact type (Event Photograph, Attendance Sign-in Roster, Financial Receipt, or Minutes).",
                    "Select which activity this evidence supports and write a brief description.",
                    "Click **'Submit for Verification'** to trigger AI preprocessing and committee inspection.",
                ]
                actions = [
                    {"label": "Upload Evidence Now", "action": "open_upload_evidence", "path": "/leader-dashboard"},
                ]
                suggestions = [
                    "How do I submit the final activity report?",
                    "How do I propose a cross-club collaboration?",
                ]

        # 5. CROSS-CLUB COLLABORATIONS
        elif is_collab_query:
            reply = (
                f"Cross-club collaborations are one of the highest-leverage actions on ClubConnect! "
                f"Confirmed partnerships award **+10 CCEA bonus points** under institutional criteria §6."
            )
            steps = [
                "Go to **Leader Dashboard** (`/leader-dashboard`).",
                "Click **'Propose Collaboration'** in Quick Actions or in the Partnerships sidebar.",
                "Choose an institutional partner from the recognized campus clubs.",
                "Outline the joint objective, expected student impact, and proposed date.",
                "Click **'Submit Proposal'**. When confirmed by both clubs, both receive verified CCEA bonus credentials.",
            ]
            actions = [
                {"label": "Propose New Collaboration", "action": "open_propose_collab", "path": "/leader-dashboard"},
            ]
            suggestions = [
                "How do CCEA rankings work?",
                "How do I schedule a collaborative event?",
            ]

        # 6. AT-RISK CLUBS & HEALTH ADVISORIES (PRS §15)
        elif is_health_query:
            reply = (
                f"ClubConnect adheres to the PRS §15 philosophy: **'Development Before Punishment'**. "
                f"At-risk clubs receive developmental interventions rather than punitive sanctions."
            )
            steps = [
                "Go to the **Command Center** (`/command-center`).",
                "Inspect the Club Health table. Statuses include **Healthy** (Score 70+), **Needs Attention** (50-69), and **At Risk** (<50).",
                "For any struggling club, click **'Help Club'** to open the Health Advisory Modal.",
                "Select a targeted developmental intervention (Quorum Grace Period, Faculty Consultation, Leadership Coaching).",
                "Issue the advisory to provide clear milestone steps for the club to recover to healthy standing.",
            ]
            actions = [
                {"label": "Open Command Center", "path": "/command-center"},
            ]
            suggestions = [
                "How do I run an AI Health Diagnostic?",
                "How does CCEA Reveal Mode work?",
            ]

        # 7. CCEA AWARDS & REVEAL CEREMONY
        elif is_ccea_query:
            reply = (
                f"The **Club Contribution & Excellence Awards (CCEA)** recognize outstanding campus organizations. "
                f"Ceremony Mode (`/ccea-reveal`) provides live unmasking controls for committee heads:"
            )
            steps = [
                "Navigate to **CCEA Reveal Mode** (`/ccea-reveal`).",
                "Click **'Reveal Winner'** on any category card to unveil the award with celebratory confetti.",
                "Click **'Reveal All Winners'** during the ceremony finale for a multi-burst confetti celebration.",
                "Click **'Export Honors Roll (CSV)'** to download the official institutional certificate roll.",
                "Click **'Reset Rehearsal'** to return outcomes to confidential sealed mode before the event.",
            ]
            actions = [
                {"label": "Go to CCEA Reveal Mode", "path": "/ccea-reveal"},
                {"label": "View CCEA Leaderboard", "path": "/student-dashboard"},
            ]
            suggestions = [
                "What criteria determine CCEA rankings?",
                "How do I issue a health advisory?",
            ]

        # 8. DEAN NOTICES & 5-DIMENSION SCORECARDS
        elif is_dean_query:
            reply = (
                f"The **Dean Dashboard** (`/dean-dashboard`) empowers institutional executives with governance controls:"
            )
            steps = [
                "Navigate to the **Dean Dashboard** (`/dean-dashboard`).",
                "Click **'Broadcast Notice'** to compose executive circulars targeting all clubs, presidents, or committee reviewers.",
                "Click on any club row in the Institutional Rankings to open the **5-Dimension Club Scorecard Drilldown**.",
                "Click **'Download Executive Brief'** to export campus-wide compliance and health metrics in CSV format.",
            ]
            actions = [
                {"label": "Go to Dean Dashboard", "path": "/dean-dashboard"},
                {"label": "Broadcast Notice", "action": "open_broadcast_notice", "path": "/dean-dashboard"},
            ]
            suggestions = [
                "How do I download the executive brief?",
                "How are club health tiers calculated?",
            ]

        # 9. ADMIN SETTINGS & IAM USER MANAGEMENT
        elif is_admin_query:
            reply = (
                f"As a **System Administrator**, you have complete governance over the ClubConnect ecosystem:"
            )
            steps = [
                "Go to the **Admin Dashboard** (`/admin-dashboard`).",
                "Click **'Manage Users'** to search directory, assign roles (Student, Leader, Committee, Dean), or toggle status.",
                "Click **'System Settings'** to adjust CCEA scoring weights, minimum attendance quorum %, and grace periods.",
                "Click **'Pending Clubs'** to review student charter applications and grant official institutional stamps.",
                "Inspect the tamper-evident **Institutional Audit Log** and export CSV records.",
            ]
            actions = [
                {"label": "Open Admin Dashboard", "path": "/admin-dashboard"},
                {"label": "Manage IAM Users", "action": "open_manage_users", "path": "/admin-dashboard"},
                {"label": "Review Pending Charters", "action": "open_pending_clubs", "path": "/admin-dashboard"},
            ]
            suggestions = [
                "How do I configure CCEA weights?",
                "How do I review audit logs?",
            ]

        # 10. DISCOVER CLUBS & DIGITAL PASSPORTS
        elif is_discover_query:
            reply = (
                f"Every recognized student club carries an official **Digital Club Passport** documenting verified activities and impact:"
            )
            steps = [
                "Visit **Discover Clubs** (`/`).",
                "Search by name or filter by category (Technology, Arts, Cultural, Sports, Entrepreneurship).",
                "Click on any club's passport card to inspect their verified activities, impact projects, and faculty charter.",
                "Click **'Request to Join Club'** in the hero banner to submit your membership request.",
                "Click **'Share'** to copy the club's permanent passport link.",
            ]
            actions = [
                {"label": "Explore Discover Clubs", "path": "/"},
            ]
            suggestions = [
                "How do I scan QR codes at club events?",
                "How do I see my attendance records?",
            ]

        # 11. GENERAL / ROLE OVERVIEW FALLBACK
        else:
            role_title = role.replace('_', ' ').title()
            reply = (
                f"Welcome {user_name}! I am your **ClubConnect Institutional AI Assistant**. "
                f"You are currently operating in the **{role_title}** role. Here is what you can accomplish on the platform:"
            )
            if role == "student":
                steps = [
                    "**Scan QR Check-In**: Mark verified presence at club events on `/student-dashboard`.",
                    "**Attendance History**: View your verified attendance record, rate %, and CCEA points.",
                    "**Discover Clubs**: Explore club digital passports at `/` and apply to join.",
                    "**CCEA Rankings**: Check current institutional standings of all campus clubs.",
                ]
                actions = [
                    {"label": "Go to Student Dashboard", "path": "/student-dashboard"},
                    {"label": "Scan QR Check-In", "action": "open_qr_checkin", "path": "/student-dashboard"},
                ]
                suggestions = [
                    "How do I check in to an event?",
                    "How do I join a club?",
                    "How do CCEA points work?",
                ]
            elif role == "club_leader":
                steps = [
                    "**Submit Activity Reports**: File narrative PRS §6 reports for committee review.",
                    "**Schedule Events & QR Tokens**: Generate dynamic QR check-in codes for your attendees.",
                    "**Upload Evidence**: Attach photos, rosters, and receipts for AI screening.",
                    "**Propose Collaborations**: Partner with other clubs to gain +10 CCEA bonus points.",
                ]
                actions = [
                    {"label": "Go to Leader Dashboard", "path": "/leader-dashboard"},
                    {"label": "Submit Activity Report", "action": "open_submit_report", "path": "/leader-dashboard"},
                ]
                suggestions = [
                    "How do I submit an activity report?",
                    "How do I schedule an event?",
                    "How do I collaborate with other clubs?",
                ]
            elif role == "committee_member":
                steps = [
                    "**Audit Evidence**: Inspect submitted artifacts with AI 96% match scores at `/committee-dashboard`.",
                    "**Verify or Reject**: Provide reviewer justification notes and sign off.",
                    "**Batch Verify**: Process clean, compliant evidence in one click.",
                    "**Export Audit Log**: Download complete CSV review history.",
                ]
                actions = [
                    {"label": "Go to Review Queue", "path": "/committee-dashboard"},
                ]
                suggestions = [
                    "How do I review and verify evidence?",
                    "How does batch verification work?",
                ]
            elif role == "committee_head":
                steps = [
                    "**Command Center**: Monitor health of all campus clubs at `/command-center`.",
                    "**Developmental Interventions**: Issue PRS §15 health advisories to at-risk clubs.",
                    "**AI Health Diagnostic**: Run automated diagnostic scans across all clubs.",
                    "**CCEA Reveal Mode**: Host the live awards ceremony at `/ccea-reveal`.",
                ]
                actions = [
                    {"label": "Go to Command Center", "path": "/command-center"},
                    {"label": "Open CCEA Reveal Mode", "path": "/ccea-reveal"},
                ]
                suggestions = [
                    "How do I issue a health advisory?",
                    "How do I reveal CCEA winners?",
                ]
            elif role == "dean_admin":
                steps = [
                    "**Executive Analytics**: View campus participation, compliance, and health on `/dean-dashboard`.",
                    "**Broadcast Circulars**: Send official executive notices to clubs or reviewers.",
                    "**5-Dimension Scorecards**: Inspect deep club performance metrics.",
                    "**Download Brief**: Export campus health reports in CSV.",
                ]
                actions = [
                    {"label": "Go to Dean Dashboard", "path": "/dean-dashboard"},
                ]
                suggestions = [
                    "How do I broadcast an institutional notice?",
                    "How do I inspect 5-dimension scorecards?",
                ]
            else:
                steps = [
                    "**IAM Directory**: Manage user roles and account statuses on `/admin-dashboard`.",
                    "**Charter Approvals**: Grant recognition stamps to newly chartered clubs.",
                    "**System Configuration**: Adjust CCEA weights, quorum thresholds, and grace periods.",
                    "**Audit Trail**: Review immutable security logs.",
                ]
                actions = [
                    {"label": "Go to Admin Dashboard", "path": "/admin-dashboard"},
                ]
                suggestions = [
                    "How do I manage users?",
                    "How do I adjust scoring thresholds?",
                ]

        return Response({
            "reply": reply,
            "steps": steps,
            "action_buttons": actions,
            "suggestions": suggestions,
            "role": role,
            "generated_at": timezone.now().isoformat(),
        })

