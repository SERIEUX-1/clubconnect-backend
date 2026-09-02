"""
Shared factories so every app's tests can build realistic objects without
copy-pasting model setup. Add a factory here whenever a new model needs
one — keep it colocated so it doesn't drift from the real schema.
"""
import datetime
from decimal import Decimal

import factory

from apps.accounts.models import User
from apps.clubs.models import Club, ClubMembership
from apps.evaluation.models import EvaluationCriterion, EvaluationCycle, Score


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.edu")
    role = User.Role.STUDENT

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        self.set_password(extracted or "TestPass123!")
        if create:
            self.save()


class ClubFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Club

    name = factory.Sequence(lambda n: f"Test Club {n}")
    slug = factory.Sequence(lambda n: f"test-club-{n}")
    category = "Technology"
    status = Club.Status.RECOGNIZED


class ClubLeaderFactory:
    """Not a DjangoModelFactory itself — a helper that creates a User with
    role CLUB_LEADER and attaches them as an active leader membership on
    the given club, since 'leadership' is derived from ClubMembership
    rather than a flag on User."""

    @staticmethod
    def create(club=None, **user_kwargs):
        club = club or ClubFactory()
        user = UserFactory(role=User.Role.CLUB_LEADER, **user_kwargs)
        ClubMembership.objects.create(
            club=club, user=user, role=ClubMembership.MembershipRole.LEADER,
            status=ClubMembership.Status.APPROVED, is_active=True,
        )
        return user, club


class EvaluationCycleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EvaluationCycle

    name = factory.Sequence(lambda n: f"Cycle {n}")
    evaluation_months = ["2026-12", "2027-01"]
    reveal_date = datetime.date(2027, 3, 1)
    aggregation_method = "simple_average"


class EvaluationCriterionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EvaluationCriterion

    cycle = factory.SubFactory(EvaluationCycleFactory)
    key = factory.Sequence(lambda n: f"criterion_{n}")
    label = "Activity & Consistency"
    weight_percent = Decimal("15.00")
    version = 1
    effective_date = datetime.date(2026, 8, 1)


class ScoreFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Score

    club = factory.SubFactory(ClubFactory)
    cycle = factory.SubFactory(EvaluationCycleFactory)
    criterion = factory.SubFactory(EvaluationCriterionFactory)
    period_year = 2026
    period_month = 12
