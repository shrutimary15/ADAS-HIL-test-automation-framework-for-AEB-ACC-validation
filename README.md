# ADAS HIL Test Automation Framework

A Python-based Hardware-in-the-Loop (HIL) test automation framework for validating
AEB (Automatic Emergency Braking) and ACC (Adaptive Cruise Control) ADAS features.

Simulates the test patterns used on real HIL benches (dSPACE ControlDesk,
NI VeriStand) — including CAN signal injection, ECU response monitoring,
ISO 26262-traceable test cases, and automated HTML report generation.

![Python](https://img.shields.io/badge/Python-3.8+-blue)
![Tests](https://img.shields.io/badge/Tests-15-blue)
![Pass Rate](https://img.shields.io/badge/Pass%20Rate-93%25-brightgreen)
![Standard](https://img.shields.io/badge/Standard-ISO%2026262-orange)

---

## Features

- **CAN signal simulation** — models radar, vehicle speed, and ECU output signals
  using a Python representation of a DBC signal database
- **HIL interface layer** — injectable/readable signal API mirroring dSPACE and NI VeriStand patterns
- **Signal monitoring** — records signals over time, detects bound violations and state transitions
- **15 test cases** across AEB and ACC, each traceable to a requirement ID (REQ_AEB_xxx / REQ_ACC_xxx)
- **ISO 26262 timing tests** — validates ASIL-B 150ms response time requirement for AEB
- **HTML report generation** — professional pass/fail report with requirement traceability
- **CI/CD ready** — exits with code 0 (pass) or 1 (fail) for Jenkins/GitHub Actions integration

---

## Requirements

- Python 3.8+
- pytest
- pyyaml

Install dependencies:

```bash
pip install pytest pyyaml
```

---

## Running the Framework

```bash
python run_tests.py
```

The runner will discover all tests, execute them with live console output,
and write an HTML report to the `reports/` folder.

To run a specific test module:

```bash
pytest tests/test_aeb.py -v
pytest tests/test_acc.py -v
```

---

## Test Coverage

| ID | Test | Feature | Requirement |
|---|---|---|---|
| REQ_AEB_001 | AEB activates within TTC threshold | AEB | ISO 22737 |
| REQ_AEB_002 | Brake demand magnitude at close range | AEB | Euro NCAP |
| REQ_AEB_003 | Inactive above 80 kph | AEB | Regulatory |
| REQ_AEB_004 | Inactive below 10 kph | AEB | Regulatory |
| REQ_AEB_005 | No false activation on clear road | AEB | ISO 22737 |
| REQ_AEB_010 | Response time within 150ms | AEB | ISO 26262 ASIL-B |
| REQ_AEB_011 | Brake prefill before full braking | AEB | System design |
| REQ_ACC_001 | Active within 30–160 kph range | ACC | System spec |
| REQ_ACC_002 | Standby below 30 kph | ACC | System spec |
| REQ_ACC_003 | Maintains 20–80m following gap | ACC | Euro NCAP |
| REQ_ACC_004 | Speed tracking within ±2 kph | ACC | System spec |
| REQ_ACC_010 | Responds to cut-in vehicle | ACC | Euro NCAP |
| REQ_ACC_011 | Intervenes when gap too close | ACC | Safety |
| REQ_ACC_012 | No signal dropout over 2 seconds | ACC | System integrity |
| REQ_ACC_013 | Does not conflict with AEB braking | ACC/AEB | Feature integration |

---

## Real-World Equivalents

This framework mirrors the patterns used on production HIL benches:

| This framework | Real HIL tooling |
|---|---|
| `hil_interface.py` | dSPACE ControlDesk Python API / NI VeriStand ClientAPI |
| `can/signals.py` | Vector DBC file parsed via CANdb++ |
| `signal_monitor.py` | CANoe Signal Observer / dSPACE Data Capture |
| `run_tests.py` | Jenkins pipeline test step |
| HTML report | Jira Xray / Allure / pytest-html |

---

## Standards Compliance

- **ISO 26262** — requirement traceability and ASIL-B timing validation
- **ISO 22737** — AEB trigger thresholds and speed envelope
- **Euro NCAP** — AEB and ACC test scenario parameters

---

