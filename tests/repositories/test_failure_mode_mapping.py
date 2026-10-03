"""Regression test for canonical prediction FailureMode mapping.

Verifies that suspected_component_id patterns ('MTR', 'BRG', 'HYD', 'GRB', etc.)
map strictly to valid FailureMode enum members without raising AttributeError.
"""

from datetime import datetime, timezone
import pytest

from domain.enums import FailureMode
from domain.models import CanonicalPrediction
from repositories.snowflake.snowflake_repository import _canonical_to_ml_prediction as snowflake_mapper
from repositories.memory.memory_repository import _canonical_to_ml_prediction as memory_mapper


@pytest.mark.parametrize("mapper", [snowflake_mapper, memory_mapper])
@pytest.mark.parametrize(
    "comp_id,expected_mode",
    [
        ("C-M21-MTR", FailureMode.MOTOR_OVERHEATING),
        ("C-M21-MOTOR-01", FailureMode.MOTOR_OVERHEATING),
        ("C-M21-BRG-DE", FailureMode.BEARING_DEGRADATION),
        ("C-M21-BEARING-NDE", FailureMode.BEARING_DEGRADATION),
        ("C-M21-HYD-01", FailureMode.MECHANICAL_WEAR),
        ("C-M21-GRB-01", FailureMode.MECHANICAL_WEAR),
        ("C-M21-GEAR-02", FailureMode.MECHANICAL_WEAR),
        ("UNKNOWN", FailureMode.BEARING_DEGRADATION),
    ],
)
def test_canonical_to_ml_prediction_valid_failure_mode(mapper, comp_id, expected_mode):
    """Ensure canonical predictions for motor, bearing, hyd, grb map to valid FailureMode."""
    cp = CanonicalPrediction(
        prediction_id="PRED-TEST-001",
        machine_id="M21",
        suspected_component_id=comp_id,
        failure_prob=0.92,
        risk_level="HIGH",
        horizon_days=7,
        model_name="XGB-M21-v1",
        scored_ts=datetime.now(timezone.utc),
        top_features='{"vib_rms": 0.45, "temp": 0.35}',
    )

    pred = mapper(cp)
    assert isinstance(pred.failure_mode, FailureMode)
    assert pred.failure_mode == expected_mode
    assert pred.failure_mode in list(FailureMode)
