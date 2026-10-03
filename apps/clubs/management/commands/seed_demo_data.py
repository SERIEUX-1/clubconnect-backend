from datetime import date, datetime, timedelta
from decimal import Decimal
import re

from django.utils.text import slugify

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import Institution, User
from apps.activities.models import Activity
from apps.attendance.models import AttendanceRecord
from apps.audit.models import AuditLog
from apps.awards.models import Award, HallOfExcellenceEntry
from apps.clubs.alche_register import (
    ALCHE_CLUBS,
    ALCHE_STAFF_DOMAINS,
    ALCHE_STUDENT_DOMAINS,
    club_officer_rows,
    is_licensed_student_email,
    split_person_name,
)
from apps.clubs.models import Club, ClubBudgetSpend, ClubConceptNote, ClubMembership, ClubHealthSnapshot, LeadershipTerm
from apps.collaborations.models import Collaboration
from apps.evaluation.models import EvaluationCriterion, EvaluationCycle, Score, ScoreAdjustment
from apps.ai_assistant.models import AIRecommendation
from apps.events.models import Event
from apps.evidence.models import Evidence, EvidenceReview
from apps.impact.models import ImpactProject
from apps.notifications.models import Notification
from apps.reporting.models import MonthlyReport


class Command(BaseCommand):
    help = "Seeds comprehensive, realistic institutional demo data for all roles and modules."

    def execute(self, *args, **options):
        from apps.notifications.dispatch import mute_notifications

        with mute_notifications():
            return super().execute(*args, **options)

    def handle(self, *args, **options):
        self.stdout.write("Starting ALCHE institutional data seeding...")

        alche, _ = Institution.objects.update_or_create(
            slug="alche",
            defaults={
                "name": "African Leadership College of Higher Education",
                "short_name": "ALCHE",
                "kind": Institution.Kind.UNIVERSITY,
                "country": "Mauritius",
                "city": "Pamplemousses",
                "allowed_email_domains": [
                    *ALCHE_STUDENT_DOMAINS,
                    *ALCHE_STAFF_DOMAINS,
                ],
                "student_email_domains": list(ALCHE_STUDENT_DOMAINS),
                "staff_email_domains": list(ALCHE_STAFF_DOMAINS),
                "awards_enabled": True,
                "awards_program_name": "Campus Clubs Excellence Awards",
                "academic_year_start_month": 8,
                "academic_year_label": "",
                "report_deadline_day": 5,
                "privacy_contact_email": "arthur.harrison@alueducation.com",
                "membership_census_open": False,
                "member_grant_amount": Decimal("7.00"),
                "member_grant_currency": "USD",
                "is_active": True,
                "logo_url": "/institutions/alche-logo.png",
                "primary_color": "#D00D2D",
            },
        )
        self.stdout.write(self.style.SUCCESS(f"Licensed institution: {alche.name}"))

        # ----------------------------------------------------------------------
        # 1. Users for all 6 Roles
        # ----------------------------------------------------------------------
        password = "Pass1234!"
        
        users_data = [
            {
                "username": "alex_student",
                "email": "alex.student@alustudent.com",
                "first_name": "Alex",
                "last_name": "Mercer",
                "role": User.Role.STUDENT,
                "student_id": "STU-2026-0812",
                "phone_number": "+1-555-0192",
            },
            {
                "username": "sarah_leader",
                "email": "sarah.leader@alustudent.com",
                "first_name": "Sarah",
                "last_name": "Chen",
                "role": User.Role.CLUB_LEADER,
                "student_id": "STU-2024-0194",
                "phone_number": "+1-555-0144",
            },
            {
                "username": "marcus_member",
                "email": "marcus.vance@alustudent.com",
                "first_name": "Marcus",
                "last_name": "Vance",
                "role": User.Role.STUDENT,
                "student_id": "STU-2025-0032",
                "phone_number": "+1-555-0155",
            },
            {
                "username": "elena_head",
                "email": "dr.elena.head@alustudent.com",
                "first_name": "Dr. Elena",
                "last_name": "Rostova",
                "role": User.Role.COMMITTEE_HEAD,
                "student_id": "ADM-2018-0001",
                "phone_number": "+1-555-0100",
                "is_staff": True,
            },
            {
                "username": "dean_harrison",
                "email": "arthur.harrison@alueducation.com",
                "first_name": "Arthur",
                "last_name": "Harrison",
                "role": User.Role.STAFF,
                "student_id": "STF-2015-0010",
                "phone_number": "+1-555-0111",
                "is_staff": True,
            },
            {
                "username": "nia_lecturer",
                "email": "nia.mwangi@alueducation.com",
                "first_name": "Nia",
                "last_name": "Mwangi",
                "role": User.Role.STAFF,
                "student_id": "STF-2019-0044",
                "phone_number": "+1-555-0166",
                "is_staff": True,
            },
            {
                "username": "admin_root",
                "email": "admin@alueducation.com",
                "first_name": "System",
                "last_name": "Administrator",
                "role": User.Role.SYSTEM_ADMIN,
                "student_id": "SYS-2020-9999",
                "phone_number": "+1-555-0199",
                "is_staff": True,
                "is_superuser": True,
            },
        ]

        users = {}
        for u_info in users_data:
            user, created = User.objects.get_or_create(
                username=u_info["username"],
                defaults={
                    "institution": alche,
                    "email": u_info["email"],
                    "first_name": u_info["first_name"],
                    "last_name": u_info["last_name"],
                    "role": u_info["role"],
                    "student_id": u_info["student_id"],
                    "phone_number": u_info["phone_number"],
                    "is_staff": u_info.get("is_staff", False),
                    "is_superuser": u_info.get("is_superuser", False),
                },
            )
            user.set_password(password)
            user.institution = alche
            user.role = u_info["role"]
            user.email = u_info["email"]
            user.first_name = u_info["first_name"]
            user.last_name = u_info["last_name"]
            user.save()
            users[u_info["username"]] = user

        users["elena_head"].last_login = timezone.now() - timedelta(days=18)
        users["elena_head"].save(update_fields=["last_login"])

        self.stdout.write(self.style.SUCCESS(f"Seeded {len(users)} users across all 6 roles."))

        # ----------------------------------------------------------------------
        # 2. Clubs — official ALCHE Clubs and Societies Database + ExCo
        # ----------------------------------------------------------------------
        CYCLE_DATES = {"August 2025": date(2025, 8, 1), "March 2026": date(2026, 3, 1)}
        CYCLE_YEARS = {"August 2025": "2025-2026", "March 2026": "2025-2026"}

        clubs_data = []
        for row in ALCHE_CLUBS:
            cycle = row["cycle"]
            status = row["status"]
            officers = club_officer_rows(row)
            licensed_contact = next(
                (o["email"] for o in officers if is_licensed_student_email(o.get("email"))),
                "",
            )
            charter_bits = [
                f"Registered {cycle} in the ALCHE Clubs and Societies Database.",
            ]
            if row.get("constitution"):
                charter_bits.append(f"Constitution on file: {row['constitution']}.")
            if row.get("notes"):
                charter_bits.append(row["notes"])
            clubs_data.append(
                {
                    "name": row["name"],
                    "slug": slugify(row["name"]),
                    "category": row["category"],
                    "status": status,
                    "established_date": CYCLE_DATES.get(cycle, date(2025, 8, 1)),
                    "description": row["description"],
                    "mission": row["description"],
                    "vision": "",
                    "objectives": "",
                    "charter_statement": " ".join(charter_bits),
                    "is_archived": status == Club.Status.DORMANT,
                    "public_contact_email": licensed_contact,
                    "public_contact_channels": {
                        "cycle": cycle,
                        "constitution": row.get("constitution") or "",
                        "notes": row.get("notes") or "",
                        "officers": officers,
                    },
                }
            )

        clubs = {}
        for c_info in clubs_data:
            club, _ = Club.objects.update_or_create(
                institution=alche,
                slug=c_info["slug"],
                defaults={**c_info, "institution": alche, "is_archived": c_info.get("is_archived", False)},
            )
            clubs[club.name] = club

        keep_slugs = {c["slug"] for c in clubs_data}
        Club.objects.filter(institution=alche).exclude(slug__in=keep_slugs).update(
            status=Club.Status.DORMANT,
            is_archived=True,
        )

        # ----------------------------------------------------------------------
        # 3. Memberships & Leadership (workbook ExCo + demo Robotics leader)
        # ----------------------------------------------------------------------
        def username_for_email(email):
            local = re.sub(r"[^a-z0-9]+", "_", email.split("@")[0].lower()).strip("_")[:40]
            return local or "officer"

        def officer_account(person, make_leader):
            email = (person.get("email") or "").strip()
            if not is_licensed_student_email(email):
                return None
            first, last = split_person_name(person.get("name") or "")
            existing = User.objects.filter(email__iexact=email).first()
            if existing:
                if make_leader and existing.role == User.Role.STUDENT:
                    existing.role = User.Role.CLUB_LEADER
                    existing.save(update_fields=["role", "updated_at"])
                return existing
            base = username_for_email(email)
            username = base
            n = 2
            while User.objects.filter(username=username).exists():
                username = f"{base}_{n}"
                n += 1
            user = User(
                username=username,
                email=email.lower(),
                first_name=first,
                last_name=last,
                institution=alche,
                role=User.Role.CLUB_LEADER if make_leader else User.Role.STUDENT,
            )
            user.set_password(password)
            user.save()
            return user

        for row in ALCHE_CLUBS:
            club = clubs[row["name"]]
            cycle = row["cycle"]
            academic_year = CYCLE_YEARS.get(cycle, "2025-2026")
            start = CYCLE_DATES.get(cycle, date(2025, 8, 1))
            for officer in club_officer_rows(row):
                is_president = officer["title"] == "President"
                account = officer_account(officer, make_leader=is_president)
                if not account:
                    continue
                membership_role = (
                    ClubMembership.MembershipRole.LEADER
                    if is_president
                    else ClubMembership.MembershipRole.OFFICER
                )
                ClubMembership.objects.update_or_create(
                    club=club,
                    user=account,
                    defaults={
                        "role": membership_role,
                        "status": ClubMembership.Status.APPROVED,
                        "is_active": True,
                        "joined_at": start,
                    },
                )
                LeadershipTerm.objects.get_or_create(
                    club=club,
                    user=account,
                    academic_year=academic_year,
                    defaults={
                        "position_title": officer["title"],
                        "start_date": start,
                    },
                )

        ClubMembership.objects.update_or_create(
            club=clubs["Robotics club"],
            user=users["sarah_leader"],
            defaults={
                "role": ClubMembership.MembershipRole.LEADER,
                "status": ClubMembership.Status.APPROVED,
                "joined_at": date(2024, 9, 1),
            },
        )
        LeadershipTerm.objects.get_or_create(
            club=clubs["Robotics club"],
            user=users["sarah_leader"],
            academic_year="2026-2027",
            defaults={
                "position_title": "President & Technical Director",
                "start_date": date(2026, 9, 1),
                "achievements_summary": "Expanded ML bootcamps and secured faculty grant.",
            },
        )

        ClubMembership.objects.update_or_create(
            club=clubs["Robotics club"],
            user=users["alex_student"],
            defaults={"role": ClubMembership.MembershipRole.MEMBER, "status": ClubMembership.Status.APPROVED},
        )
        ClubMembership.objects.update_or_create(
            club=clubs["Alchemists Gardening Club"],
            user=users["alex_student"],
            defaults={"role": ClubMembership.MembershipRole.MEMBER, "status": ClubMembership.Status.APPROVED},
        )
        ClubMembership.objects.update_or_create(
            club=clubs["Alchemist Creators"],
            user=users["alex_student"],
            defaults={"role": ClubMembership.MembershipRole.MEMBER, "status": ClubMembership.Status.REQUESTED},
        )

        self.stdout.write(self.style.SUCCESS(f"Seeded {len(clubs)} clubs with memberships and leadership."))

        robotics = clubs["Robotics club"]
        year = alche.current_academic_year()
        note, _ = ClubConceptNote.objects.update_or_create(
            club=robotics,
            title="Line-follower kits for first-year members",
            academic_year=year,
            defaults={
                "submitted_by": users["sarah_leader"],
                "purpose": "Buy ten training kits so exclusive and sharing members can run the open lab without using personal funds.",
                "amount_requested": Decimal("120.00"),
                "status": ClubConceptNote.Status.SUBMITTED,
            },
        )
        ClubBudgetSpend.objects.update_or_create(
            club=robotics,
            comment="Venue hire for the ML bootcamp closing exhibition.",
            academic_year=year,
            defaults={
                "recorded_by": users["elena_head"],
                "amount": Decimal("40.00"),
                "spent_on": date(2026, 9, 20),
                "concept_note": None,
            },
        )

        # ----------------------------------------------------------------------
        # 4. Activities & Impact Projects
        # ----------------------------------------------------------------------
        now = timezone.now()
        act1, _ = Activity.objects.update_or_create(
            club=clubs["Robotics club"],
            title="Beginner Machine Learning Bootcamp",
            defaults={
                "activity_type": "Workshop",
                "status": Activity.Status.VERIFIED,
                "date_time": now - timedelta(days=20),
                "location": "Turing Engineering Hall, Lab 3B",
                "objective": "Give first-year students a working machine-learning classifier in a single afternoon, removing the intimidation barrier around AI.",
                "description": "Interactive Python & Scikit-Learn session covering data preprocessing, model fitting, and evaluation on real sensor data.",
                "expected_participation": 35,
                "actual_participation": 42,
                "report_text": "42 students attended, up from 26 last term. 9 out of 10 post-session survey respondents said they'd attend a follow-up session.",
                "lessons_learned": "Provide pre-configured virtual environments next term to reduce initial installation setup time.",
                "submitted_by": users["sarah_leader"],
                "submitted_at": now - timedelta(days=19),
            },
        )

        act2, _ = Activity.objects.update_or_create(
            club=clubs["Robotics club"],
            title="Autonomous Line-Follower Challenge",
            defaults={
                "activity_type": "Competition",
                "status": Activity.Status.VERIFIED,
                "date_time": now - timedelta(days=8),
                "location": "Student Union Atrium",
                "objective": "A friendly build-and-race competition to apply control-systems theory learned in the workshop series.",
                "description": "14 multi-faculty teams raced Arduino-based rovers on an obstacle-strewn track.",
                "expected_participation": 50,
                "actual_participation": 64,
                "report_text": "14 teams competed. Partnered with the Engineering Faculty for judging and prize sponsorship.",
                "lessons_learned": "Ensure track surface has higher friction coefficient for optical infrared sensors.",
                "submitted_by": users["sarah_leader"],
                "submitted_at": now - timedelta(days=7),
            },
        )

        act3, _ = Activity.objects.update_or_create(
            club=clubs["Robotics club"],
            title="Campus AI Hackathon 2026",
            defaults={
                "activity_type": "Hackathon",
                "status": Activity.Status.SUBMITTED,
                "date_time": now - timedelta(days=2),
                "location": "Innovation Hub & Online",
                "objective": "48-hour collaborative build sprint creating campus-assistant prototypes.",
                "description": "Over 80 students registered across 20 teams.",
                "expected_participation": 80,
                "actual_participation": 78,
                "report_text": "78 active builders completed 16 project submissions.",
                "submitted_by": users["sarah_leader"],
                "submitted_at": now - timedelta(days=1),
            },
        )

        env_act, _ = Activity.objects.update_or_create(
            club=clubs["Alchemists Gardening Club"],
            title="Native Campus Tree Planting Drive",
            defaults={
                "activity_type": "Community Service",
                "status": Activity.Status.VERIFIED,
                "date_time": now - timedelta(days=14),
                "location": "North Campus Arboretum",
                "objective": "Plant 150 indigenous saplings along the campus water basin to prevent soil erosion.",
                "description": "Hands-on conservation day involving 55 student volunteers and campus grounds staff.",
                "expected_participation": 40,
                "actual_participation": 55,
                "report_text": "Planted 165 saplings in 4 hours. Irrigation system verified and mulch applied.",
                "submitted_by": users["sarah_leader"],
                "submitted_at": now - timedelta(days=13),
            },
        )

        debate_act, _ = Activity.objects.update_or_create(
            club=clubs["The Alchemists' Times"],
            title="Campus newspaper launch night",
            defaults={
                "activity_type": "Public Event",
                "status": Activity.Status.VERIFIED,
                "date_time": now - timedelta(days=11),
                "location": "Main Auditorium",
                "objective": "Launch The Alchemists' Times to the campus community.",
                "description": "Reading of the latest issue, editor introductions, and an open call for student correspondents.",
                "expected_participation": 80,
                "actual_participation": 96,
                "report_text": "96 students attended. The issue is published on the club page.",
                "submitted_by": users["sarah_leader"],
                "submitted_at": now - timedelta(days=10),
            },
        )

        health_act, _ = Activity.objects.update_or_create(
            club=clubs["ACF (ALCHE Christian Fellowship) Society"],
            title="Fellowship gathering",
            defaults={
                "activity_type": "Community Service",
                "status": Activity.Status.VERIFIED,
                "date_time": now - timedelta(days=18),
                "location": "Campus chapel hall",
                "objective": "Weekly fellowship and service for students in ACF.",
                "description": "Worship, discussion, and a welcome for new members.",
                "expected_participation": 40,
                "actual_participation": 52,
                "report_text": "52 students attended. A recording is on the club page.",
                "submitted_by": users["sarah_leader"],
                "submitted_at": now - timedelta(days=17),
            },
        )

        chess_act, _ = Activity.objects.update_or_create(
            club=clubs["Zero to checkmate"],
            title="Campus Blitz Championship",
            defaults={
                "activity_type": "Competition",
                "status": Activity.Status.VERIFIED,
                "date_time": now - timedelta(days=6),
                "location": "Student Union Lounge",
                "objective": "Run an inclusive Swiss blitz that beginners and rated players can both join.",
                "description": "Boards, clocks, live board cameras, and a recap video of the final round.",
                "expected_participation": 30,
                "actual_participation": 44,
                "report_text": "44 players. Recap video published so students who missed the final can still watch the games.",
                "submitted_by": users["sarah_leader"],
                "submitted_at": now - timedelta(days=5),
            },
        )

        # Impact Projects
        robotics_project, _ = ImpactProject.objects.update_or_create(
            club=clubs["Robotics club"],
            title="STEM Outreach at Riverside Secondary School",
            defaults={
                "problem_statement": "Local secondary students had zero hands-on exposure to robotics or algorithmic coding before choosing university subject streams.",
                "objective": "Run a termly robotics taster day with low-cost hardware kits for Year 10 and 11 students.",
                "activities_summary": "Mentored 120 students across three weekend workshops, donating 10 micro:bit kits to their computer club.",
                "beneficiaries_description": "120 secondary pupils from low-income school catchments.",
                "estimated_beneficiaries_count": 120,
                "outcomes": "Post-visit survey: 68% reported increased interest in an engineering or computing degree pathway. School formed its first robotics team.",
                "lessons_learned": "Curriculum needs simpler step-by-step visual cheat sheets for absolute beginners.",
                "next_steps": "Formalize as an annual partnership with a dedicated budget line from the institution.",
                "start_date": date(2026, 9, 15),
            },
        )

        eco_project, _ = ImpactProject.objects.update_or_create(
            club=clubs["Alchemists Gardening Club"],
            title="Campus Food Composting Initiative",
            defaults={
                "problem_statement": "Dining halls generated 3.5 tonnes of organic waste monthly, all previously sent straight to landfill.",
                "objective": "Divert 50% of cafeteria kitchen pre-consumer waste into on-campus composting beds.",
                "activities_summary": "Installed four aerated compost tumblers and organized weekly student volunteer collection rotations.",
                "beneficiaries_description": "Campus community and local botanical gardens receiving nutrient-rich compost.",
                "estimated_beneficiaries_count": 450,
                "outcomes": "Diverted 1.8 tonnes of organic waste in first 60 days. Generated 400kg organic compost.",
                "lessons_learned": "Clearly label collection bins to avoid plastic contamination in compost tumblers.",
                "next_steps": "Expand collection bins to student residential quads.",
                "start_date": date(2026, 10, 1),
            },
        )

        # ----------------------------------------------------------------------
        # 5. Events & QR Attendance
        # ----------------------------------------------------------------------
        event1, _ = Event.objects.update_or_create(
            club=clubs["Robotics club"],
            title="Weekly AI Lab & Robot Build Session",
            defaults={
                "description": "Bring your laptops or hardware components. Mentors on-site for machine learning debugging and soldering.",
                "starts_at": now - timedelta(hours=1),
                "ends_at": now + timedelta(hours=3),
                "location": "Innovation Lab Room 204",
                "capacity": 60,
                "check_in_opens_at": now - timedelta(hours=2),
                "check_in_closes_at": now + timedelta(hours=4),
                "created_by": users["sarah_leader"],
            },
        )

        event2, _ = Event.objects.update_or_create(
            club=clubs["Alchemists Gardening Club"],
            title="Sustainability Workshop: Urban Micro-Farming",
            defaults={
                "description": "Learn vertical balcony gardening and rainwater harvesting principles.",
                "starts_at": now + timedelta(days=2),
                "ends_at": now + timedelta(days=2, hours=2),
                "location": "Greenhouse 1A",
                "capacity": 40,
                "check_in_opens_at": now + timedelta(days=2, hours=-1),
                "check_in_closes_at": now + timedelta(days=2, hours=3),
                "created_by": users["sarah_leader"],
            },
        )

        # Attendance record
        AttendanceRecord.objects.get_or_create(
            event=event1,
            user=users["alex_student"],
        )

        # ----------------------------------------------------------------------
        # 6. Evidence Vault & Reviews
        # ----------------------------------------------------------------------
        ev1, _ = Evidence.objects.update_or_create(
            club=clubs["Robotics club"],
            activity=act1,
            caption="ML Bootcamp Attendance Sheet & Feedback Summary",
            defaults={
                "evidence_type": Evidence.EvidenceType.ATTENDANCE_RECORD,
                "status": Evidence.Status.VERIFIED,
                "uploaded_by": users["sarah_leader"],
                "file": "evidence/bootcamp_roster.pdf",
            },
        )
        EvidenceReview.objects.get_or_create(
            evidence=ev1,
            reviewer=users["elena_head"],
            defaults={
                "status": Evidence.Status.VERIFIED,
                "comment": "Roster cross-checked against institutional registration records. Outstanding student engagement.",
            },
        )

        ev2, _ = Evidence.objects.update_or_create(
            club=clubs["Robotics club"],
            activity=act2,
            caption="Rover Competition High-Res Action Photos & Faculty Scoring Matrix",
            defaults={
                "evidence_type": Evidence.EvidenceType.IMAGE,
                "status": Evidence.Status.VERIFIED,
                "uploaded_by": users["sarah_leader"],
                "file": "evidence/rover_race.jpg",
            },
        )
        EvidenceReview.objects.get_or_create(
            evidence=ev2,
            reviewer=users["elena_head"],
            defaults={
                "status": Evidence.Status.VERIFIED,
                "comment": "Complete evidence submitted. Clear proof of faculty collaboration.",
            },
        )

        def publish_watchable(**kwargs):
            caption = kwargs.pop("caption")
            club = kwargs.pop("club")
            Evidence.objects.update_or_create(
                club=club,
                caption=caption,
                defaults={
                    "status": Evidence.Status.VERIFIED,
                    "uploaded_by": users["sarah_leader"],
                    "file": "",
                    **kwargs,
                },
            )

        publish_watchable(
            club=clubs["Robotics club"],
            activity=act1,
            caption="ML Bootcamp highlight reel — watch the workshop",
            evidence_type=Evidence.EvidenceType.VIDEO,
            external_link="https://www.youtube.com/watch?v=aqz-KE-bpKQ",
        )
        publish_watchable(
            club=clubs["Robotics club"],
            activity=act2,
            caption="Line-follower race — onboard camera",
            evidence_type=Evidence.EvidenceType.VIDEO,
            external_link="https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
        )
        publish_watchable(
            club=clubs["Robotics club"],
            impact_project=robotics_project,
            caption="Riverside Secondary STEM day — student film",
            evidence_type=Evidence.EvidenceType.VIDEO,
            external_link="https://www.youtube.com/watch?v=R6MlUcmOul8",
        )
        publish_watchable(
            club=clubs["Alchemists Gardening Club"],
            activity=env_act,
            caption="Tree planting day — field video",
            evidence_type=Evidence.EvidenceType.VIDEO,
            external_link="https://www.youtube.com/watch?v=eRsGyueVLvQ",
        )
        publish_watchable(
            club=clubs["Alchemists Gardening Club"],
            impact_project=eco_project,
            caption="Composting beds in action",
            evidence_type=Evidence.EvidenceType.IMAGE,
            external_link="https://upload.wikimedia.org/wikipedia/commons/thumb/4/4c/Compost.jpg/640px-Compost.jpg",
        )
        publish_watchable(
            club=clubs["The Alchemists' Times"],
            activity=debate_act,
            caption="Open debate night — recorded floor speeches",
            evidence_type=Evidence.EvidenceType.VIDEO,
            external_link="https://www.youtube.com/watch?v=aqz-KE-bpKQ",
        )
        publish_watchable(
            club=clubs["ACF (ALCHE Christian Fellowship) Society"],
            activity=health_act,
            caption="Screening clinic documentary short",
            evidence_type=Evidence.EvidenceType.VIDEO,
            external_link="https://www.youtube.com/watch?v=R6MlUcmOul8",
        )
        publish_watchable(
            club=clubs["Zero to checkmate"],
            activity=chess_act,
            caption="Blitz championship recap",
            evidence_type=Evidence.EvidenceType.VIDEO,
            external_link="https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
        )

        # ----------------------------------------------------------------------
        # 7. Collaborations
        # ----------------------------------------------------------------------
        Collaboration.objects.update_or_create(
            initiating_club=clubs["Robotics club"],
            partner_club=clubs["Alchemists Gardening Club"],
            defaults={
                "description": "Solar-Powered Environmental Drone Sensing: Robotics builds lightweight telemetry drones to monitor canopy health for Environmental Collective.",
                "status": Collaboration.Status.CONFIRMED,
                "confirmed_by": users["sarah_leader"],
                "confirmed_at": now - timedelta(days=10),
            },
        )

        Collaboration.objects.update_or_create(
            initiating_club=clubs["Alchemist Creators"],
            partner_club=clubs["Robotics club"],
            defaults={
                "description": "Documentary on Student Autonomous Robotics: 15-minute documentary tracking student teams building obstacle and rover hardware.",
                "status": Collaboration.Status.PENDING,
            },
        )

        # ----------------------------------------------------------------------
        # 8. Monthly Reporting
        # ----------------------------------------------------------------------
        MonthlyReport.objects.update_or_create(
            club=clubs["Robotics club"],
            period_year=2026,
            period_month=12,
            defaults={
                "status": MonthlyReport.Status.SUBMITTED,
                "deadline": now - timedelta(days=25),
                "summary": "Ran Beginner ML Bootcamp (42 participants) and prepared Autonomous Line-Follower Challenge.",
                "highlights": "Doubled novice coder participation. Secured 2 faculty lab mentors.",
                "challenges": "Component supply chain delays for motor controllers.",
                "submitted_by": users["sarah_leader"],
                "submitted_at": now - timedelta(days=26),
            },
        )

        # ----------------------------------------------------------------------
        # 9. Evaluation Cycle & Configurable Criteria (PRS §9 Table: 100%)
        # ----------------------------------------------------------------------
        cycle, _ = EvaluationCycle.objects.update_or_create(
            name="CCEA Cycle 1 (2026-2027)",
            defaults={
                "evaluation_months": ["2026-09", "2026-10", "2026-11", "2026-12", "2027-01", "2027-02"],
                "reveal_date": date(2027, 3, 20),
                "is_active": True,
                "is_finalized": False,
                "submission_deadline_day_of_month": 5,
                "aggregation_method": "simple_average",
            },
        )

        criteria_specs = [
            ("activity", "Activity & Consistency", "Meaningful activities, plan completion, regular schedule", Decimal("15.00")),
            ("participation", "Student Participation", "Active participation, member involvement, diversity", Decimal("15.00")),
            ("attendance", "Attendance & Engagement", "Verified event attendance and check-in participation rate", Decimal("10.00")),
            ("impact", "Impact & Outcomes", "Beneficiaries reached, measurable community results", Decimal("15.00")),
            ("collaboration", "Collaboration", "Confirmed joint initiatives and cross-club partnerships", Decimal("10.00")),
            ("innovation", "Innovation & Creativity", "New initiatives, original formats, creative problem-solving", Decimal("10.00")),
            ("leadership", "Leadership & Governance", "Planning, communication, accountability, organization", Decimal("10.00")),
            ("documentation", "Documentation & Accountability", "Timely monthly reports, accurate evidence and compliance", Decimal("5.00")),
            ("growth", "Growth & Improvement", "Improvement from previous periods, feedback adoption", Decimal("5.00")),
            ("wellbeing", "Inclusion & Student Well-being", "Inclusive participation, positive activities and student care", Decimal("5.00")),
        ]

        criteria_objs = {}
        for key, label, desc, weight in criteria_specs:
            crit, _ = EvaluationCriterion.objects.update_or_create(
                cycle=cycle,
                key=key,
                defaults={
                    "label": label,
                    "description": desc,
                    "weight_percent": weight,
                    "version": 1,
                    "effective_date": date(2026, 9, 1),
                },
            )
            criteria_objs[key] = crit

        # Scores for Robotics club
        score_configs = [
            ("activity", 92.0, 90.0, "Consistent bi-weekly sessions with documented lesson plans and verified attendance."),
            ("participation", 88.0, 88.0, "High member involvement across 4 engineering departments and humanities."),
            ("attendance", 94.0, 94.0, "64 verified QR check-ins at competition; 42 at bootcamp."),
            ("impact", 90.0, 89.0, "120 secondary students reached in STEM outreach with high positive feedback."),
            ("collaboration", 95.0, 95.0, "Confirmed active partnership with Alchemists Gardening Club on sensing drones."),
            ("innovation", 87.0, 85.0, "Autonomous line-follower track design was original and technically challenging."),
            ("leadership", 90.0, 90.0, "Prompt communication, clear executive minutes, effective handover archiving."),
            ("documentation", 96.0, 96.0, "All reports filed on-time with high-resolution evidence attachments."),
            ("growth", 85.0, 85.0, "Active membership grew 35% compared to previous academic term."),
            ("wellbeing", 90.0, 90.0, "Safe workshop environment, positive student feedback, peer tutoring available."),
        ]

        for key, ai_val, final_val, note in score_configs:
            crit = criteria_objs[key]
            score_obj, _ = Score.objects.update_or_create(
                club=clubs["Robotics club"],
                cycle=cycle,
                criterion=crit,
                period_year=2026,
                period_month=12,
                defaults={
                    "ai_recommended_value": Decimal(str(ai_val)),
                    "final_value": Decimal(str(final_val)),
                    "stage": Score.Stage.FINAL,
                },
            )
            AIRecommendation.objects.get_or_create(
                score=score_obj,
                defaults={
                    "recommended_value": Decimal(str(ai_val)),
                    "explanation": f"Based on verified activities and attendance records: {note}",
                    "flags": [],
                    "provider": "anthropic",
                    "model_name": "claude-sonnet-4-6",
                },
            )
            ScoreAdjustment.objects.get_or_create(
                score=score_obj,
                reason="Reviewed and validated by Committee Member Vance against verified evidence.",
                defaults={
                    "previous_value": Decimal(str(ai_val)),
                    "new_value": Decimal(str(final_val)),
                    "adjusted_by": users["elena_head"],
                },
            )

        # ----------------------------------------------------------------------
        # 10. Awards & Hall of Excellence
        # ----------------------------------------------------------------------
        award_cats = [
            ("Club of the Year", "Recognizes overall institutional excellence, governance, impact, and high participation."),
            ("Most Innovative Club", "Exemplary novelty, technical advancement, or creative formats in club programming."),
            ("Best Collaboration", "Outstanding joint initiative and spirit of cross-club partnership."),
            ("Best Community Impact", "Highest verifiable positive impact on external or campus communities."),
            ("Most Active Club", "Highest cadence of consistent, well-attended student activities."),
            ("Student Well-being Champion", "Outstanding commitment to student support, mental health, and inclusive community."),
        ]

        created_awards = {}
        for title, desc in award_cats:
            aw, _ = Award.objects.update_or_create(
                cycle=cycle,
                category_name=title,
                defaults={
                    "description": desc,
                    "winner_club": clubs["Robotics club"] if title == "Most Innovative Club" else (
                        clubs["Alchemists Gardening Club"] if title == "Best Community Impact" else
                        clubs["Zero to checkmate"] if title == "Most Active Club" else
                        clubs["Young African Luminaries at ALCHE"] if title == "Student Well-being Champion" else
                        clubs["ALCHEPELLA"] if title == "Best Collaboration" else
                        clubs["Robotics club"] if title == "Club of the Year" else None
                    ),
                    "is_revealed": False,
                },
            )
            created_awards[title] = aw

        HallOfExcellenceEntry.objects.all().delete()
        hall_history = [
            ("2023", "Club of the Year", "Karma Football Club",
             "For building a campus football culture that drew students from every faculty into weekly play."),
            ("2023", "Best Community Impact", "Rwandan Students Society",
             "For cultural programming that welcomed new students and kept Rwandan heritage visible on campus."),
            ("2023", "Most Active Club", "Muslims@ALCHE",
             "For a steady calendar of fellowship, study circles, and open campus gatherings."),
            ("2024", "Club of the Year", "The Alchemists' Times",
             "For documenting campus life with a newspaper that every society could recognise itself in."),
            ("2024", "Most Innovative Club", "ALCHE BlockChain Club",
             "For student-led learning sessions that made emerging technology usable for non-specialists."),
            ("2024", "Best Collaboration", "ALCHEPELLA",
             "For joint performances with other arts societies that filled campus halls."),
            ("2024", "Best Community Impact", "Alchemists Gardening Club",
             "For turning unused ground into a shared garden and teaching composting on campus."),
            ("2025", "Club of the Year", "Robotics club",
             "For open workshops, a published campus film record, and technical excellence recognised across ALCHE."),
            ("2025", "Best Community Impact", "ACF (ALCHE Christian Fellowship) Society",
             "For consistent fellowship, welcome, and service as a recognised ALCHE society."),
            ("2025", "Most Active Club", "Zero to checkmate",
             "For a chess programme that kept tables full throughout the academic year."),
            ("2025", "Student Well-being Champion", "Young African Luminaries at ALCHE",
             "For leadership programming that connected students across years after the society’s renewal from the Pan African Society."),
        ]
        for year, category, club_name, citation in hall_history:
            hist_cycle, _ = EvaluationCycle.objects.update_or_create(
                name=f"CCEA {year}",
                defaults={
                    "evaluation_months": [f"{year}-03", f"{year}-08"],
                    "reveal_date": date(int(year), 6, 1),
                    "is_active": False,
                    "is_finalized": True,
                    "submission_deadline_day_of_month": 5,
                    "aggregation_method": "simple_average",
                },
            )
            desc = next(d for n, d in award_cats if n == category)
            award, _ = Award.objects.update_or_create(
                cycle=hist_cycle,
                category_name=category,
                defaults={
                    "description": desc,
                    "winner_club": clubs[club_name],
                    "is_revealed": True,
                },
            )
            HallOfExcellenceEntry.objects.update_or_create(
                academic_year=year,
                club=clubs[club_name],
                award=award,
                defaults={"citation": citation},
            )

        # ----------------------------------------------------------------------
        # 11. Club Health Snapshots (PRS §16 Early Intervention)
        # ----------------------------------------------------------------------
        today = date.today()
        health_configs = [
            ("Robotics club", ClubHealthSnapshot.Status.HEALTHY, {"days_since_last_activity": 5, "report_completion_rate": 1.0, "attendance_trend": 0.22, "evidence_completeness": 0.95}),
            ("Alchemists Gardening Club", ClubHealthSnapshot.Status.HEALTHY, {"days_since_last_activity": 12, "report_completion_rate": 1.0, "attendance_trend": 0.15, "evidence_completeness": 0.90}),
            ("The Alchemists' Times", ClubHealthSnapshot.Status.NEEDS_ATTENTION, {"days_since_last_activity": 34, "report_completion_rate": 0.67, "attendance_trend": -0.05, "evidence_completeness": 0.72}),
            ("Alchemist Creators", ClubHealthSnapshot.Status.NEEDS_ATTENTION, {"days_since_last_activity": 28, "report_completion_rate": 0.50, "attendance_trend": 0.00, "evidence_completeness": 0.60}),
            ("ACF (ALCHE Christian Fellowship) Society", ClubHealthSnapshot.Status.AT_RISK, {"days_since_last_activity": 71, "report_completion_rate": 0.33, "attendance_trend": -0.35, "evidence_completeness": 0.40}),
            ("Zero to checkmate", ClubHealthSnapshot.Status.HEALTHY, {"days_since_last_activity": 3, "report_completion_rate": 1.0, "attendance_trend": 0.10, "evidence_completeness": 0.85}),
        ]

        for club_name, status_val, ind in health_configs:
            ClubHealthSnapshot.objects.update_or_create(
                club=clubs[club_name],
                computed_for_date=today,
                defaults={"status": status_val, "indicators": ind},
            )

        # ----------------------------------------------------------------------
        # 12. Notifications & Audit Logs
        # ----------------------------------------------------------------------
        Notification.objects.get_or_create(
            recipient=users["alex_student"],
            title="Attendance Confirmed",
            defaults={
                "category": Notification.Category.VERIFICATION,
                "body": "Your QR check-in for 'Weekly AI Lab & Robot Build Session' has been verified.",
                "is_read": False,
            },
        )
        Notification.objects.get_or_create(
            recipient=users["sarah_leader"],
            title="Evidence Review Completed",
            defaults={
                "category": Notification.Category.VERIFICATION,
                "body": "Marcus Vance verified your submission for Beginner Machine Learning Bootcamp.",
                "is_read": False,
            },
        )

        AuditLog.objects.create(
            actor=users["elena_head"],
            action="criteria.configured",
            target_model="EvaluationCycle",
            target_id=str(cycle.id),
            reason="Configured 10 criteria summing to 100% for CCEA Cycle 1.",
            metadata={"cycle_name": cycle.name, "total_weight": 100},
        )

        self.stdout.write(self.style.SUCCESS("All institutional demo data seeded successfully!"))
