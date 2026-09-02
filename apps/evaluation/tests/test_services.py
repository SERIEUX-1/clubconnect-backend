"""
Unit tests for apps.evaluation.services — the scoring engine.

Deliberately independent of the API layer (no client, no auth) per the
scaffold's design goal: this logic must be testable and trustworthy on its
own. If these tests are green, the numbers a Committee Head sees are
provably correct arithmetic, whatever the UI does around them.
"""
from decimal import Decimal

import pytest

from apps.core.tests.factories import (
    ClubFactory, EvaluationCriterionFactory, EvaluationCycleFactory, ScoreFactory, UserFactory,
)
from apps.evaluation.models import Score
from apps.evaluation.services import (
    WeightConfigurationError, aggregate_cycle_score, apply_human_adjustment,
    compute_month_score, validate_cycle_weights,
)

pytestmark = pytest.mark.django_db


def make_cycle_with_two_criteria(weight_a=Decimal("60.00"), weight_b=Decimal("40.00")):
    cycle = EvaluationCycleFactory(evaluation_months=["2026-12"])
    crit_a = EvaluationCriterionFactory(cycle=cycle, key="activity", weight_percent=weight_a)
    crit_b = EvaluationCriterionFactory(cycle=cycle, key="participation", weight_percent=weight_b)
    return cycle, crit_a, crit_b


class TestValidateCycleWeights:
    def test_passes_when_weights_sum_to_100(self):
        cycle, *_ = make_cycle_with_two_criteria(Decimal("60.00"), Decimal("40.00"))
        validate_cycle_weights(cycle)  # should not raise

    def test_raises_when_weights_do_not_sum_to_100(self):
        cycle, *_ = make_cycle_with_two_criteria(Decimal("60.00"), Decimal("30.00"))
        with pytest.raises(WeightConfigurationError):
            validate_cycle_weights(cycle)

    def test_only_the_latest_version_of_a_criterion_counts(self):
        """A superseded (old-version) criterion must not double-count
        towards the 100% total once a new version exists."""
        cycle, crit_a, crit_b = make_cycle_with_two_criteria(Decimal("60.00"), Decimal("40.00"))
        # Superseding crit_a with a new version at a different weight.
        EvaluationCriterionFactory(
            cycle=cycle, key="activity", weight_percent=Decimal("55.00"), version=2
        )
        # New total should still be checked against the latest versions only: 55 + 40 = 95 -> fails.
        with pytest.raises(WeightConfigurationError):
            validate_cycle_weights(cycle)


class TestComputeMonthScore:
    def test_weighted_contribution_is_correct(self):
        cycle, crit_a, crit_b = make_cycle_with_two_criteria(Decimal("60.00"), Decimal("40.00"))
        club = ClubFactory()
        ScoreFactory(club=club, cycle=cycle, criterion=crit_a, period_year=2026, period_month=12,
                     final_value=Decimal("80.00"))
        ScoreFactory(club=club, cycle=cycle, criterion=crit_b, period_year=2026, period_month=12,
                     final_value=Decimal("50.00"))

        result = compute_month_score(club, cycle, 2026, 12)

        # 80 * 0.60 = 48.00, 50 * 0.40 = 20.00 -> total 68.00
        assert result.total_score == Decimal("68.00")
        assert len(result.breakdown) == 2

    def test_falls_back_to_ai_recommendation_when_no_final_value(self):
        cycle, crit_a, crit_b = make_cycle_with_two_criteria(Decimal("100.00"), Decimal("0.00"))
        club = ClubFactory()
        ScoreFactory(club=club, cycle=cycle, criterion=crit_a, period_year=2026, period_month=12,
                     final_value=None, ai_recommended_value=Decimal("70.00"))

        result = compute_month_score(club, cycle, 2026, 12)

        assert result.total_score == Decimal("70.00")

    def test_scores_with_no_value_at_all_are_skipped_not_treated_as_zero(self):
        cycle, crit_a, crit_b = make_cycle_with_two_criteria(Decimal("60.00"), Decimal("40.00"))
        club = ClubFactory()
        ScoreFactory(club=club, cycle=cycle, criterion=crit_a, period_year=2026, period_month=12,
                     final_value=Decimal("90.00"))
        ScoreFactory(club=club, cycle=cycle, criterion=crit_b, period_year=2026, period_month=12,
                     final_value=None, ai_recommended_value=None)

        result = compute_month_score(club, cycle, 2026, 12)

        # Only the scored criterion contributes -- unscored is NOT silently zeroed.
        assert len(result.breakdown) == 1
        assert result.total_score == Decimal("54.00")  # 90 * 0.60


