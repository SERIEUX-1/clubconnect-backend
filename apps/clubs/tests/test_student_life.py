import pytest
from rest_framework.test import APIClient

from apps.clubs.models import Club
from apps.core.tests.factories import ClubFactory, InstitutionFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_student_life_desk_hides_healthy_clubs_and_blocks_students():
    campus = InstitutionFactory()
    office = UserFactory(role="student_life", institution=campus)
    student = UserFactory(role="student", institution=campus)
    ClubFactory(institution=campus, status=Club.Status.PENDING, name="New Film Club")
    ClubFactory(institution=campus, status=Club.Status.RECOGNIZED, name="Quiet Chess")

    client = APIClient()
    client.force_authenticate(student)
    assert client.get("/api/student-life/desk/").status_code == 403

    client.force_authenticate(office)
    res = client.get("/api/student-life/desk/")
    assert res.status_code == 200
    assert res.data["waiting"][0]["name"] == "New Film Club"
    assert res.data["waiting"][0]["kind"] == "charter"
    assert "fine_count" in res.data


def test_student_life_can_recognise_and_pause_with_a_reason():
    campus = InstitutionFactory()
    office = UserFactory(role="student_life", institution=campus)
    club = ClubFactory(institution=campus, status=Club.Status.PENDING, name="Garden Circle")
    client = APIClient()
    client.force_authenticate(office)

    recognised = client.post(f"/api/clubs/{club.id}/recognize/")
    assert recognised.status_code == 200
    club.refresh_from_db()
    assert club.status == Club.Status.RECOGNIZED

    missing = client.post(f"/api/clubs/{club.id}/pause/", {"reason": "short"}, format="json")
    assert missing.status_code == 400

    paused = client.post(
        f"/api/clubs/{club.id}/pause/",
        {"reason": "Leaders have not answered two reminders."},
        format="json",
    )
    assert paused.status_code == 200
    club.refresh_from_db()
    assert club.status == Club.Status.SUSPENDED


def test_lecturer_cannot_pause_a_club():
    campus = InstitutionFactory()
    lecturer = UserFactory(role="staff", institution=campus)
    club = ClubFactory(institution=campus, status=Club.Status.RECOGNIZED)
    client = APIClient()
    client.force_authenticate(lecturer)
    res = client.post(
        f"/api/clubs/{club.id}/pause/",
        {"reason": "A lecturer should not pause a club from this seat."},
        format="json",
    )
    assert res.status_code == 403
