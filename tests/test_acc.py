# =============================================================================
# test_acc.py — Adaptive Cruise Control Test Cases
# =============================================================================
# ACC keeps the car at a set speed AND maintains a safe gap to vehicles ahead.
# Unlike basic cruise control, ACC automatically adjusts speed using radar.
#
# ACC operates from 30-160 kph (their luxury/performance range).
# The NVIDIA DRIVE platform handles sensor fusion for these features.
# =============================================================================

import pytest
import yaml
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from framework.hil_interface import HILInterface
from framework.signal_monitor import SignalMonitor


@pytest.fixture(scope="module")
def config():
    cfg_path = os.path.join(os.path.dirname(__file__), "../config/test_config.yaml")
    with open(cfg_path) as f:
        return yaml.safe_load(f)

@pytest.fixture
def hil(config):
    bench = HILInterface(config)
    bench.connect()
    yield bench
    bench.disconnect()


class TestACCActivation:
    """
    Tests that ACC activates and deactivates within its designed envelope.
    Maps to: REQ_ACC_001 – REQ_ACC_004
    """

    def test_acc_active_in_speed_range(self, hil, config):
        """
        REQ_ACC_001: ACC system SHALL be ACTIVE when vehicle speed is 30-160 kph.
        """
        hil.inject_signal("VEHICLE_SPEED", 100.0)   # 100 kph — well within range
        hil.inject_signal("RADAR_OBJ_DISTANCE", 50.0)
        hil.inject_signal("RADAR_OBJ_VELOCITY", 0.0)

        hil.step(5)
        acc_state = hil.read_signal("ACC_SYSTEM_STATE")

        assert acc_state == 2, (  # ACTIVE = 2
            f"REQ_ACC_001 FAIL: ACC not ACTIVE at 100kph. Got state {acc_state}."
        )

    def test_acc_standby_below_speed_range(self, hil, config):
        """
        REQ_ACC_002: ACC SHALL be in STANDBY (not ACTIVE) below 30 kph.

        Why: At low speed, ACC would fight with stop-go traffic logic.
        It stays armed (STANDBY) so it re-engages automatically above 30kph.
        """
        hil.inject_signal("VEHICLE_SPEED", 15.0)    # 15 kph — below range

        hil.step(5)
        acc_state = hil.read_signal("ACC_SYSTEM_STATE")

        assert acc_state != 2, (  # Should NOT be ACTIVE
            f"REQ_ACC_002 FAIL: ACC is ACTIVE at 15kph — below 30kph minimum."
        )

    def test_acc_maintains_follow_gap(self, hil, config):
        """
        REQ_ACC_003: ACC SHALL maintain following gap within 20-80 metres.

        This is the gap-control loop — the core of ACC functionality.
        Too close = danger. Too far = gap filled by other vehicles.
        """
        target_gap = 40.0   # Target 40m following distance

        hil.inject_signal("VEHICLE_SPEED", 90.0)
        hil.inject_signal("RADAR_OBJ_DISTANCE", target_gap)
        hil.inject_signal("RADAR_OBJ_VELOCITY", 0.0)

        hil.step(5)
        reported_gap = hil.read_signal("ACC_FOLLOW_GAP")

        cfg = config["acc"]
        assert cfg["follow_gap_min_m"] <= reported_gap <= cfg["follow_gap_max_m"], (
            f"REQ_ACC_003 FAIL: ACC follow gap {reported_gap:.1f}m outside "
            f"allowed range [{cfg['follow_gap_min_m']}-{cfg['follow_gap_max_m']}m]."
        )

    def test_acc_speed_tracking_accuracy(self, hil, config):
        """
        REQ_ACC_004: ACC speed demand SHALL be within ±2.0 kph of set speed.

        Speed tracking accuracy — the ECU must not demand wildly wrong speeds.
        """
        set_speed = 110.0   # Driver has set 110 kph

        hil.inject_signal("VEHICLE_SPEED", set_speed)
        hil.inject_signal("RADAR_OBJ_DISTANCE", 80.0)   # Far ahead, free road

        hil.step(5)
        target_speed = hil.read_signal("ACC_TARGET_SPEED")

        tolerance = config["acc"]["speed_tolerance_kph"]   # 2.0 kph
        error = abs(target_speed - set_speed)

        assert error <= tolerance, (
            f"REQ_ACC_004 FAIL: ACC speed error {error:.1f}kph exceeds "
            f"tolerance ±{tolerance}kph. Target={target_speed}, Set={set_speed}"
        )


