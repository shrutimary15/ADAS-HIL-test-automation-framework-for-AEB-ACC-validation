# =============================================================================
# test_aeb.py — Automatic Emergency Braking Test Cases
# =============================================================================
# These are the ACTUAL test cases. Each function is one test.
#
# WHY pytest?
# pytest is the industry standard Python test runner. It:
#   - Auto-discovers test functions (anything starting with "test_")
#   - Handles setup/teardown via "fixtures"
#   - Produces structured pass/fail results
#   - Integrates with CI/CD pipelines (Jenkins, GitHub Actions)
#
# In a real HIL project, pytest would be called by:
#   - Jenkins running overnight regression suites
#   - A pre-merge gate on GitLab/GitHub
#   - A scheduled nightly test campaign
#
# REQUIREMENT TRACEABILITY:
# Each test references a requirement ID (e.g. REQ_AEB_001).
# In a real project these map to DOORS/Jama/Polarion requirements.
# This is an ISO 26262 / ASPICE expectation.
# =============================================================================

import pytest
import yaml
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from framework.hil_interface import HILInterface
from framework.signal_monitor import SignalMonitor


# =============================================================================
# FIXTURES — pytest's way of doing setup/teardown
# =============================================================================
# A fixture runs BEFORE each test and cleans up AFTER.
# Think of it like TestCase.setUp() in unittest.
# The "yield" is where the test runs — code after yield = teardown.

@pytest.fixture(scope="module")
def config():
    """Load test configuration once per module."""
    cfg_path = os.path.join(os.path.dirname(__file__), "../config/test_config.yaml")
    with open(cfg_path) as f:
        return yaml.safe_load(f)

@pytest.fixture
def hil(config):
    """Create and connect HIL interface for each test, disconnect after."""
    bench = HILInterface(config)
    bench.connect()
    yield bench          # <-- test runs here
    bench.disconnect()   # <-- always runs after test, pass or fail


# =============================================================================
# TEST CASES
# =============================================================================

class TestAEBActivation:
    """
    Tests that AEB activates correctly when a collision threat is detected.
    Maps to: REQ_AEB_001, REQ_AEB_002
    Standard: ISO 22737, Euro NCAP AEB protocol
    """

    def test_aeb_activates_within_ttc_threshold(self, hil, config):
        """
        REQ_AEB_001: AEB system SHALL enter BRAKING state when TTC < 2.5s
                     and vehicle speed is between 10-80 kph.

        Scenario: Vehicle travelling at 50 kph, object 15m ahead closing
                  at 20 m/s → TTC = 0.75s (well below 2.5s threshold)

        Why this matters: This is the PRIMARY safety function.
        If this fails, the car won't brake automatically. People die.
        """
        # --- ARRANGE: Set up the scenario ---
        hil.inject_signal("VEHICLE_SPEED", 50.0)       # 50 kph
        hil.inject_signal("RADAR_OBJ_DISTANCE", 15.0)  # 15 metres ahead
        hil.inject_signal("RADAR_OBJ_VELOCITY", -20.0) # Closing at 20 m/s
        # TTC = 15 / 20 = 0.75s → well below 2.5s threshold

        # --- ACT: Step simulation and read ECU output ---
        hil.step(5)
        aeb_state = hil.read_signal("AEB_SYSTEM_STATE")

        # --- ASSERT: ECU must be in BRAKING state (value = 4) ---
        assert aeb_state == 4, (
            f"REQ_AEB_001 FAIL: Expected AEB state BRAKING(4), got {aeb_state}. "
            f"TTC = 0.75s is below threshold 2.5s — AEB must activate."
        )

    def test_aeb_brake_demand_magnitude(self, hil, config):
        """
        REQ_AEB_002: AEB brake demand SHALL be > 50% when TTC < 1.0s.

        Why this matters: The brake demand determines how hard the car brakes.
        Too little = not enough deceleration to avoid collision.
        """
        hil.inject_signal("VEHICLE_SPEED", 60.0)
        hil.inject_signal("RADAR_OBJ_DISTANCE", 10.0)  # Very close
        hil.inject_signal("RADAR_OBJ_VELOCITY", -25.0) # TTC = 0.4s

        hil.step(5)
        brake_demand = hil.read_signal("AEB_BRAKE_DEMAND")

        assert brake_demand > 50.0, (
            f"REQ_AEB_002 FAIL: Brake demand {brake_demand:.1f}% insufficient "
            f"for TTC < 1.0s. Expected > 50%."
        )

    def test_aeb_inactive_above_speed_limit(self, hil, config):
        """
        REQ_AEB_003: AEB SHALL remain INACTIVE when vehicle speed > 80 kph.

        Why this matters: At high speed, AEB autonomous braking could cause
        rear-end accidents. Above 80kph it only warns, doesn't brake.
        This is the Euro NCAP / regulatory boundary.
        """
        hil.inject_signal("VEHICLE_SPEED", 120.0)      # 120 kph — above limit
        hil.inject_signal("RADAR_OBJ_DISTANCE", 20.0)
        hil.inject_signal("RADAR_OBJ_VELOCITY", -15.0) # TTC = 1.3s (threatening)

        hil.step(5)
        aeb_state = hil.read_signal("AEB_SYSTEM_STATE")

        assert aeb_state != 4, (
            f"REQ_AEB_003 FAIL: AEB activated at 120kph — outside allowed speed "
            f"range (10-80kph). This would violate regulatory requirements."
        )

    def test_aeb_inactive_below_speed_limit(self, hil, config):
        """
        REQ_AEB_004: AEB SHALL remain INACTIVE when vehicle speed < 10 kph.

        Why: At parking speeds, AEB braking would be disruptive and unnecessary.
        """
        hil.inject_signal("VEHICLE_SPEED", 5.0)        # 5 kph — below minimum
        hil.inject_signal("RADAR_OBJ_DISTANCE", 3.0)
        hil.inject_signal("RADAR_OBJ_VELOCITY", -3.0)

        hil.step(5)
        aeb_state = hil.read_signal("AEB_SYSTEM_STATE")

        assert aeb_state == 0, (  # INACTIVE = 0
            f"REQ_AEB_004 FAIL: AEB active at {5.0}kph — below 10kph minimum."
        )

    def test_aeb_no_false_activation_clear_road(self, hil, config):
        """
        REQ_AEB_005: AEB SHALL NOT activate when there is no collision threat.

        Why: False activations are dangerous and erode driver trust.
        A car randomly braking on a motorway could cause accidents.
        """
        hil.inject_signal("VEHICLE_SPEED", 50.0)
        hil.inject_signal("RADAR_OBJ_DISTANCE", 150.0)  # Object far away
        hil.inject_signal("RADAR_OBJ_VELOCITY", 5.0)    # Moving away (positive)

        hil.step(5)
        brake_demand = hil.read_signal("AEB_BRAKE_DEMAND")

        assert brake_demand == 0.0, (
            f"REQ_AEB_005 FAIL: False AEB activation — brake demand "
            f"{brake_demand}% on clear road."
        )


