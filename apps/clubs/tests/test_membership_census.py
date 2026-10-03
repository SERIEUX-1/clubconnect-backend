import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.clubs.models import ClubMembership, ClubConceptNote, ClubBudgetSpend
from apps.core.tests.factories import ClubFactory, ClubLeaderFactory, InstitutionFactory, UserFactory

pytestmark = pytest.mark.django_db


def _open_window(head, client, amount="7.00"):
    client.force_authenticate(head)
    res = client.patch(
        "/api/membership-census/window/",
        {"open": True, "member_grant_amount": amount, "member_grant_currency": "USD"},
        format="json",
    )
    assert res.status_code == 200, res.data
    assert res.data["open"] is True


def test_join_blocked_until_committee_opens_window():
    club = ClubFactory(status="recognized")
    student = UserFactory(role=User.Role.STUDENT, institution=club.institution)
    head = UserFactory(role=User.Role.COMMITTEE_HEAD, institution=club.institution)
    client = APIClient()
    client.force_authenticate(student)
    closed = client.post("/api/club-memberships/", {"club": str(club.id)}, format="json")
    assert closed.status_code == 403
    _open_window(head, client)
    client.force_authenticate(student)
    opened = client.post("/api/club-memberships/", {"club": str(club.id)}, format="json")
    assert opened.status_code == 201
    assert opened.data["status"] == "requested"


def test_share_weighted_grant_and_spend_follow_membership():
    inst = InstitutionFactory()
    club_a = ClubFactory(institution=inst, status="recognized", name="Alpha", slug="alpha")
    club_b = ClubFactory(institution=inst, status="recognized", name="Beta", slug="beta")
    club_c = ClubFactory(institution=inst, status="recognized", name="Gamma", slug="gamma")
    exclusive = UserFactory(institution=inst)
    pair = UserFactory(institution=inst)
    triple = UserFactory(institution=inst)
    for user, clubs in (
        (exclusive, [club_a]),
        (pair, [club_a, club_b]),
        (triple, [club_a, club_b, club_c]),
    ):
        for club in clubs:
            ClubMembership.objects.create(
                club=club,
                user=user,
                status=ClubMembership.Status.APPROVED,
                is_active=True,
            )
    head = UserFactory(role=User.Role.COMMITTEE_HEAD, institution=inst)
    client = APIClient()
    _open_window(head, client, "7.00")
    ledger = client.get("/api/membership-ledger/")
    assert ledger.status_code == 200
    by_name = {row["name"]: row for row in ledger.data["clubs"]}
    # 7 + 3.50 + 2.33
    assert by_name["Alpha"]["exclusive"] == 1
    assert by_name["Alpha"]["in_2"] == 1
    assert by_name["Alpha"]["in_3"] == 1
    assert by_name["Alpha"]["entitlement"] == "12.83"
    assert by_name["Beta"]["entitlement"] == "5.83"
    assert by_name["Gamma"]["entitlement"] == "2.33"
    assert ledger.data["campus"]["unique_members"] == 3
    assert ledger.data["campus"]["pot"] == "21.00"

    spend = client.post(
        "/api/club-budget-spends/",
        {"club": str(club_a.id), "amount": "4.00", "comment": "Bus hire for the open day."},
        format="json",
    )
    assert spend.status_code == 201, spend.data
    again = client.get("/api/membership-ledger/")
    alpha = {row["name"]: row for row in again.data["clubs"]}["Alpha"]
    assert alpha["spent"] == "4.00"
    assert alpha["remaining"] == "8.83"
    assert alpha["latest_comment"] == "Bus hire for the open day."


def test_student_declares_clubs_then_committee_confirms():
    club = ClubFactory(status="recognized")
    other = ClubFactory(institution=club.institution, status="recognized", name="Other", slug="other")
    student = UserFactory(role=User.Role.STUDENT, institution=club.institution)
    head = UserFactory(role=User.Role.COMMITTEE_HEAD, institution=club.institution)
    client = APIClient()
    client.force_authenticate(student)
    blocked = client.post(
        "/api/membership-census/declare/",
        {"club_ids": [str(club.id), str(other.id)]},
        format="json",
    )
    assert blocked.status_code == 403
    _open_window(head, client)
    client.force_authenticate(student)
    declared = client.post(
        "/api/membership-census/declare/",
        {"club_ids": [str(club.id), str(other.id)]},
        format="json",
    )
    assert declared.status_code == 201, declared.data
    assert declared.data["count"] == 2
    ids = [row["id"] for row in declared.data["requested"]]
    client.force_authenticate(head)
    confirmed = client.post("/api/membership-census/confirm/", {"ids": ids}, format="json")
    assert confirmed.status_code == 200
    assert confirmed.data["count"] == 2
    assert ClubMembership.objects.filter(user=student, status=ClubMembership.Status.APPROVED).count() == 2


def test_session_identity_follows_live_membership_window():
    inst = InstitutionFactory()
    head = UserFactory(role=User.Role.COMMITTEE_HEAD, institution=inst)
    student = UserFactory(role=User.Role.STUDENT, institution=inst)
    client = APIClient()
    client.force_authenticate(student)
    me = client.get("/api/me/")
    assert me.status_code == 200
    assert me.data["institution"]["membership_census_open"] is False
    _open_window(head, client)
    client.force_authenticate(student)
    opened = client.get("/api/me/")
    assert opened.data["institution"]["membership_census_open"] is True
    window = client.get("/api/membership-census/window/")
    assert window.data["open"] is True
    client.force_authenticate(head)
    client.patch("/api/membership-census/window/", {"open": False}, format="json")
    client.force_authenticate(student)
    closed = client.get("/api/me/")
    assert closed.data["institution"]["membership_census_open"] is False
    blocked = client.post("/api/club-memberships/", {"club": str(ClubFactory(institution=inst, status="recognized").id)}, format="json")
    assert blocked.status_code == 403