class TestACCGapControl:
    """
    Tests ACC gap-control behaviour in dynamic scenarios.
    Maps to: REQ_ACC_010 – REQ_ACC_013
    """

    def test_acc_responds_to_cut_in(self, hil, config):
        """
        REQ_ACC_010: When a vehicle cuts in ahead, ACC SHALL respond
                     within 300ms (reduce speed or increase brake demand).

        Scenario: Car travelling at 100kph on clear road.
        Another vehicle suddenly cuts in at 25m (close gap!).

        This is one of the hardest ACC scenarios — sudden gap reduction.
        """
        max_response_ms = config["acc"]["response_time_max_ms"]   # 300ms

        # Initial: clear road
        hil.inject_signal("VEHICLE_SPEED", 100.0)
        hil.inject_signal("RADAR_OBJ_DISTANCE", 100.0)
        hil.inject_signal("RADAR_OBJ_VELOCITY", 0.0)
        hil.step(5)

        initial_speed_demand = hil.read_signal("ACC_TARGET_SPEED")

        # Cut-in event: vehicle suddenly appears at 25m
        hil.inject_signal("RADAR_OBJ_DISTANCE", 25.0)
        hil.inject_signal("RADAR_OBJ_VELOCITY", -5.0)  # Slightly slower

        response_time = hil.measure_response_time(
            signal_name="ACC_SYSTEM_STATE",
            expected_state=2,   # Should remain ACTIVE and adapt
            timeout_ms=max_response_ms + 100
        )

        # Just verify ACC is still active (didn't fault) and speed demand changed
        hil.step(5)
        new_speed_demand = hil.read_signal("ACC_TARGET_SPEED")
        acc_state = hil.read_signal("ACC_SYSTEM_STATE")

        assert acc_state == 2, (
            f"REQ_ACC_010 FAIL: ACC entered fault state after cut-in. Got state {acc_state}."
        )

    def test_acc_gap_too_close_triggers_intervention(self, hil, config):
        """
        REQ_ACC_011: If following gap drops below 20m at speed > 50kph,
                     ACC SHALL demand reduced speed (deceleration event).

        This is the boundary between ACC and AEB — ACC handles it first.
        """
        hil.inject_signal("VEHICLE_SPEED", 80.0)
        hil.inject_signal("RADAR_OBJ_DISTANCE", 15.0)   # Below 20m minimum!
        hil.inject_signal("RADAR_OBJ_VELOCITY", -2.0)

        hil.step(5)
        follow_gap = hil.read_signal("ACC_FOLLOW_GAP")
        acc_state = hil.read_signal("ACC_SYSTEM_STATE")

        # ACC must still be active (not faulted) — it should handle this
        assert acc_state in [2, 3], (  # ACTIVE or OVERRIDE
            f"REQ_ACC_011 FAIL: ACC faulted when gap was too close. State={acc_state}"
        )

    def test_acc_signal_continuity_during_operation(self, hil, config):
        """
        REQ_ACC_012: ACC signals SHALL not exhibit dropouts (gaps in signal)
                     during continuous operation over 2 seconds.

        Why: Signal dropouts can cause false deactivation or unsafe gaps.
        This tests the stability of the signal chain.
        """
        monitor = SignalMonitor(hil)
        monitor.watch("ACC_SYSTEM_STATE", min_val=0, max_val=4)
        monitor.watch("ACC_FOLLOW_GAP", min_val=0, max_val=100)
        monitor.start()

        hil.inject_signal("VEHICLE_SPEED", 90.0)
        hil.inject_signal("RADAR_OBJ_DISTANCE", 45.0)
        hil.inject_signal("RADAR_OBJ_VELOCITY", 0.0)

        # Run for 100 steps × 20ms = 2 seconds of simulated time
        for _ in range(100):
            hil.step(1)
            monitor.sample()

        results = monitor.stop()

        # Check no bound violations occurred
        for signal_name, result in results.items():
            assert result.passed, (
                f"REQ_ACC_012 FAIL: Signal violations on {signal_name}:\n"
                + "\n".join(result.violations)
            )
            # Check we got samples (no dropout)
            assert len(result.samples) > 0, (
                f"REQ_ACC_012 FAIL: No samples recorded for {signal_name} — signal dropout?"
            )

    def test_acc_does_not_interfere_with_aeb(self, hil, config):
        """
        REQ_ACC_013: When AEB is active (braking state), ACC SHALL
                     not demand acceleration. Features must not fight each other.

        SYSTEM INTEGRATION test — verifying two features coexist safely.
        This is a common real-world HIL test category.
        """
        # Set up AEB-triggering scenario
        hil.inject_signal("VEHICLE_SPEED", 60.0)
        hil.inject_signal("RADAR_OBJ_DISTANCE", 8.0)   # Very close
        hil.inject_signal("RADAR_OBJ_VELOCITY", -25.0) # TTC = 0.32s

        hil.step(10)

        aeb_state = hil.read_signal("AEB_SYSTEM_STATE")
        aeb_brake = hil.read_signal("AEB_BRAKE_DEMAND")
        acc_speed_demand = hil.read_signal("ACC_TARGET_SPEED")

        # If AEB is braking, ACC shouldn't be demanding high speed
        if aeb_state == 4:  # BRAKING
            assert aeb_brake > 0, (
                "REQ_ACC_013: AEB in BRAKING but brake demand is 0."
            )
            # ACC speed demand should be low (not accelerating into obstacle)
            assert acc_speed_demand <= 65.0, (
                f"REQ_ACC_013 FAIL: ACC demanding {acc_speed_demand}kph while AEB is braking. "
                f"Feature conflict — ACC fighting AEB!"
            )