class TestAEBTiming:
    """
    Tests timing requirements for AEB response.
    ISO 26262 mandates specific response times for safety functions.
    Maps to: REQ_AEB_010, REQ_AEB_011
    """

    def test_aeb_response_time_within_150ms(self, hil, config):
        """
        REQ_AEB_010: AEB SHALL enter BRAKING state within 150ms of TTC breach.

        WHY 150ms? ISO 26262 ASIL-B requirement for active safety systems.
        Human reaction time is ~250ms — the car must react faster.
        """
        max_response_ms = config["aeb"]["brake_response_max_ms"]  # 150ms

        # Start with safe scenario
        hil.inject_signal("VEHICLE_SPEED", 60.0)
        hil.inject_signal("RADAR_OBJ_DISTANCE", 100.0)
        hil.inject_signal("RADAR_OBJ_VELOCITY", 5.0)
        hil.step(3)

        # Suddenly inject dangerous scenario
        hil.inject_signal("RADAR_OBJ_DISTANCE", 12.0)
        hil.inject_signal("RADAR_OBJ_VELOCITY", -20.0)  # TTC = 0.6s

        # Measure response time to reach BRAKING state
        response_time = hil.measure_response_time(
            signal_name="AEB_SYSTEM_STATE",
            expected_state=4,            # BRAKING
            timeout_ms=500
        )

        assert response_time != -1, (
            f"REQ_AEB_010 FAIL: AEB did not reach BRAKING state within 500ms timeout."
        )
        assert response_time <= max_response_ms, (
            f"REQ_AEB_010 FAIL: AEB response time {response_time}ms "
            f"exceeds maximum allowed {max_response_ms}ms. "
            f"ISO 26262 ASIL-B violation."
        )

    def test_aeb_prefill_before_brake(self, hil, config):
        """
        REQ_AEB_011: AEB SHALL enter BRAKE_PREFILL state before full BRAKING.

        Why: Brake pre-fill reduces lag — the hydraulic system is pressurised
        ready to fire. This is standard on all modern ADAS systems.
        The state sequence should be: STANDBY → WARNING → PREFILL → BRAKING
        """
        monitor = SignalMonitor(hil)
        monitor.watch("AEB_SYSTEM_STATE")
        monitor.start()

        # Inject gradually worsening scenario
        hil.inject_signal("VEHICLE_SPEED", 55.0)
        hil.inject_signal("RADAR_OBJ_DISTANCE", 30.0)
        hil.inject_signal("RADAR_OBJ_VELOCITY", -15.0)  # TTC = 2.0s (near threshold)
        hil.step(10)

        hil.inject_signal("RADAR_OBJ_DISTANCE", 10.0)
        hil.inject_signal("RADAR_OBJ_VELOCITY", -20.0)  # TTC = 0.5s
        hil.step(10)

        results = monitor.stop()
        state_result = results["AEB_SYSTEM_STATE"]

        # Check that PREFILL (3) appeared before BRAKING (4)
        prefill_time = None
        braking_time = None

        for t, from_v, to_v in state_result.transitions:
            if to_v == 3 and prefill_time is None:
                prefill_time = t
            if to_v == 4 and braking_time is None:
                braking_time = t

        assert prefill_time is not None, (
            "REQ_AEB_011 FAIL: BRAKE_PREFILL state never observed."
        )
        if braking_time is not None:
            assert prefill_time < braking_time, (
                f"REQ_AEB_011 FAIL: BRAKING ({braking_time}ms) occurred "
                f"before BRAKE_PREFILL ({prefill_time}ms)."
            )
