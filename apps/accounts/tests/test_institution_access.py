import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Institution, User
from apps.clubs.models import Club, ClubMembership
from apps.core.tests.factories import ClubFactory, InstitutionFactory, UserFactory
from apps.evaluation.monthly import evaluate_club_month

pytestmark = pytest.mark.django_db


def test_register_rejects_unlicensed_email():
    Institution.objects.create(
        name="African Leadership College of Higher Education",
        short_name="ALCHE",
        slug="alche",
        allowed_email_domains=["alustudent.com", "alueducation.com"],
        student_email_domains=["alustudent.com"],
        staff_email_domains=["alueducation.com"],
        is_active=True,
    )
    client = APIClient()
    res = client.post(
        "/api/auth/register/",
        {
            "first_name": "Ada",
            "last_name": "Okeke",
            "email": "ada@gmail.com",
            "password": "StrongPass123!",
            "student_id": "STU-1",
        },
        format="json",
    )
    assert res.status_code == 400


def test_register_accepts_alche_email_and_assigns_institution():
    Institution.objects.create(
        name="African Leadership College of Higher Education",
        short_name="ALCHE",
        slug="alche",
        allowed_email_domains=["alustudent.com", "alueducation.com"],
        student_email_domains=["alustudent.com"],
        staff_email_domains=["alueducation.com"],
        is_active=True,
    )
    client = APIClient()
    res = client.post(
        "/api/auth/register/",
        {
            "first_name": "Ada",
            "last_name": "Okeke",
            "email": "ada.okeke@alustudent.com",
            "password": "StrongPass123!",
            "student_id": "STU-1",
        },
        format="json",
    )
    assert res.status_code == 201
    assert res.data["user"]["role"] == "student"
    assert res.data["user"]["institution"]["slug"] == "alche"
    assert res.data["access"]


def test_staff_email_registers_as_staff_not_student():
    Institution.objects.create(
        name="African Leadership College of Higher Education",
        short_name="ALCHE",
        slug="alche",
        allowed_email_domains=["alustudent.com", "alueducation.com"],
        student_email_domains=["alustudent.com"],
        staff_email_domains=["alueducation.com"],
        is_active=True,
    )
    client = APIClient()
    res = client.post(
        "/api/auth/register/",
        {
            "first_name": "Nia",
            "last_name": "Mwangi",
            "email": "nia.mwangi@alueducation.com",
            "password": "StrongPass123!",
            "student_id": "STF-1",
        },
        format="json",
    )
    assert res.status_code == 201
    assert res.data["user"]["role"] == "staff"


def test_student_cannot_see_other_institution_clubs():
    alche = InstitutionFactory(slug="alche", short_name="ALCHE", allowed_email_domains=["alche.ac.mu"])
    other = InstitutionFactory(slug="riverside", short_name="RHS")
    ClubFactory(institution=alche, name="ALCHE Debate", slug="alche-debate")
    ClubFactory(institution=other, name="Riverside Debate", slug="riverside-debate")
    student = UserFactory(role=User.Role.STUDENT, institution=alche, email="ada@alustudent.com")
    client = APIClient()
    client.force_authenticate(student)
    res = client.get("/api/clubs/")
    names = [row["name"] for row in res.data["results"]]
    assert "ALCHE Debate" in names
    assert "Riverside Debate" not in names


def test_join_request_and_leader_approval():
    club = ClubFactory()
    student = UserFactory(institution=club.institution)
    leader = UserFactory(role=User.Role.CLUB_LEADER, institution=club.institution)
    head = UserFactory(role=User.Role.COMMITTEE_HEAD, institution=club.institution)
    ClubMembership.objects.create(
        club=club,
        user=leader,
        role=ClubMembership.MembershipRole.LEADER,
        status=ClubMembership.Status.APPROVED,
        is_active=True,
    )
    client = APIClient()
    client.force_authenticate(head)
    client.patch("/api/membership-census/window/", {"open": True}, format="json")
    client.force_authenticate(student)
    res = client.post("/api/club-memberships/", {"club": str(club.id)}, format="json")
    assert res.status_code == 201
    assert res.data["status"] == "requested"
    membership_id = res.data["id"]

    client.force_authenticate(leader)
    res = client.post(f"/api/club-memberships/{membership_id}/approve/", format="json")
    assert res.status_code == 200
    assert res.data["status"] == "approved"


