# =============================================================================
# hil_interface.py — Simulated HIL Hardware Interface
# =============================================================================
# In a REAL HIL bench, this module would talk directly to:
#   - dSPACE DS1007 / MicroAutoBox (injects signals into the ECU)
#   - NI PXI chassis (National Instruments hardware)
#   - Vector CANoe/CANalyzer (CAN bus interface)
#
# The HIL hardware sits BETWEEN your test PC and the real ECU.
# It can:
#   [1] INJECT stimuli  → fake sensor inputs  (e.g. "radar sees object at 30m")
#   [2] READ responses  → ECU output signals   (e.g. "AEB demanded 80% brake")
#   [3] CONTROL time    → run scenarios at 20ms steps matching real rate
#
# Since we don't have the hardware here, this module SIMULATES it.
# The API (function names, parameters) mirrors what you'd see in real tools.
# =============================================================================

import time
import random
import logging
from can.signals import CAN_SIGNALS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [HIL] %(message)s")
log = logging.getLogger(__name__)


class HILInterface:
    """
    Simulates a HIL bench interface.

    In production, __init__ would call something like:
        self.board = dspace.connect("DS1007", channel=1)
    or
        self.session = ni_veristand.open_session("bench_config.nivssdf")
    """

    def __init__(self, config: dict):
        self.config = config
        self.sample_rate_ms = config["bench"]["sample_rate_ms"]
        self._state = {}          # Internal simulated ECU state
        self._scenario = None     # Active scenario parameters
        self._time_ms = 0         # Simulated elapsed time
        self._connected = False

    def connect(self):
        """Open connection to HIL bench hardware."""
        log.info(f"Connecting to bench: {self.config['bench']['name']}")
        log.info(f"DUT: {self.config['bench']['dut']}")
        # In real code: self.board.initialize() or similar
        self._connected = True
        self._time_ms = 0
        log.info("HIL bench connected ✓")

    def disconnect(self):
        """Cleanly close the HIL connection."""
        self._connected = False
        log.info("HIL bench disconnected.")

    # -------------------------------------------------------------------------
    # SIGNAL INJECTION — Stimulate the ECU with fake sensor inputs
    # -------------------------------------------------------------------------

    def inject_signal(self, signal_name: str, value: float):
        """
        Inject a CAN signal value onto the bus.

        In real HIL this would call:
            canoe.set_signal_value("RADAR_OBJ_DISTANCE", value)
        or
            dspace.write_variable("/Model Root/RadarDistance", value)

        Args:
            signal_name: Key from CAN_SIGNALS dict
            value:       Physical value (e.g. 35.0 for 35 metres)
        """
        if signal_name not in CAN_SIGNALS:
            raise ValueError(f"Unknown signal: {signal_name}")

        sig = CAN_SIGNALS[signal_name]
        # Clamp to signal's valid range
        value = max(sig["min"], min(sig["max"], value))
        self._state[signal_name] = value
        log.debug(f"INJECT {signal_name} = {value} {sig['unit']}")

    def inject_scenario(self, scenario: dict):
        """
        Load a full test scenario — sets initial conditions for all signals.

        Example scenario:
            {"VEHICLE_SPEED": 60.0, "RADAR_OBJ_DISTANCE": 25.0, ...}
        """
        log.info(f"Loading scenario: {scenario.get('name', 'unnamed')}")
        self._scenario = scenario
        for signal, value in scenario.items():
            if signal != "name" and signal in CAN_SIGNALS:
                self.inject_signal(signal, value)

    # -------------------------------------------------------------------------
    # SIGNAL READING — Read what the ECU output (what we are testing)
    # -------------------------------------------------------------------------

    def read_signal(self, signal_name: str) -> float:
        """
        Read a CAN signal value from the bus.

        In real HIL this would call:
            return canoe.get_signal_value("AEB_BRAKE_DEMAND")

        This simulation applies simple physics logic to produce realistic
        ECU responses based on the injected inputs.
        """
        if not self._connected:
            raise RuntimeError("HIL bench not connected. Call connect() first.")

        # Simulate ECU response based on injected state
        return self._simulate_ecu_response(signal_name)

    def _simulate_ecu_response(self, signal_name: str) -> float:
        """
        Core simulation logic — mimics ECU behaviour.
        This is where you'd normally just READ from hardware.
        We're generating plausible outputs based on inputs.
        """
        speed = self._state.get("VEHICLE_SPEED", 0.0)
        distance = self._state.get("RADAR_OBJ_DISTANCE", 999.0)
        rel_velocity = self._state.get("RADAR_OBJ_VELOCITY", 0.0)

        # Calculate Time-To-Collision (TTC)
        # TTC = distance / closing_speed
        # If rel_velocity is negative, object is approaching (closing)
        closing_speed = max(abs(rel_velocity), 0.1)
        ttc = distance / closing_speed if rel_velocity < 0 else 999.0

        aeb_cfg = self.config.get("aeb", {})
        ttc_threshold = aeb_cfg.get("ttc_threshold_s", 2.5)
        speed_min = aeb_cfg.get("speed_range_kph", {}).get("min", 10)
        speed_max = aeb_cfg.get("speed_range_kph", {}).get("max", 80)
        in_speed_range = speed_min <= speed <= speed_max

        # --- AEB outputs ---
        if signal_name == "AEB_SYSTEM_STATE":
            if not in_speed_range or speed < 1.0:
                return 0   # INACTIVE
            elif ttc > ttc_threshold * 1.5:
                return 1   # STANDBY
            elif ttc > ttc_threshold:
                return 2   # WARNING
            elif ttc > ttc_threshold * 0.6:
                return 3   # BRAKE_PREFILL
            else:
                return 4   # BRAKING

        elif signal_name == "AEB_BRAKE_DEMAND":
            if ttc < ttc_threshold and in_speed_range:
                # Scale brake demand: closer = harder braking
                # Add small noise (±2%) to simulate real sensor noise
                base_demand = min(100.0, (ttc_threshold / max(ttc, 0.1)) * 50)
                noise = random.uniform(-2.0, 2.0)
                return round(max(0.0, base_demand + noise), 1)
            return 0.0

        # --- ACC outputs ---
        elif signal_name == "ACC_SYSTEM_STATE":
            acc_cfg = self.config.get("acc", {})
            acc_min = acc_cfg.get("speed_range_kph", {}).get("min", 30)
            acc_max = acc_cfg.get("speed_range_kph", {}).get("max", 160)
            if acc_min <= speed <= acc_max:
                return 2   # ACTIVE
            elif speed > 0:
                return 1   # STANDBY
            return 0       # OFF

        elif signal_name == "ACC_FOLLOW_GAP":
            # Return current gap with small noise
            return round(distance + random.uniform(-0.5, 0.5), 1)

        elif signal_name == "ACC_TARGET_SPEED":
            return round(speed + random.uniform(-1.0, 1.0), 1)

        # Pass-through for input signals
        return self._state.get(signal_name, 0.0)

    # -------------------------------------------------------------------------
    # TIMING — Step through simulation time
    # -------------------------------------------------------------------------

    def step(self, steps: int = 1):
        """
        Advance simulation by N timesteps (each = sample_rate_ms).
        In real HIL, the hardware clock drives this — you just wait.
        """
        for _ in range(steps):
            self._time_ms += self.sample_rate_ms
            time.sleep(self.sample_rate_ms / 1000.0 * 0.1)  # 10x faster for demo

    @property
    def elapsed_ms(self) -> int:
        return self._time_ms

    def measure_response_time(self, signal_name: str, expected_state,
                               timeout_ms: int = 500) -> float:
        """
        Measure how long the ECU takes to reach expected_state.
        This is critical for ISO 26262 timing requirements.

        Returns response time in ms, or -1 if timeout exceeded.
        """
        start_ms = self._time_ms
        deadline = start_ms + timeout_ms

        while self._time_ms < deadline:
            self.step(1)
            current = self.read_signal(signal_name)
            if current == expected_state:
                return self._time_ms - start_ms

        return -1.0  # Timeout — ECU did not respond in time
