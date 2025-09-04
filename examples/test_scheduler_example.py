"""Minimal example demonstrating the test run scheduler.

Set ``PYCTUATOR_TEST_SCHEDULE_INTERVAL`` and optionally
``PYCTUATOR_TEST_UPLOAD_URL`` before running this script to enable the
scheduler.  The scheduler will periodically execute ``pytest`` and save
its artifacts under ``test_results``.
"""

import time

from pyctuator.endpoints import Endpoints
from pyctuator.impl.pyctuator_impl import AppDetails, AppInfo, PyctuatorImpl


# Instantiate Pyctuator which will automatically start the scheduler when
# the environment variable is configured.
pyctuator = PyctuatorImpl(
    app_info=AppInfo(app=AppDetails(name="scheduler-example")),
    pyctuator_endpoint_url="http://localhost/pyctuator",
    logfile_max_size=0,
    logfile_formatter="",  # no log file
    additional_app_info=None,
    disabled_endpoints=Endpoints.NONE,
)

# Keep the application alive for a short while so the scheduler can run.
print("Scheduler started; sleeping for 10 seconds...")
try:
    time.sleep(10)
finally:
    if pyctuator.test_scheduler:
        pyctuator.test_scheduler.stop()
