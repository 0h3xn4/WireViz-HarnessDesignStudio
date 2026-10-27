#!/bin/sh
# Run inside the 24.04 build image with the source mounted at /src: installs the pinned
# dependencies, runs the whole release checklist and leaves the packages in dist/.
set -eu
cd /src
git config --global --add safe.directory /src   # the mounted source belongs to another user
export HARNESS_REQUIRE_BROWSER=1                  # no Chromium: fail, do not skip
python3.14 -m venv /tmp/venv
. /tmp/venv/bin/activate
pip install -e ".[gui,dev]"
export QT_QPA_PLATFORM=offscreen
python -m tools.release_check
ls -l dist/*.deb dist/*.tar.gz
