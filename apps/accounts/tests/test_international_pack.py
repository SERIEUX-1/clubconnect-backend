import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.clubs.models import ClubMembership, LeadershipHandover, LeadershipTerm
from apps.core.tests.factories import ClubFactory, ClubLeaderFactory, InstitutionFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_academic_year_follows_campus_start_month():
    inst = InstitutionFactory(academic_year_start_month=8, academic_year_label="")
    from datetime import date

    assert inst.current_academic_year(today=date(2026, 9, 1)) == "2026-2027"
    assert inst.current_academic_year(today=date(2026, 7, 1)) == "2025-2026"
    inst.academic_year_label = "2024-2025"
    assert inst.current_academic_year() == "2024-2025"
    assert inst.current_ceremony_year(today=date(2026, 9, 1)) == "2024"


def test_staff_brief_and_student_transcript():
    inst = InstitutionFactory()
    ClubFactory(institution=inst, status="recognized")
    staff = UserFactory(role=User.Role.STAFF, institution=inst)
    student = UserFactory(role=User.Role.STUDENT, institution=inst)
    client = APIClient()
    client.force_authenticate(student)
    assert client.get("/api/campus-brief/").status_code == 403
    trans = client.get("/api/me/transcript/")
    assert trans.status_code == 200
    assert trans.data["engine"] == "clubconnect-transcript-v1"
    assert "MEMBERSHIPS" in trans.data["text"]
    client.force_authenticate(staff)
    brief = client.get("/api/campus-brief/")
    assert brief.status_code == 200
    assert brief.data["engine"] == "clubconnect-brief-v1"
    assert brief.data["academic_year"]
    analytics = client.get("/api/campus-analytics/")
    assert analytics.data["academic_year"] == inst.current_academic_year()