def test_monthly_evaluation_flags_missing_report():
    club = ClubFactory()
    result = evaluate_club_month(club, 2026, 9)
    codes = {item["code"] for item in result["lackings"]}
    assert "missing_report" in codes
    assert result["band"] in ("at_risk", "needs_attention")


def test_copilot_tells_student_they_cannot_submit_reports():
    inst = InstitutionFactory(slug="alche", short_name="ALCHE", allowed_email_domains=["alche.ac.mu"])
    student = UserFactory(role=User.Role.STUDENT, institution=inst)
    client = APIClient()
    client.force_authenticate(student)
    res = client.post("/api/copilot/chat/", {"message": "How do I submit a monthly report?"}, format="json")
    assert res.status_code == 200
    assert "Club Leader" in res.data["reply"]
    assert res.data["engine"] == "clubconnect-copilot-v2"


def test_copilot_health_scan_is_for_committee_not_students():
    inst = InstitutionFactory()
    ClubFactory(institution=inst)
    student = UserFactory(role=User.Role.STUDENT, institution=inst)
    head = UserFactory(role=User.Role.COMMITTEE_HEAD, institution=inst)
    client = APIClient()
    client.force_authenticate(student)
    assert client.get("/api/copilot/health-scan/").status_code == 403
    client.force_authenticate(head)
    res = client.get("/api/copilot/health-scan/")
    assert res.status_code == 200
    assert res.data["engine"] == "clubconnect-copilot-v1"
    assert "health_roster" in res.data
    staff = UserFactory(role=User.Role.STAFF, institution=inst)
    client.force_authenticate(staff)
    staff_res = client.get("/api/copilot/health-scan/")
    assert staff_res.status_code == 403


def test_staff_gets_campus_analytics_students_do_not():
    inst = InstitutionFactory()
    ClubFactory(institution=inst, status=Club.Status.RECOGNIZED)
    student = UserFactory(role=User.Role.STUDENT, institution=inst)
    staff = UserFactory(role=User.Role.STAFF, institution=inst)
    client = APIClient()
    client.force_authenticate(student)
    assert client.get("/api/campus-analytics/").status_code == 403
    client.force_authenticate(staff)
    res = client.get("/api/campus-analytics/")
    assert res.status_code == 200
    assert "total_active_clubs" in res.data
    assert "category_distribution" in res.data
    assert res.data["institution"] == inst.short_name


def test_staff_broadcast_notice_creates_recipient_notifications():
    inst = InstitutionFactory()
    staff = UserFactory(role=User.Role.STAFF, institution=inst)
    other_staff = UserFactory(role=User.Role.STAFF, institution=inst)
    student = UserFactory(role=User.Role.STUDENT, institution=inst)
    outsider = UserFactory(role=User.Role.STUDENT)
    client = APIClient()
    client.force_authenticate(student)
    denied = client.post(
        "/api/notices/broadcast/",
        {"subject": "Hello", "message": "Campus note", "audience": "all_clubs"},
        format="json",
    )
    assert denied.status_code == 403
    client.force_authenticate(staff)
    res = client.post(
        "/api/notices/broadcast/",
        {"subject": "Evidence deadline", "message": "Upload reports by Friday.", "audience": "all_clubs"},
        format="json",
    )
    assert res.status_code == 201
    assert res.data["sent"] >= 2
    client.force_authenticate(student)
    inbox = client.get("/api/notifications/")
    assert inbox.status_code == 200
    titles = [row["title"] for row in (inbox.data.get("results") if isinstance(inbox.data, dict) else inbox.data)]
    assert "Evidence deadline" in titles
    client.force_authenticate(outsider)
    other_inbox = client.get("/api/notifications/")
    other_rows = other_inbox.data.get("results") if isinstance(other_inbox.data, dict) else other_inbox.data
    other_titles = [row["title"] for row in other_rows]
    assert "Evidence deadline" not in other_titles
    client.force_authenticate(other_staff)
    peer = client.get("/api/notifications/")
    peer_rows = peer.data.get("results") if isinstance(peer.data, dict) else peer.data
    peer_titles = [row["title"] for row in peer_rows]
    assert "Evidence deadline" in peer_titles


