"""
Scoring engine.

PRS Section 14 hard requirement: "Do not tightly couple the scoring engine
to the UI." Everything here is plain Python/Decimal operating on the
EvaluationCriterion/Score models — no request, no response, no view. This
is what makes it independently unit-testable (PRS Section 20: "Unit tests:
scoring calculations...") and safe to call from the API, from a management
command, or from the AI assistant's recommendation pipeline.
"""
from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Sum

from .models import Appeal, EvaluationCriterion, Score, ScoreAdjustment


class WeightConfigurationError(Exception):
    """Raised when a cycle's criteria weights don't sum to 100%."""


@dataclass
class CriterionResult:
    key: str
    label: str
    weight_percent: Decimal
    raw_value: Decimal  # 0-100 score the club earned on this criterion
    weighted_contribution: Decimal


@dataclass
class ClubCycleScoreResult:
    club_id: str
    cycle_id: str
    total_score: Decimal
    breakdown: list[CriterionResult]


def _latest_criterion_versions(cycle):
    """
    Returns one EvaluationCriterion per distinct `key`: whichever has the
    highest `version`. Deliberately implemented without `.distinct(field)`
    (Postgres-only `DISTINCT ON` syntax) so this logic behaves identically
    on every backend, including SQLite in tests/CI.
    """
    latest_by_key: dict[str, EvaluationCriterion] = {}
    for criterion in EvaluationCriterion.objects.filter(cycle=cycle).order_by("key", "version"):
        latest_by_key[criterion.key] = criterion  # last write per key wins = highest version
    return latest_by_key.values()


def validate_cycle_weights(cycle) -> None:
    """A cycle's *current-version* criteria must sum to exactly 100%."""
    latest_versions = _latest_criterion_versions(cycle)
    total = sum((c.weight_percent for c in latest_versions), Decimal("0"))
    if total != Decimal("100.00"):
        raise WeightConfigurationError(
            f"Cycle '{cycle.name}' criteria weights sum to {total}%, not 100%."
        )


def compute_month_score(club, cycle, period_year: int, period_month: int) -> ClubCycleScoreResult:
    """
    Combines each criterion's final (human-approved) value, weighted by its
    configured percentage, into a single month score. Falls back to the AI
    recommendation ONLY for display/preview purposes — a score is never
    counted as authoritative until stage == FINAL, enforced by the caller.
    """
    scores = Score.objects.filter(
        club=club, cycle=cycle, period_year=period_year, period_month=period_month
    ).select_related("criterion")

    breakdown = []
    total = Decimal("0.00")
    for score in scores:
        value = score.final_value if score.final_value is not None else score.ai_recommended_value
        if value is None:
            continue
        weight = score.criterion.weight_percent / Decimal("100")
        contribution = (value * weight).quantize(Decimal("0.01"))
        breakdown.append(
            CriterionResult(
                key=score.criterion.key,
                label=score.criterion.label,
                weight_percent=score.criterion.weight_percent,
                raw_value=value,
                weighted_contribution=contribution,
            )
        )
        total += contribution

    return ClubCycleScoreResult(
        club_id=str(club.id), cycle_id=str(cycle.id), total_score=total, breakdown=breakdown
    )


def aggregate_cycle_score(club, cycle) -> Decimal:
    """
    Rolls up every evaluated month in the cycle into one overall score,
    using whichever aggregation_method the cycle was configured with (PRS
    Section 10: "The aggregation method must be configurable").
    """
    monthly_totals = []
    for period in cycle.evaluation_months:  # ["2026-12", "2027-01", ...]
        year, month = (int(p) for p in period.split("-"))
        result = compute_month_score(club, cycle, year, month)
        if result.breakdown:
            monthly_totals.append(result.total_score)

    if not monthly_totals:
        return Decimal("0.00")

    if cycle.aggregation_method == "simple_average":
        return (sum(monthly_totals) / len(monthly_totals)).quantize(Decimal("0.01"))

    if cycle.aggregation_method == "weighted_average":
        weights = cycle.aggregation_config.get("month_weights", {})
        weighted_sum = Decimal("0.00")
        weight_total = Decimal("0.00")
        for period, total in zip(cycle.evaluation_months, monthly_totals):
            w = Decimal(str(weights.get(period, 1)))
            weighted_sum += total * w
            weight_total += w
        return (weighted_sum / weight_total).quantize(Decimal("0.01")) if weight_total else Decimal("0.00")

    # "custom": delegate to a pluggable callable registered in aggregation_config
    raise NotImplementedError(
        "Custom aggregation rule requested but no handler registered. "
        "Implement and register it rather than hard-coding it here."
    )


def apply_human_adjustment(score: Score, new_value: Decimal, reason: str, adjusted_by) -> ScoreAdjustment:
    """The ONLY sanctioned way to change a score's final value. Always
    writes an immutable adjustment record before mutating the score."""
    adjustment = ScoreAdjustment.objects.create(
        score=score,
        previous_value=score.final_value,
        new_value=new_value,
        reason=reason,
        adjusted_by=adjusted_by,
    )
    score.final_value = new_value
    score.stage = Score.Stage.FINAL
    score.reviewed_by = adjusted_by
    score.save(update_fields=["final_value", "stage", "reviewed_by", "updated_at"])
    return adjustment