def test_sso_stays_off_without_client_id_and_never_skips_licensed_email(settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = ""
    client = APIClient()
    status = client.get("/api/auth/sso-status/")
    assert status.status_code == 200
    assert status.data["google"] is False
    assert status.data["microsoft"] is False
    assert status.data["licensed_email_required"] is True


def test_google_sso_still_requires_licensed_domain(settings, monkeypatch):
    settings.GOOGLE_OAUTH_CLIENT_ID = "test-client"
    monkeypatch.setattr(
        "apps.accounts.views.verify_google_id_token",
        lambda token, client_id: "stranger@gmail.com",
    )
    client = APIClient()
    res = client.post("/api/auth/sso/google/", {"id_token": "tok"}, format="json")
    assert res.status_code == 403


def test_leader_handover_requires_campus_email_then_committee_confirm():
    club = ClubFactory()
    leader, club = ClubLeaderFactory.create(club=club)
    domain = club.institution.student_email_domains[0]
    leader.email = f"old@{domain}"
    leader.save()
    incoming = UserFactory(role=User.Role.STUDENT, institution=club.institution)
    incoming.email = f"next@{domain}"
    incoming.save()
    treasurer = UserFactory(role=User.Role.STUDENT, institution=club.institution)
    treasurer.email = f"cash@{domain}"
    treasurer.save()
    outsider = UserFactory(role=User.Role.STUDENT)
    head = UserFactory(role=User.Role.COMMITTEE_HEAD, institution=club.institution)
    client = APIClient()
    client.force_authenticate(leader)
    bad = client.post(
        "/api/leadership-handovers/",
        {
            "club": str(club.id),
            "outgoing_committee": [
                {"name": leader.get_full_name(), "email": leader.email, "position": "Club leader"}
            ],
            "incoming_committee": [
                {"name": "Stranger", "email": outsider.email, "position": "Club leader"}
            ],
        },
        format="json",
    )
    assert bad.status_code == 400
    ok = client.post(
        "/api/leadership-handovers/",
        {
            "club": str(club.id),
            "outgoing_committee": [
                {"name": leader.get_full_name() or "Sarah", "email": leader.email, "position": "Club leader"}
            ],
            "incoming_committee": [
                {"name": "Next Leader", "email": incoming.email, "position": "President"},
                {"name": "Cash Officer", "email": treasurer.email, "position": "Treasurer"},
            ],
            "notes": "Bank signatories in the private notes.",
            "achievements_summary": "Won the robotics invitational.",
        },
        format="json",
    )
    assert ok.status_code == 201
    handover_id = ok.data["id"]
    assert ok.data["status"] == "nominated"
    assert len(ok.data["incoming_committee"]) == 2
    client.force_authenticate(incoming)
    blocked = client.post(f"/api/leadership-handovers/{handover_id}/confirm/", {}, format="json")
    assert blocked.status_code == 403
    client.force_authenticate(head)
    confirmed = client.post(f"/api/leadership-handovers/{handover_id}/confirm/", {}, format="json")
    assert confirmed.status_code == 200, confirmed.data
    assert confirmed.data["status"] == LeadershipHandover.Status.CONFIRMED
    assert ClubMembership.objects.filter(
        club=club, user=incoming, role=ClubMembership.MembershipRole.LEADER, is_active=True
    ).exists()
    assert ClubMembership.objects.filter(
        club=club, user=treasurer, role=ClubMembership.MembershipRole.OFFICER, is_active=True
    ).exists()
    outgoing_mem = ClubMembership.objects.get(club=club, user=leader)
    assert outgoing_mem.role == ClubMembership.MembershipRole.MEMBER
    assert LeadershipTerm.objects.filter(club=club, user=leader).exists()
    leader.refresh_from_db()
    incoming.refresh_from_db()
    treasurer.refresh_from_db()
    assert incoming.role == User.Role.CLUB_LEADER
    assert treasurer.role == User.Role.STUDENT
    assert leader.role == User.Role.STUDENT


def test_committee_head_handover_requires_campus_admin_confirm():
    inst = InstitutionFactory()
    student_domain = inst.student_email_domains[0]
    staff_domain = inst.staff_email_domains[0]
    head = UserFactory(role=User.Role.COMMITTEE_HEAD, institution=inst)
    head.email = f"head@{student_domain}"
    head.save()
    incoming = UserFactory(role=User.Role.STUDENT, institution=inst)
    incoming.email = f"nexthead@{student_domain}"
    incoming.save()
    deputy = UserFactory(role=User.Role.STUDENT, institution=inst)
    deputy.email = f"deputy@{student_domain}"
    deputy.save()
    admin = UserFactory(role=User.Role.SYSTEM_ADMIN, institution=inst)
    admin.email = f"admin@{staff_domain}"
    admin.save()
    outsider = UserFactory(role=User.Role.STUDENT)
    client = APIClient()
    client.force_authenticate(head)
    bad = client.post(
        "/api/campus-committee-handovers/",
        {
            "outgoing_committee": [{"name": "Head", "email": head.email, "position": "Committee Head"}],
            "incoming_committee": [{"name": "Stranger", "email": outsider.email, "position": "Committee Head"}],
        },
        format="json",
    )
    assert bad.status_code == 400
    ok = client.post(
        "/api/campus-committee-handovers/",
        {
            "outgoing_committee": [{"name": "Head", "email": head.email, "position": "Committee Head"}],
            "incoming_committee": [
                {"name": "Next Head", "email": incoming.email, "position": "Committee Head"},
                {"name": "Deputy", "email": deputy.email, "position": "Deputy committee head"},
            ],
        },
        format="json",
    )
    assert ok.status_code == 201, ok.data
    handover_id = ok.data["id"]
    assert ok.data["status"] == "nominated"
    client.force_authenticate(incoming)
    blocked = client.post(f"/api/campus-committee-handovers/{handover_id}/confirm/", {}, format="json")
    assert blocked.status_code == 403
    client.force_authenticate(head)
    still_blocked = client.post(f"/api/campus-committee-handovers/{handover_id}/confirm/", {}, format="json")
    assert still_blocked.status_code == 403
    client.force_authenticate(admin)
    confirmed = client.post(f"/api/campus-committee-handovers/{handover_id}/confirm/", {}, format="json")
    assert confirmed.status_code == 200, confirmed.data
    assert confirmed.data["status"] == "confirmed"
    head.refresh_from_db()
    incoming.refresh_from_db()
    deputy.refresh_from_db()
    assert incoming.role == User.Role.COMMITTEE_HEAD
    assert deputy.role == User.Role.STUDENT
    assert head.role == User.Role.STUDENT


def test_campus_admin_onboarding_and_year_fields():
    inst = InstitutionFactory(privacy_contact_email="")
    admin = UserFactory(role=User.Role.SYSTEM_ADMIN, institution=inst)
    client = APIClient()
    client.force_authenticate(admin)
    board = client.get("/api/campus-onboarding/")
    assert board.status_code == 200
    assert board.data["complete"] is False
    patch = client.patch(
        "/api/campus-institution/",
        {
            "academic_year_start_month": 1,
            "academic_year_label": "2026-2027",
            "report_deadline_day": 7,
            "privacy_contact_email": "privacy@example.edu",
        },
        format="json",
    )
    assert patch.status_code == 200
    assert patch.data["academic_year"] == "2026-2027"
    inst.refresh_from_db()
    assert inst.report_deadline_day == 7
