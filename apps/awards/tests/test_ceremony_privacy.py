import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.awards.models import Award, HallOfExcellenceEntry
from apps.awards.serializers import ceremony_year
from apps.core.tests.factories import ClubFactory, EvaluationCycleFactory, InstitutionFactory, UserFactory
from apps.core.tests.factories import ClubLeaderFactory

pytestmark = pytest.mark.django_db


def _ceremony_setup():
    inst = InstitutionFactory()
    club = ClubFactory(institution=inst, status="recognized")
    cycle = EvaluationCycleFactory()
    award = Award.objects.create(
        cycle=cycle,
        category_name="Club of the Year",
        description="Overall excellence.",
        winner_club=club,
        is_revealed=False,
    )
    head = UserFactory(role=User.Role.COMMITTEE_HEAD, institution=inst)
    student = UserFactory(role=User.Role.STUDENT, institution=inst)
    staff = UserFactory(role=User.Role.STAFF, institution=inst)
    leader, _ = ClubLeaderFactory.create(club=club)
    return inst, club, award, head, student, staff, leader


def test_ceremony_year_is_a_single_calendar_year():
    assert ceremony_year("2024-2025") == "2024"
    assert ceremony_year("2025") == "2025"
    assert ceremony_year(2026) == "2026"


def test_marks_and_awards_are_committee_head_only_until_publish():
    inst, club, award, head, student, staff, leader = _ceremony_setup()
    client = APIClient()
    for user in (student, staff):
        client.force_authenticate(user)
        assert client.get("/api/awards/").status_code == 403
        assert client.get("/api/monthly-evaluations/").status_code == 403
        hall = client.get("/api/hall-of-excellence/")
        assert hall.status_code == 200
        rows = hall.data["results"] if isinstance(hall.data, dict) else hall.data
        assert list(rows) == []

    client.force_authenticate(leader)
    assert client.get("/api/awards/").status_code == 403
    own = client.get("/api/monthly-evaluations/")
    assert own.status_code == 200
    assert "score" not in own.data
    assert "clubs" not in own.data

    client.force_authenticate(head)
    assert client.get("/api/awards/").status_code == 200
    ranks = client.get("/api/monthly-evaluations/")
    assert ranks.status_code == 200
    assert "clubs" in ranks.data
    assert "score" in ranks.data["clubs"][0]


def test_publish_ceremony_writes_hall_with_single_year():
    inst, club, award, head, student, staff, leader = _ceremony_setup()
    client = APIClient()
    client.force_authenticate(student)
    assert client.post("/api/awards/publish-ceremony/", {"year": "2025-2026"}, format="json").status_code == 403

    client.force_authenticate(head)
    res = client.post("/api/awards/publish-ceremony/", {"year": "2025-2026"}, format="json")
    assert res.status_code == 200
    assert res.data["year"] == "2025"
    assert res.data["count"] == 1
    award.refresh_from_db()
    assert award.is_revealed is True
    entry = HallOfExcellenceEntry.objects.get(award=award, club=club)
    assert entry.academic_year == "2025"

    client.force_authenticate(student)
    hall = client.get("/api/hall-of-excellence/")
    rows = hall.data["results"] if isinstance(hall.data, dict) else hall.data
    assert len(rows) == 1
    assert rows[0]["year"] == "2025"
    assert "-" not in rows[0]["year"]
    assert rows[0]["club_name"] == club.name

    client.force_authenticate(staff)
    hall2 = client.get("/api/hall-of-excellence/")
    rows2 = hall2.data["results"] if isinstance(hall2.data, dict) else hall2.data
    assert len(rows2) == 1


def test_unpublished_current_awards_do_not_appear_in_the_hall():
    inst, club, award, head, student, staff, leader = _ceremony_setup()
    HallOfExcellenceEntry.objects.create(
        club=club,
        award=award,
        academic_year="2026",
        citation="Should stay secret.",
    )
    client = APIClient()
    client.force_authenticate(student)
    hall = client.get("/api/hall-of-excellence/")
    rows = hall.data["results"] if isinstance(hall.data, dict) else hall.data
    assert list(rows) == []