def test_unlicensed_campus_can_request_a_licence():
    operator = UserFactory(role=User.Role.SYSTEM_ADMIN, email="admin@alche.ac.mu", institution=None)
    client = APIClient()
    res = client.post(
        "/api/licence-inquiries/",
        {
            "institution_name": "Riverside College",
            "country": "Mauritius",
            "kind": "university",
            "contact_name": "Priya Shah",
            "contact_role": "Dean of Students",
            "contact_email": "priya.shah@riverside.ac.mu",
            "student_email_domain": "student.riverside.ac.mu",
            "staff_email_domain": "riverside.ac.mu",
            "message": "We would like ClubConnect for our clubs.",
        },
        format="json",
    )
    assert res.status_code == 201
    from apps.accounts.models import LicenceInquiry
    from apps.notifications.models import Notification

    inquiry = LicenceInquiry.objects.get(contact_email="priya.shah@riverside.ac.mu")
    assert inquiry.institution_name == "Riverside College"
    titles = list(Notification.objects.filter(recipient=operator).values_list("title", flat=True))
    assert any("Riverside College" in t for t in titles)

    again = client.post(
        "/api/licence-inquiries/",
        {
            "institution_name": "Riverside College",
            "contact_name": "Priya Shah",
            "contact_email": "priya.shah@riverside.ac.mu",
        },
        format="json",
    )
    assert again.status_code == 200
    assert again.data["duplicate"] is True
    assert LicenceInquiry.objects.filter(contact_email="priya.shah@riverside.ac.mu").count() == 1

    student = UserFactory(role=User.Role.STUDENT)
    client.force_authenticate(student)
    assert client.get("/api/admin/licence-inquiries/").status_code == 403
    client.force_authenticate(operator)
    inbox = client.get("/api/admin/licence-inquiries/")
    assert inbox.status_code == 200
    assert inbox.data[0]["contact_email"] == "priya.shah@riverside.ac.mu"


def test_help_center_accepts_a_ticket():
    inst = InstitutionFactory()
    student = UserFactory(role=User.Role.STUDENT, institution=inst, first_name="Ada")
    staff = UserFactory(role=User.Role.STAFF, institution=inst)
    client = APIClient()
    guest = client.post(
        "/api/help/tickets/",
        {
            "name": "Maya Nkosi",
            "email": "maya@example.com",
            "category": "technical",
            "subject": "The sun covers my menu",
            "body": "On a small screen the profile menu sits under the sun disc.",
            "language": "en",
        },
        format="json",
    )
    assert guest.status_code == 201
    client.force_authenticate(student)
    mine = client.post(
        "/api/help/tickets/",
        {
            "category": "clubs",
            "subject": "Join request stuck",
            "body": "I requested Robotics yesterday and still see pending.",
            "language": "rw",
        },
        format="json",
    )
    assert mine.status_code == 201
    listed = client.get("/api/help/tickets/")
    assert listed.status_code == 200
    assert any(row["subject"] == "Join request stuck" for row in listed.data)
    client.force_authenticate(staff)
    inbox = client.get("/api/admin/help-tickets/")
    assert inbox.status_code == 200
    subjects = [row["subject"] for row in inbox.data]
    assert "Join request stuck" in subjects


def test_campus_system_admin_is_tenant_admin_not_licence_desk():
    alche = InstitutionFactory(
        slug="alche-admin",
        student_email_domains=["student.alche-admin.edu"],
        staff_email_domains=["alche-admin.edu"],
    )
    other = InstitutionFactory()
    admin = UserFactory(role=User.Role.SYSTEM_ADMIN, institution=alche, email="it@alche-admin.edu")
    student = UserFactory(role=User.Role.STUDENT, institution=alche, email="ada@student.alche-admin.edu")
    outsider = UserFactory(role=User.Role.STUDENT, institution=other)
    client = APIClient()
    client.force_authenticate(admin)
    assert client.get("/api/admin/licence-inquiries/").status_code == 403
    directory = client.get("/api/campus-users/")
    assert directory.status_code == 200
    emails = {row["email"] for row in directory.data}
    assert student.email in emails
    assert outsider.email not in emails
    res = client.patch(f"/api/campus-users/{student.id}/", {"role": "club_leader"}, format="json")
    assert res.status_code == 200
    student.refresh_from_db()
    assert student.role == User.Role.CLUB_LEADER
    settings = client.get("/api/campus-institution/")
    assert settings.status_code == 200
    assert settings.data["slug"] == "alche-admin"
    patched = client.patch(
        "/api/campus-institution/",
        {"awards_program_name": "Campus Clubs Excellence Awards"},
        format="json",
    )
    assert patched.status_code == 200
    client.force_authenticate(student)
    assert client.get("/api/campus-users/").status_code == 403

