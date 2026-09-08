from datetime import date, datetime, timedelta
from decimal import Decimal
from django.utils.text import slugify

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.activities.models import Activity
from apps.attendance.models import AttendanceRecord
from apps.audit.models import AuditLog
from apps.awards.models import Award, HallOfExcellenceEntry
from apps.clubs.models import Club, ClubMembership, ClubHealthSnapshot, LeadershipTerm
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

    def handle(self, *args, **options):
        self.stdout.write("Starting institutional data seeding...")

        # ----------------------------------------------------------------------
        # 1. Users for all 6 Roles
        # ----------------------------------------------------------------------
        password = "Pass1234!"
        
        users_data = [
            {
                "username": "alex_student",
                "email": "alex.student@campus.edu",
                "first_name": "Alex",
                "last_name": "Mercer",
                "role": User.Role.STUDENT,
                "student_id": "STU-2026-0812",
                "phone_number": "+1-555-0192",
            },
            {
                "username": "sarah_leader",
                "email": "sarah.leader@campus.edu",
                "first_name": "Sarah",
                "last_name": "Chen",
                "role": User.Role.CLUB_LEADER,
                "student_id": "STU-2024-0194",
                "phone_number": "+1-555-0144",
            },
            {
                "username": "marcus_member",
                "email": "marcus.member@campus.edu",
                "first_name": "Marcus",
                "last_name": "Vance",
                "role": User.Role.COMMITTEE_MEMBER,
                "student_id": "FAC-2021-0032",
                "phone_number": "+1-555-0155",
            },
            {
                "username": "elena_head",
                "email": "dr.elena.head@campus.edu",
                "first_name": "Dr. Elena",
                "last_name": "Rostova",
                "role": User.Role.COMMITTEE_HEAD,
                "student_id": "ADM-2018-0001",
                "phone_number": "+1-555-0100",
                "is_staff": True,
            },
            {
                "username": "dean_harrison",
                "email": "dean.harrison@campus.edu",
                "first_name": "Arthur",
                "last_name": "Harrison",
                "role": User.Role.DEAN_ADMIN,
                "student_id": "DEAN-2015-0010",
                "phone_number": "+1-555-0111",
                "is_staff": True,
            },
            {
                "username": "admin_root",
                "email": "admin@campus.edu",
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
            user.role = u_info["role"]
            user.email = u_info["email"]
            user.first_name = u_info["first_name"]
            user.last_name = u_info["last_name"]
            user.save()
            users[u_info["username"]] = user

        self.stdout.write(self.style.SUCCESS(f"Seeded {len(users)} users across all 6 roles."))

        # ----------------------------------------------------------------------
        # 2. Clubs (Digital Passports)
        # ----------------------------------------------------------------------
        clubs_data = [
            {
                "name": "Robotics & AI Society",
                "slug": "robotics-and-ai-society",
                "category": "Technology",
                "status": Club.Status.RECOGNIZED,
                "established_date": date(2022, 3, 14),
                "description": "Builds autonomous robots and runs weekly workshops on machine learning for beginners across every faculty.",
                "mission": "To make robotics and applied machine learning genuinely accessible to every student, regardless of prior coding experience.",
                "vision": "A campus where any student can turn an engineering or computational idea into a working prototype.",
                "objectives": "1. Run termly beginner ML bootcamps. 2. Field competitive teams in national autonomous robotics contests. 3. Partner with secondary schools on STEM outreach.",
                "public_contact_email": "robotics@campus.edu",
            },
            {
                "name": "Environmental Action Collective",
                "slug": "environmental-action-collective",
                "category": "Sustainability",
                "status": Club.Status.RECOGNIZED,
                "established_date": date(2019, 9, 2),
                "description": "Runs campus composting, native tree-planting drives, and a termly sustainability audit published to the whole institution.",
                "mission": "Drive campus sustainability through student-led action, ecological stewardship, and transparent institutional reporting.",
                "vision": "A zero-waste, carbon-conscious institution setting the benchmark for sustainable universities.",
                "objectives": "1. Divert 2+ tonnes of organic waste per term. 2. Restore native flora on campus boundaries. 3. Publish biannual carbon audit.",
                "public_contact_email": "ecoclub@campus.edu",
            },
            {
                "name": "Debate & Rhetoric Union",
                "slug": "debate-and-rhetoric-union",
                "category": "Academic",
                "status": Club.Status.RECOGNIZED,
                "established_date": date(2015, 1, 20),
                "description": "Competitive debate training, public speaking clinics, and the institution's delegation to the national inter-varsity circuit.",
                "mission": "Cultivate rigorous analytical thought, articulate advocacy, and respectful discourse across contentious public issues.",
                "vision": "Inspire the next generation of civic and intellectual leaders.",
                "objectives": "1. Compete in 4 national tournaments. 2. Host campus open debate nights. 3. Train novice speakers in British Parliamentary style.",
                "public_contact_email": "debate@campus.edu",
            },
            {
                "name": "Filmmakers Guild",
                "slug": "filmmakers-guild",
                "category": "Arts & Culture",
                "status": Club.Status.PENDING,
                "established_date": date(2026, 6, 1),
                "description": "A newly forming collective for student filmmakers — short films, a termly screening night, and equipment-sharing.",
                "mission": "Provide hands-on cinema production opportunities, camera gear access, and an artistic community for all aspiring filmmakers.",
                "vision": "Establish an annual student cinema festival showcasing campus voices.",
                "objectives": "1. Produce 6 original student short films. 2. Establish a pooled equipment gear-cage. 3. Host monthly critique screenings.",
                "public_contact_email": "film@campus.edu",
            },
            {
                "name": "Community Health Outreach",
                "slug": "community-health-outreach",
                "category": "Community Service",
                "status": Club.Status.RECOGNIZED,
                "established_date": date(2017, 5, 11),
                "description": "Free health-literacy workshops in surrounding communities, run in partnership with the Faculty of Medicine.",
                "mission": "Bridge health information gaps in underserved urban neighborhoods through evidence-based student volunteering.",
                "vision": "Equitable access to preventative health education for every surrounding community.",
                "objectives": "1. Conduct 10 free preventative screening clinics. 2. Distribute 1,000 health literacy guides in 3 languages.",
                "public_contact_email": "health.outreach@campus.edu",
            },
            {
                "name": "Chess & Strategy Circle",
                "slug": "chess-and-strategy-circle",
                "category": "Recreation",
                "status": Club.Status.RECOGNIZED,
                "established_date": date(2020, 11, 30),
                "description": "Weekly ladder tournaments, beginner coaching, and an annual campus-wide blitz championship.",
                "mission": "Foster strategic thinking, patience, and inclusive social connection through competitive and casual chess.",
                "vision": "A welcoming intellectual recreational space accessible to any skill level.",
                "objectives": "1. Run weekly Wednesday open blitz sessions. 2. Crown the annual Campus Grandmaster. 3. Provide free coaching to beginners.",
                "public_contact_email": "chess@campus.edu",
            },
        ]

        clubs = {}
        for c_info in clubs_data:
            club, _ = Club.objects.update_or_create(
                slug=c_info["slug"],
                defaults=c_info,
            )
            clubs[club.name] = club

        # Assign Committee Member Marcus to Robotics and Environmental
        users["marcus_member"].assigned_clubs.set([clubs["Robotics & AI Society"], clubs["Environmental Action Collective"]])

        # ----------------------------------------------------------------------
        # 3. Memberships & Leadership
        # ----------------------------------------------------------------------
        # Sarah Chen is leader of Robotics
        ClubMembership.objects.update_or_create(
            club=clubs["Robotics & AI Society"],
            user=users["sarah_leader"],
            defaults={
                "role": ClubMembership.MembershipRole.LEADER,
                "status": ClubMembership.Status.APPROVED,
                "joined_at": date(2024, 9, 1),
            },
        )
        LeadershipTerm.objects.get_or_create(
            club=clubs["Robotics & AI Society"],
            user=users["sarah_leader"],
            academic_year="2026-2027",
            defaults={
                "position_title": "President & Technical Director",
                "start_date": date(2026, 9, 1),
                "achievements_summary": "Expanded ML bootcamps and secured faculty grant.",
            },
        )

        # Alex Mercer memberships
        ClubMembership.objects.update_or_create(
            club=clubs["Robotics & AI Society"],
            user=users["alex_student"],
            defaults={"role": ClubMembership.MembershipRole.MEMBER, "status": ClubMembership.Status.APPROVED},
        )
        ClubMembership.objects.update_or_create(
            club=clubs["Environmental Action Collective"],
            user=users["alex_student"],
            defaults={"role": ClubMembership.MembershipRole.MEMBER, "status": ClubMembership.Status.APPROVED},
        )
        ClubMembership.objects.update_or_create(
            club=clubs["Filmmakers Guild"],
            user=users["alex_student"],
            defaults={"role": ClubMembership.MembershipRole.MEMBER, "status": ClubMembership.Status.REQUESTED},
        )

        self.stdout.write(self.style.SUCCESS(f"Seeded {len(clubs)} clubs with memberships and leadership."))

        # ----------------------------------------------------------------------
        # 4. Activities & Impact Projects
        # ----------------------------------------------------------------------
        now = timezone.now()
        act1, _ = Activity.objects.update_or_create(
            club=clubs["Robotics & AI Society"],
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
            club=clubs["Robotics & AI Society"],
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
            club=clubs["Robotics & AI Society"],
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

        # Environmental activities
        Activity.objects.update_or_create(
            club=clubs["Environmental Action Collective"],
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

        # Impact Projects
        ImpactProject.objects.update_or_create(
            club=clubs["Robotics & AI Society"],
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

        ImpactProject.objects.update_or_create(
            club=clubs["Environmental Action Collective"],
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
            club=clubs["Robotics & AI Society"],
            title="Weekly AI Lab & Robot Build Session",
            defaults={
                "description": "Bring your laptops or hardware components. Mentors on-site for machine learning debugging and soldering.",
                "starts_at": now - timedelta(hours=1),
                "ends_at": now + timedelta(hours=3),
                "location": "Innovation Lab Room 204",
                "capacity": 60,
                "qr_token": "QR-ROBOTICS-2026-ACTIVE",
                "check_in_opens_at": now - timedelta(hours=2),
                "check_in_closes_at": now + timedelta(hours=4),
                "created_by": users["sarah_leader"],
            },
        )

        event2, _ = Event.objects.update_or_create(
            club=clubs["Environmental Action Collective"],
            title="Sustainability Workshop: Urban Micro-Farming",
            defaults={
                "description": "Learn vertical balcony gardening and rainwater harvesting principles.",
                "starts_at": now + timedelta(days=2),
                "ends_at": now + timedelta(days=2, hours=2),
                "location": "Greenhouse 1A",
                "capacity": 40,
                "qr_token": "QR-ENV-2026-FARM",
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
            club=clubs["Robotics & AI Society"],
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
            reviewer=users["marcus_member"],
            defaults={
                "status": Evidence.Status.VERIFIED,
                "comment": "Roster cross-checked against institutional registration records. Outstanding student engagement.",
            },
        )

        ev2, _ = Evidence.objects.update_or_create(
            club=clubs["Robotics & AI Society"],
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
            reviewer=users["marcus_member"],
            defaults={
                "status": Evidence.Status.VERIFIED,
                "comment": "Complete evidence submitted. Clear proof of faculty collaboration.",
            },
        )

        # ----------------------------------------------------------------------
        # 7. Collaborations
        # ----------------------------------------------------------------------
        Collaboration.objects.update_or_create(
            initiating_club=clubs["Robotics & AI Society"],
            partner_club=clubs["Environmental Action Collective"],
            defaults={
                "description": "Solar-Powered Environmental Drone Sensing: Robotics builds lightweight telemetry drones to monitor canopy health for Environmental Collective.",
                "status": Collaboration.Status.CONFIRMED,
                "confirmed_by": users["sarah_leader"],
                "confirmed_at": now - timedelta(days=10),
            },
        )

        Collaboration.objects.update_or_create(
            initiating_club=clubs["Filmmakers Guild"],
            partner_club=clubs["Robotics & AI Society"],
            defaults={
                "description": "Documentary on Student Autonomous Robotics: 15-minute documentary tracking student teams building obstacle and rover hardware.",
                "status": Collaboration.Status.PENDING,
            },
        )

        # ----------------------------------------------------------------------
        # 8. Monthly Reporting
        # ----------------------------------------------------------------------
        MonthlyReport.objects.update_or_create(
            club=clubs["Robotics & AI Society"],
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
                "evaluation_months": ["2026-12", "2027-01", "2027-02"],
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

        # Scores for Robotics & AI Society
        score_configs = [
            ("activity", 92.0, 90.0, "Consistent bi-weekly sessions with documented lesson plans and verified attendance."),
            ("participation", 88.0, 88.0, "High member involvement across 4 engineering departments and humanities."),
            ("attendance", 94.0, 94.0, "64 verified QR check-ins at competition; 42 at bootcamp."),
            ("impact", 90.0, 89.0, "120 secondary students reached in STEM outreach with high positive feedback."),
            ("collaboration", 95.0, 95.0, "Confirmed active partnership with Environmental Action Collective on sensing drones."),
            ("innovation", 87.0, 85.0, "Autonomous line-follower track design was original and technically challenging."),
            ("leadership", 90.0, 90.0, "Prompt communication, clear executive minutes, effective handover archiving."),
            ("documentation", 96.0, 96.0, "All reports filed on-time with high-resolution evidence attachments."),
            ("growth", 85.0, 85.0, "Active membership grew 35% compared to previous academic term."),
            ("wellbeing", 90.0, 90.0, "Safe workshop environment, positive student feedback, peer tutoring available."),
        ]

        for key, ai_val, final_val, note in score_configs:
            crit = criteria_objs[key]
            score_obj, _ = Score.objects.update_or_create(
                club=clubs["Robotics & AI Society"],
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
                    "adjusted_by": users["marcus_member"],
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
                    "winner_club": clubs["Robotics & AI Society"] if title == "Most Innovative Club" else None,
                    "is_revealed": title == "Most Innovative Club",
                },
            )
            created_awards[title] = aw

        HallOfExcellenceEntry.objects.update_or_create(
            academic_year="2025-2026",
            club=clubs["Robotics & AI Society"],
            award=created_awards["Club of the Year"],
            defaults={
                "citation": "For pioneering campus-wide open workshops in artificial intelligence and winning first place at the National Autonomous Rover Games.",
            },
        )
        HallOfExcellenceEntry.objects.update_or_create(
            academic_year="2025-2026",
            club=clubs["Community Health Outreach"],
            award=created_awards["Best Community Impact"],
            defaults={
                "citation": "Screened over 1,200 local residents for preventable cardiovascular conditions in under-served community centers.",
            },
        )

        # ----------------------------------------------------------------------
        # 11. Club Health Snapshots (PRS §16 Early Intervention)
        # ----------------------------------------------------------------------
        today = date.today()
        health_configs = [
            ("Robotics & AI Society", ClubHealthSnapshot.Status.HEALTHY, {"days_since_last_activity": 5, "report_completion_rate": 1.0, "attendance_trend": 0.22, "evidence_completeness": 0.95}),
            ("Environmental Action Collective", ClubHealthSnapshot.Status.HEALTHY, {"days_since_last_activity": 12, "report_completion_rate": 1.0, "attendance_trend": 0.15, "evidence_completeness": 0.90}),
            ("Debate & Rhetoric Union", ClubHealthSnapshot.Status.NEEDS_ATTENTION, {"days_since_last_activity": 34, "report_completion_rate": 0.67, "attendance_trend": -0.05, "evidence_completeness": 0.72}),
            ("Filmmakers Guild", ClubHealthSnapshot.Status.NEEDS_ATTENTION, {"days_since_last_activity": 28, "report_completion_rate": 0.50, "attendance_trend": 0.00, "evidence_completeness": 0.60}),
            ("Community Health Outreach", ClubHealthSnapshot.Status.AT_RISK, {"days_since_last_activity": 71, "report_completion_rate": 0.33, "attendance_trend": -0.35, "evidence_completeness": 0.40}),
            ("Chess & Strategy Circle", ClubHealthSnapshot.Status.HEALTHY, {"days_since_last_activity": 3, "report_completion_rate": 1.0, "attendance_trend": 0.10, "evidence_completeness": 0.85}),
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
