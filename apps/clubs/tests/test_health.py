import pytest

from apps.clubs.health import HealthIndicators, determine_status
from apps.clubs.health_models import ClubHealthSnapshot

pytestmark = pytest.mark.django_db


class TestDetermineStatus:
    def test_healthy_when_all_indicators_good(self):
        indicators = HealthIndicators(
            days_since_last_activity=5, report_completion_rate=1.0, evidence_completeness_rate=1.0
        )
        assert determine_status(indicators) == ClubHealthSnapshot.Status.HEALTHY

    def test_needs_attention_on_moderate_inactivity(self):
        indicators = HealthIndicators(
            days_since_last_activity=35, report_completion_rate=1.0, evidence_completeness_rate=1.0
        )
        assert determine_status(indicators) == ClubHealthSnapshot.Status.NEEDS_ATTENTION

    def test_at_risk_on_prolonged_inactivity(self):
        indicators = HealthIndicators(
            days_since_last_activity=90, report_completion_rate=1.0, evidence_completeness_rate=1.0
        )
        assert determine_status(indicators) == ClubHealthSnapshot.Status.AT_RISK

    def test_at_risk_triggered_by_report_completion_alone(self):
        """A single bad indicator is enough to flag AT_RISK -- the system
        favors catching problems early over waiting for everything to
        deteriorate at once (PRS: earlier intervention)."""
        indicators = HealthIndicators(
            days_since_last_activity=2, report_completion_rate=0.0, evidence_completeness_rate=1.0
        )
        assert determine_status(indicators) == ClubHealthSnapshot.Status.AT_RISK

    def test_brand_new_club_with_no_activity_yet_is_not_penalized_as_at_risk(self):
        """days_since_last_activity=None (never had an activity) must not
        crash or be misread as 'infinitely inactive'."""
        indicators = HealthIndicators(
            days_since_last_activity=None, report_completion_rate=1.0, evidence_completeness_rate=1.0
        )
        assert determine_status(indicators) == ClubHealthSnapshot.Status.HEALTHY
