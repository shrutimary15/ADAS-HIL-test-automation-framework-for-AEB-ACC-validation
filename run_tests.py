#!/usr/bin/env python3
# =============================================================================
# run_tests.py — Master Test Runner
# =============================================================================
# This is the ENTRY POINT for the entire test suite.
#
# In a real HIL project, this script would be called by:
#   - Jenkins CI: `python run_tests.py --suite regression`
#   - A nightly cron job on the HIL bench PC
#   - A test engineer manually running a specific campaign
#
# What it does:
#   1. Loads config
#   2. Discovers and runs all tests
#   3. Collects results with timing
#   4. Generates the HTML report
#   5. Exits with code 0 (pass) or 1 (fail) — CI/CD friendly
# =============================================================================

import os
import sys
import time
import yaml
import importlib
import traceback
import inspect
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from reports.report_generator import generate_report

# ── Requirement ID mapping ─────────────────────────────────────────────────
# In real projects this would be in a database (DOORS/Polarion)
# Here we embed it in function docstrings and parse it out
REQ_MAP = {
    "test_aeb_activates_within_ttc_threshold":    "REQ_AEB_001",
    "test_aeb_brake_demand_magnitude":             "REQ_AEB_002",
    "test_aeb_inactive_above_speed_limit":         "REQ_AEB_003",
    "test_aeb_inactive_below_speed_limit":         "REQ_AEB_004",
    "test_aeb_no_false_activation_clear_road":     "REQ_AEB_005",
    "test_aeb_response_time_within_150ms":         "REQ_AEB_010",
    "test_aeb_prefill_before_brake":               "REQ_AEB_011",
    "test_acc_active_in_speed_range":              "REQ_ACC_001",
    "test_acc_standby_below_speed_range":          "REQ_ACC_002",
    "test_acc_maintains_follow_gap":               "REQ_ACC_003",
    "test_acc_speed_tracking_accuracy":            "REQ_ACC_004",
    "test_acc_responds_to_cut_in":                 "REQ_ACC_010",
    "test_acc_gap_too_close_triggers_intervention":"REQ_ACC_011",
    "test_acc_signal_continuity_during_operation": "REQ_ACC_012",
    "test_acc_does_not_interfere_with_aeb":        "REQ_ACC_013",
}


def load_config():
    cfg_path = os.path.join(os.path.dirname(__file__), "config/test_config.yaml")
    with open(cfg_path) as f:
        return yaml.safe_load(f)


def discover_tests(test_modules):
    """
    Find all test methods in all test classes.
    Returns list of (module_name, class_name, class_instance, method_name, method)
    """
    tests = []
    for mod_name, module in test_modules:
        for class_name, cls in inspect.getmembers(module, inspect.isclass):
            if not class_name.startswith("Test"):
                continue
            instance = cls()
            for method_name, method in inspect.getmembers(instance, inspect.ismethod):
                if method_name.startswith("test_"):
                    tests.append((mod_name, class_name, instance, method_name, method))
    return tests


def run_single_test(mod_name, class_name, instance, method_name, method, config):
    """
    Run one test and return a result dict.
    Handles pass, fail (AssertionError), and unexpected errors separately.
    """
    from framework.hil_interface import HILInterface

    # Create fresh HIL instance for each test (like pytest fixture)
    hil = HILInterface(config)
    hil.connect()

    start = time.time()
    result = {
        "test_name": method_name,
        "module": mod_name,
        "class": class_name,
        "req_id": REQ_MAP.get(method_name, "—"),
        "status": "PASS",
        "message": "",
        "duration_ms": 0,
    }

    try:
        # Inject config and hil into test (mimics pytest fixtures)
        sig = inspect.signature(method)
        kwargs = {}
        if "hil" in sig.parameters:
            kwargs["hil"] = hil
        if "config" in sig.parameters:
            kwargs["config"] = config

        method(**kwargs)
        result["status"] = "PASS"

    except AssertionError as e:
        result["status"] = "FAIL"
        # Get just the meaningful part of the assertion message
        result["message"] = str(e).split("\n")[0][:200]

    except Exception as e:
        result["status"] = "ERROR"
        result["message"] = f"{type(e).__name__}: {str(e)[:150]}"

    finally:
        hil.disconnect()
        result["duration_ms"] = (time.time() - start) * 1000

    return result


def print_live_result(result):
    """Print result to console as tests run (like pytest's live output)."""
    icons = {"PASS": "✓", "FAIL": "✗", "ERROR": "⚠"}
    colors = {"PASS": "\033[92m", "FAIL": "\033[91m", "ERROR": "\033[93m"}
    reset = "\033[0m"

    icon = icons.get(result["status"], "?")
    color = colors.get(result["status"], "")
    req = result.get("req_id", "—")
    name = result["test_name"].replace("test_", "").replace("_", " ")
    dur = result["duration_ms"]

    print(f"  {color}{icon} {result['status']}{reset}  [{req}] {name}  ({dur:.0f}ms)")
    if result["message"]:
        print(f"       → {result['message']}")


def main():
    print("\n" + "="*65)
    print("ADAS HIL TEST FRAMEWORK")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*65)

    config = load_config()

    # Import test modules
    print("\n📂 Discovering tests...")
    test_module_names = ["tests.test_aeb", "tests.test_acc"]
    test_modules = []
    for name in test_module_names:
        mod = importlib.import_module(name)
        test_modules.append((name.split(".")[-1], mod))

    tests = discover_tests(test_modules)
    print(f"   Found {len(tests)} test cases across {len(test_modules)} modules\n")

    # Run all tests
    all_results = []
    current_module = None

    for mod_name, class_name, instance, method_name, method in tests:
        if mod_name != current_module:
            print(f"\n📋 {mod_name.upper()}")
            current_module = mod_name

        result = run_single_test(
            mod_name, class_name, instance, method_name, method, config
        )
        all_results.append(result)
        print_live_result(result)

    # Summary
    total = len(all_results)
    passed = sum(1 for r in all_results if r["status"] == "PASS")
    failed = sum(1 for r in all_results if r["status"] == "FAIL")
    errors = sum(1 for r in all_results if r["status"] == "ERROR")
    pass_rate = (passed / total * 100) if total > 0 else 0
    threshold = config["environment"]["pass_threshold_percent"]
    suite_pass = pass_rate >= threshold

    print("\n" + "="*65)
    print(f"  RESULTS: {passed}/{total} passed  ({pass_rate:.0f}%)")
    print(f"  Passed: {passed}  Failed: {failed}  Errors: {errors}")
    print(f"  Suite: {'✓ PASS' if suite_pass else '✗ FAIL'} (threshold: {threshold}%)")
    print("="*65)

    # Generate HTML report
    report_path = os.path.join(
        os.path.dirname(__file__),
        "reports",
        f"hil_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    )
    generate_report(all_results, config, report_path)

    # Exit code for CI/CD — 0 = pass, 1 = fail
    sys.exit(0 if suite_pass else 1)


if __name__ == "__main__":
    main()
