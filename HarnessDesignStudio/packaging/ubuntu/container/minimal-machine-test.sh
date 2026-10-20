#!/bin/sh
# Run the Linux tarball on the SMALLEST machine it is meant for: a bare Ubuntu with no Python and only
# the three libraries the package cannot carry (libgl1, libegl1, libxcb1), plus a virtual screen.
# It must start there, and with a library missing it must say so in words (D-167).
# Usage (on a machine with Docker, after building the tarball):
#   packaging/ubuntu/container/minimal-machine-test.sh dist/harness-design-studio-<version>-linux-x86_64.tar.gz
# The image is prepared while online; the test itself runs with --network none.
set -eu
tarball="${1:?usage: minimal-machine-test.sh PATH_TO_TARBALL}"
case "$tarball" in /*) ;; *) tarball="$(pwd)/$tarball" ;; esac
image="harness-minimal:24.04"
docker build -t "$image" - <<'DOCKER'
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libegl1 libxcb1 xvfb xauth \
 && rm -rf /var/lib/apt/lists/*
DOCKER
docker run --rm --network none -v "$tarball":/pkg.tar.gz:ro "$image" sh -eu -c '
  if command -v python3 >/dev/null 2>&1; then echo "this image must have no Python"; exit 1; fi
  mkdir /work && cd /work && tar xzf /pkg.tar.gz && cd harness-design-studio
  ./harness-design-studio-gui --check-system
  QT_QPA_PLATFORM=offscreen ./harness-design-studio-gui --selftest
  ./cli/harness-design-studio --version
  # the editor opens a real window and keeps running (timeout ends it with 124)
  xvfb-run -a sh -c "timeout 10 ./harness-design-studio-gui >/tmp/gui.txt 2>&1; test \$? -eq 124"
  # with a library gone it says what is missing and the command that fixes it
  dpkg --purge --force-depends libegl1 >/dev/null 2>&1
  rc=0
  ./harness-design-studio-gui --check-system >/tmp/check.txt 2>&1 || rc=$?
  cat /tmp/check.txt
  test "$rc" -eq 3
  grep -q "sudo apt install libegl1" /tmp/check.txt
  echo MINIMAL-MACHINE-TEST-OK'
