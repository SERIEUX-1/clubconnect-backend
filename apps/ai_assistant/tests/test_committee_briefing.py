import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.clubs.models import Club
from apps.core.tests.factories import ClubFactory, InstitutionFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_committee_head_briefing_orders_pending_charter_before_healthy_club():
    institution = InstitutionFactory(short_name="ALCHE", slug="alche")
    ClubFactory(institution=institution, name="Healthy Debate", status=Club.Status.RECOGNIZED)
    ClubFactory(
        institution=institution,
        name="Pending Robotics",
        status=Club.Status.PENDING,
        charter_statement="We want to build robots.",
    )
    head = UserFactory(role=User.Role.COMMITTEE_HEAD, institution=institution)
    client = APIClient()
    client.force_authenticate(head)

    res = client.get("/api/copilot/committee-briefing/")
    assert res.status_code == 200
    items = res.data["items"]
    assert items
    titles = [row["title"] for row in items]
    assert any("Pending Robotics" in t for t in titles)
    assert any(row.get("waiting_on_you") for row in items)
    assert res.data["days_away"] >= 0
    urgencies = [row["urgency"] for row in items]
    assert urgencies == sorted(urgencies)

    chat = client.post("/api/copilot/chat/", {"message": "Catch me up"}, format="json")
    assert chat.status_code == 200
    assert "Most urgent" in chat.data["reply"]
    assert chat.data["briefing"]["items"]


def test_student_cannot_open_committee_briefing():
    institution = InstitutionFactory()
    student = UserFactory(role=User.Role.STUDENT, institution=institution)
    client = APIClient()
    client.force_authenticate(student)
    res = client.get("/api/copilot/committee-briefing/")
    assert res.status_code == 403
