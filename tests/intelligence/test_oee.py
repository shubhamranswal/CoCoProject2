"""Tests verifying mathematical correctness of OEE calculations."""

from datetime import datetime, timedelta, timezone
import pytest

from domain.models import DowntimeEvent, ProductionRun
from services.oee_service import OEEService


def test_oee_perfect_run():
    service = OEEService()
    t0 = datetime(2026, 3, 30, 8, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(hours=8)  # 480 minutes

    # Ideal cycle time = 10.0s -> Ideal rate = 360 units / hr -> 2880 units for 8 hrs
    run = ProductionRun(
        run_id="RUN-PERFECT",
        line_id="LINE-B",
        machine_id="M204",
        product_code="BOTTLE-500",
        start_time=t0,
        end_time=t1,
        planned_units=2880,
        actual_units=2880,
        good_units=2880,
        scrap_units=0,
        ideal_cycle_time_seconds=10.0,
    )

    res = service.calculate_oee(production_run=run, downtime_events=None)

    assert res.availability == 1.0
    assert res.performance == 1.0
    assert res.quality == 1.0
    assert res.oee == 1.0


def test_oee_with_downtime_speed_loss_and_scrap():
    service = OEEService()
    t0 = datetime(2026, 3, 30, 8, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(hours=8)  # 480 minutes planned

    # 60 min unplanned downtime -> Operating time = 420 min -> Availability = 420 / 480 = 0.875
    # Operating seconds = 420 * 60 = 25200s
    # Ideal cycle time = 10s -> Max possible in operating time = 2520 units
    # Actual units produced = 2268 -> Performance = 2268 / 2520 = 0.90
    # Good units = 2154.6, scrap = 113.4 -> Quality = 2154.6 / 2268 = 0.95
    # OEE = 0.875 * 0.90 * 0.95 = 0.748125

    run = ProductionRun(
        run_id="RUN-IMPACTED",
        line_id="LINE-B",
        machine_id="M204",
        product_code="BOTTLE-500",
        start_time=t0,
        end_time=t1,
        planned_units=2880,
        actual_units=2268,
        good_units=2155,
        scrap_units=113,
        ideal_cycle_time_seconds=10.0,
    )

    dt = DowntimeEvent(
        downtime_id="DT-1",
        machine_id="M204",
        line_id="LINE-B",
        start_time=t0 + timedelta(hours=2),
        end_time=t0 + timedelta(hours=3),
        duration_minutes=60.0,
        reason_code="BEARING_OVERHEAT",
        category="UNPLANNED",
    )

    res = service.calculate_oee(production_run=run, downtime_events=[dt])

    assert pytest.approx(res.availability, abs=1e-3) == 0.875
    assert pytest.approx(res.performance, abs=1e-3) == 0.900
    assert pytest.approx(res.quality, abs=1e-3) == 2155 / 2268
    assert pytest.approx(res.oee, abs=1e-3) == 0.875 * 0.900 * (2155 / 2268)
    assert res.downtime_minutes == 60.0

