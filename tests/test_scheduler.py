import threading
from typing import List

import subprocess

from pyctuator.testing.scheduler import TestRunScheduler


def test_scheduler_spawns_and_invokes_pytest(tmp_path):
    called = threading.Event()

    def fake_run(cmd, check=False):  # noqa: ARG001 - signature for subprocess.run
        if cmd[0] == "pytest":
            called.set()
        return subprocess.CompletedProcess(cmd, 0)

    scheduler = TestRunScheduler(0.1, None, tmp_path, subprocess_run=fake_run)
    scheduler.start()
    assert called.wait(1), "pytest was not invoked by scheduler"
    scheduler.stop()


def test_subprocess_failure_does_not_crash(tmp_path):
    def failing_run(cmd, check=False):  # noqa: ARG001 - signature for subprocess.run
        return subprocess.CompletedProcess(cmd, 1)

    scheduler = TestRunScheduler(0.1, None, tmp_path, subprocess_run=failing_run)
    # Should not raise even though return code indicates failure
    scheduler.run_tests()


def test_artifacts_and_upload(tmp_path):
    def fake_run(cmd, check=False):  # noqa: ARG001 - signature for subprocess.run
        (tmp_path / "coverage.json").write_text("{}", encoding="utf-8")
        (tmp_path / "test_report.json").write_text("{}", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0)

    posts: List[dict] = []

    def fake_post(url, json, timeout):  # noqa: ARG001 - signature for requests.post
        posts.append(json)
        class Resp:
            ok = True
        return Resp()

    scheduler = TestRunScheduler(
        0.1,
        "http://server/upload",
        tmp_path,
        subprocess_run=fake_run,
        post=fake_post,
    )
    scheduler.run_tests()

    assert (tmp_path / "coverage.json").exists()
    assert (tmp_path / "test_report.json").exists()
    assert posts, "expected a POST request to be attempted"
