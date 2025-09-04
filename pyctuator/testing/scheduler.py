"""Test run scheduler for Pyctuator.

This module provides :class:`TestRunScheduler` which can be used to
periodically execute the project's test-suite.  The tests are executed
using ``pytest`` and the resulting artifacts are stored under the given
``results_path``.  Optionally the results can be uploaded to a remote
HTTP server.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import requests

# We intentionally import subprocess only after typing to ease testing
import subprocess  # noqa: E402  (imported late on purpose)


class TestRunScheduler:
    """Periodically execute the project's tests in a background thread.

    The scheduler runs ``pytest`` in a subprocess and stores the JSON
    coverage report and the JSON test report under ``results_path``.  If an
    ``upload_url`` is supplied, the two reports are merged and uploaded to
    the server using an HTTP POST request.  Failures while running the
    tests or while uploading the results never raise exceptions to the
    caller.
    """

    __test__ = False  # prevent pytest from collecting this class as a test

    def __init__(
        self,
        interval_seconds: int,
        upload_url: Optional[str],
        results_path: Path,
        subprocess_run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
        post: Callable[..., requests.Response] = requests.post,
    ) -> None:
        self.interval_seconds = interval_seconds
        self.upload_url = upload_url
        self.results_path = Path(results_path)
        self._subprocess_run = subprocess_run
        self._post = post
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start the scheduler in a daemon thread."""
        if self._thread is None:
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Stop the scheduler and wait for the thread to finish."""
        if self._thread is not None:
            self._stop_event.set()
            self._thread.join(timeout=self.interval_seconds + 1)
            self._thread = None
            self._stop_event.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            self.run_tests()
            # Wait for interval or until stop event is set
            self._stop_event.wait(self.interval_seconds)

    def run_tests(self) -> None:
        """Execute the tests once and optionally upload the results."""
        self.results_path.mkdir(parents=True, exist_ok=True)
        coverage_file = self.results_path / "coverage.json"
        report_file = self.results_path / "test_report.json"
        cmd = [
            "pytest",
            "--cov=.",
            f"--cov-report=json:{coverage_file}",
            "--json-report",
            f"--json-report-file={report_file}",
        ]
        # Execute tests but never raise an exception
        self._subprocess_run(cmd, check=False)

        if self.upload_url:
            payload = {}
            try:
                if coverage_file.exists():
                    with coverage_file.open("r", encoding="utf-8") as cov_fd:
                        payload["coverage"] = json.load(cov_fd)
                if report_file.exists():
                    with report_file.open("r", encoding="utf-8") as rep_fd:
                        payload["report"] = json.load(rep_fd)

                self._post_with_retry(payload)
            except Exception:
                # Swallow all exceptions – the scheduler should never crash the app
                pass

    def _post_with_retry(self, payload: dict) -> None:
        for _ in range(3):
            try:
                response = self._post(self.upload_url, json=payload, timeout=10)
                if response.ok:
                    return
            except Exception:
                time.sleep(1)
        # Silently give up after retries
        return
