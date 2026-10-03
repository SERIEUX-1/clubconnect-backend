import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.activities.models import Activity
from apps.clubs.models import Club
from apps.core.tests.factories import ClubFactory, InstitutionFactory, UserFactory
from apps.evidence.models import Evidence
from apps.impact.models import ImpactProject

pytestmark = pytest.mark.django_db


def _portfolio_club():
    inst = InstitutionFactory()
    club = ClubFactory(institution=inst, status=Club.Status.RECOGNIZED)
    activity = Activity.objects.create(
        club=club,
        title="Published workshop",
        activity_type="Workshop",
        date_time=timezone.now(),
        objective="Teach openly.",
        status=Activity.Status.VERIFIED,
        report_text="Everyone on campus can watch the film.",
    )
    project = ImpactProject.objects.create(
        club=club,
        title="Neighbourhood project",
        problem_statement="Need.",
        objective="Help.",
        beneficiaries_description="Residents.",
        start_date="2026-09-01",
        outcomes="Film published.",
    )
    Evidence.objects.create(
        club=club,
        activity=activity,
        evidence_type=Evidence.EvidenceType.VIDEO,
        status=Evidence.Status.VERIFIED,
        caption="Workshop film",
        external_link="https://www.youtube.com/watch?v=aqz-KE-bpKQ",
    )
    Evidence.objects.create(
        club=club,
        impact_project=project,
        evidence_type=Evidence.EvidenceType.VIDEO,
        status=Evidence.Status.VERIFIED,
        caption="Project film",
        external_link="https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
    )
    return inst, club


@pytest.mark.parametrize("role", ["student", "club_leader", "committee_head", "staff"])
def test_every_campus_role_can_watch_published_club_media(role):
    inst, club = _portfolio_club()
    user = UserFactory(role=role, institution=inst)
    client = APIClient()
    client.force_authenticate(user)
    res = client.get(f"/api/clubs/{club.id}/portfolio/")
    assert res.status_code == 200
    assert len(res.data["verified_activities"]) == 1
    assert res.data["verified_activities"][0]["media"]
    assert res.data["verified_activities"][0]["media"][0]["is_video"] is True
    assert res.data["impact_projects"][0]["media"][0]["is_video"] is True
    assert res.data["published_watch_count"] >= 2


def test_other_institution_cannot_open_club_portfolio():
    inst, club = _portfolio_club()
    outsider = UserFactory(role="student")
    assert outsider.institution_id != inst.id
    client = APIClient()
    client.force_authenticate(outsider)
    res = client.get(f"/api/clubs/{club.id}/portfolio/")
    assert res.status_code in (403, 404)


def test_anonymous_cannot_open_club_portfolio():
    _, club = _portfolio_club()
    res = APIClient().get(f"/api/clubs/{club.id}/portfolio/")
    assert res.status_code in (401, 403)


from apps.clubs.models import ClubMembership


def test_club_leader_can_publish_watch_item():
    inst, club = _portfolio_club()
    leader = UserFactory(role="club_leader", institution=inst)
    ClubMembership.objects.create(
        club=club,
        user=leader,
        role=ClubMembership.MembershipRole.LEADER,
        status=ClubMembership.Status.APPROVED,
        is_active=True,
    )
    client = APIClient()
    client.force_authenticate(leader)
    res = client.post(
        f"/api/clubs/{club.id}/publish-watch/",
        {
            "caption": "Match film",
            "evidence_type": "video",
            "external_link": "https://www.youtube.com/watch?v=aqz-KE-bpKQ",
        },
        format="json",
    )
    assert res.status_code == 201
    assert res.data["is_video"] is True
    port = client.get(f"/api/clubs/{club.id}/portfolio/")
    assert any(row["caption"] == "Match film" for row in port.data["published_media"])


def test_student_cannot_publish_watch_item():
    inst, club = _portfolio_club()
    student = UserFactory(role="student", institution=inst)
    client = APIClient()
    client.force_authenticate(student)
    res = client.post(
        f"/api/clubs/{club.id}/publish-watch/",
        {
            "caption": "Should fail",
            "external_link": "https://www.youtube.com/watch?v=aqz-KE-bpKQ",
        },
        format="json",
    )
    assert res.status_code == 403