class TestAggregateCycleScore:
    def test_simple_average_across_months(self):
        cycle = EvaluationCycleFactory(evaluation_months=["2026-12", "2027-01"], aggregation_method="simple_average")
        crit = EvaluationCriterionFactory(cycle=cycle, key="activity", weight_percent=Decimal("100.00"))
        club = ClubFactory()
        ScoreFactory(club=club, cycle=cycle, criterion=crit, period_year=2026, period_month=12,
                     final_value=Decimal("80.00"))
        ScoreFactory(club=club, cycle=cycle, criterion=crit, period_year=2027, period_month=1,
                     final_value=Decimal("60.00"))

        total = aggregate_cycle_score(club, cycle)

        assert total == Decimal("70.00")

    def test_weighted_average_respects_configured_month_weights(self):
        cycle = EvaluationCycleFactory(
            evaluation_months=["2026-12", "2027-01"],
            aggregation_method="weighted_average",
            aggregation_config={"month_weights": {"2026-12": 1, "2027-01": 3}},
        )
        crit = EvaluationCriterionFactory(cycle=cycle, key="activity", weight_percent=Decimal("100.00"))
        club = ClubFactory()
        ScoreFactory(club=club, cycle=cycle, criterion=crit, period_year=2026, period_month=12,
                     final_value=Decimal("100.00"))
        ScoreFactory(club=club, cycle=cycle, criterion=crit, period_year=2027, period_month=1,
                     final_value=Decimal("0.00"))

        total = aggregate_cycle_score(club, cycle)

        # (100*1 + 0*3) / 4 = 25.00 -- the later, heavier-weighted month dominates.
        assert total == Decimal("25.00")

    def test_returns_zero_when_no_months_scored(self):
        cycle = EvaluationCycleFactory(evaluation_months=["2026-12"])
        club = ClubFactory()
        assert aggregate_cycle_score(club, cycle) == Decimal("0.00")


class TestApplyHumanAdjustment:
    def test_writes_an_immutable_adjustment_record(self):
        score = ScoreFactory(ai_recommended_value=Decimal("65.00"), final_value=None)
        reviewer = UserFactory(role="committee_head")

        adjustment = apply_human_adjustment(score, Decimal("72.00"), "Strong evidence of impact", reviewer)

        assert adjustment.previous_value is None
        assert adjustment.new_value == Decimal("72.00")
        assert adjustment.reason == "Strong evidence of impact"
        assert adjustment.adjusted_by == reviewer

    def test_updates_score_to_final_stage(self):
        score = ScoreFactory(ai_recommended_value=Decimal("65.00"), final_value=None)
        reviewer = UserFactory(role="committee_head")

        apply_human_adjustment(score, Decimal("72.00"), "reason", reviewer)
        score.refresh_from_db()

        assert score.final_value == Decimal("72.00")
        assert score.stage == Score.Stage.FINAL
        assert score.reviewed_by == reviewer

    def test_second_adjustment_records_the_true_previous_value(self):
        """Guards against a regression where 'previous_value' could be
        computed from the wrong source (e.g. the AI value) instead of
        whatever the score's final_value actually was before this change."""
        score = ScoreFactory(ai_recommended_value=Decimal("65.00"), final_value=None)
        reviewer = UserFactory(role="committee_head")

        apply_human_adjustment(score, Decimal("72.00"), "first pass", reviewer)
        score.refresh_from_db()
        second = apply_human_adjustment(score, Decimal("80.00"), "appeal upheld", reviewer)

        assert second.previous_value == Decimal("72.00")
        assert second.new_value == Decimal("80.00")
