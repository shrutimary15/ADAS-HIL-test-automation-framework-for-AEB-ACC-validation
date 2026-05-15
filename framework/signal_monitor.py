# =============================================================================
# signal_monitor.py — Real-time Signal Monitoring
# =============================================================================
# In HIL testing, you don't just check one value once.
# You WATCH signals over time — like an oscilloscope.
#
# A signal monitor:
#   - Records signal values at each timestep
#   - Checks if values stay within bounds during a test
#   - Detects transitions (e.g. state went from STANDBY → BRAKING)
#   - Flags violations (e.g. brake demand exceeded max allowed)
#
# In CANoe (Vector), you'd use "Signal Observers" or "Test Feature Set".
# In dSPACE, you'd use "Data Capture" or "Experiment Automation".
# =============================================================================

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

log = logging.getLogger(__name__)


@dataclass
class SignalSample:
    """One recorded sample of a signal at a point in time."""
    time_ms: int
    value: float


@dataclass
class MonitorResult:
    """Summary of what a monitor observed during a test."""
    signal_name: str
    samples: List[SignalSample] = field(default_factory=list)
    violations: List[str] = field(default_factory=list)
    transitions: List[Tuple[int, float, float]] = field(default_factory=list)
    # transitions = [(time_ms, from_value, to_value), ...]

    @property
    def passed(self) -> bool:
        return len(self.violations) == 0

    @property
    def min_value(self) -> Optional[float]:
        if self.samples:
            return min(s.value for s in self.samples)
        return None

    @property
    def max_value(self) -> Optional[float]:
        if self.samples:
            return max(s.value for s in self.samples)
        return None

    @property
    def values(self) -> List[float]:
        return [s.value for s in self.samples]

    @property
    def timestamps(self) -> List[int]:
        return [s.time_ms for s in self.samples]


class SignalMonitor:
    """
    Monitors one or more CAN signals during a test run.

    Usage:
        monitor = SignalMonitor(hil)
        monitor.watch("AEB_BRAKE_DEMAND", min_val=0, max_val=100)
        monitor.start()
        ... run test scenario ...
        results = monitor.stop()
    """

    def __init__(self, hil_interface):
        self.hil = hil_interface
        self._watched_signals = {}   # signal_name -> {min, max, last_value}
        self._results = {}           # signal_name -> MonitorResult
        self._active = False

    def watch(self, signal_name: str,
              min_val: Optional[float] = None,
              max_val: Optional[float] = None):
        """
        Register a signal to watch.

        Args:
            signal_name: CAN signal key to monitor
            min_val:     If set, flag a violation if value drops below this
            max_val:     If set, flag a violation if value goes above this
        """
        self._watched_signals[signal_name] = {
            "min": min_val,
            "max": max_val,
            "last_value": None
        }
        self._results[signal_name] = MonitorResult(signal_name=signal_name)
        log.debug(f"Watching signal: {signal_name} [{min_val} - {max_val}]")

    def sample(self):
        """
        Take one sample of all watched signals.
        Call this at each HIL timestep.

        In real HIL, this would be triggered by a hardware interrupt
        at exactly 20ms intervals.
        """
        if not self._active:
            return

        t = self.hil.elapsed_ms

        for sig_name, cfg in self._watched_signals.items():
            value = self.hil.read_signal(sig_name)
            result = self._results[sig_name]

            # Record sample
            result.samples.append(SignalSample(time_ms=t, value=value))

            # Detect transitions (state changes)
            last = cfg["last_value"]
            if last is not None and value != last:
                result.transitions.append((t, last, value))
                log.debug(f"TRANSITION {sig_name}: {last} → {value} @ {t}ms")

            # Check bounds violations
            if cfg["min"] is not None and value < cfg["min"]:
                msg = f"{sig_name} = {value} below minimum {cfg['min']} at {t}ms"
                result.violations.append(msg)
                log.warning(f"VIOLATION: {msg}")

            if cfg["max"] is not None and value > cfg["max"]:
                msg = f"{sig_name} = {value} above maximum {cfg['max']} at {t}ms"
                result.violations.append(msg)
                log.warning(f"VIOLATION: {msg}")

            cfg["last_value"] = value

    def start(self):
        """Begin monitoring."""
        self._active = True
        log.info(f"Monitor started — watching {list(self._watched_signals.keys())}")

    def stop(self) -> dict:
        """Stop monitoring and return results dict."""
        self._active = False
        log.info("Monitor stopped.")
        return self._results

    def get_first_transition_time(self, signal_name: str,
                                   to_value: float) -> Optional[int]:
        """
        Find the first time a signal transitioned TO a specific value.
        Useful for measuring response time.

        e.g. "When did AEB_SYSTEM_STATE first reach BRAKING (4)?"
        """
        result = self._results.get(signal_name)
        if not result:
            return None
        for t, from_v, to_v in result.transitions:
            if to_v == to_value:
                return t
        return None
