import io
import json
import os
from typing import Any, Dict

import coverage
import requests

SERVER_URL_ENV_VAR = "PYCTUATOR_TEST_RESULTS_URL"


def _load_coverage_data() -> Dict[str, Any]:
    """Return coverage data as JSON, or empty dict if unavailable."""
    cov = coverage.Coverage()
    try:
        cov.load()
    except coverage.CoverageException:
        return {}

    buffer = io.StringIO()
    cov.json_report(outfile=buffer)
    buffer.seek(0)
    try:
        return json.loads(buffer.getvalue())
    except json.JSONDecodeError:
        return {}


def _load_pytest_json_report(session) -> Dict[str, Any]:
    """Return pytest-json-report contents if available."""
    report_file = getattr(session.config.option, "json_report_file", None)
    if not report_file:
        # default used by pytest-json-report
        report_file = ".report.json"
    if not os.path.isabs(report_file):
        report_file = os.path.join(str(session.config.rootpath), report_file)

    try:
        with open(report_file, "r", encoding="utf-8") as report:
            return json.load(report)
    except (OSError, json.JSONDecodeError):
        return {}


def pytest_sessionfinish(session, exitstatus):  # pylint: disable=unused-argument
    """Hook for reporting coverage and test results to a remote server."""
    server_url = os.getenv(SERVER_URL_ENV_VAR)
    if not server_url:
        return

    payload: Dict[str, Any] = {
        "coverage": _load_coverage_data(),
        "tests": _load_pytest_json_report(session),
    }

    try:
        requests.post(server_url, json=payload, timeout=10)
    except Exception:  # pylint: disable=broad-except
        # Avoid failing the test session because of reporting issues
        terminal_reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if terminal_reporter is not None:
            terminal_reporter.write_line("Failed to post test results", red=True)
