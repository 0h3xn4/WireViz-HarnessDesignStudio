#!/bin/sh
# Install the package on a CLEAN Ubuntu without network and run its self-test.
# Usage (on a machine with Docker, after building the .deb):
#   packaging/ubuntu/container/clean-machine-test.sh 24.04 dist/harness-design-studio_<version>_amd64.deb
# The image is prepared with the runtime libraries while online; the test itself runs with --network none.
set -eu
release="${1:?usage: clean-machine-test.sh UBUNTU_RELEASE PATH_TO_DEB}"; deb="${2:?usage: clean-machine-test.sh UBUNTU_RELEASE PATH_TO_DEB}"
case "$deb" in /*) ;; *) deb="$(pwd)/$deb" ;; esac
image="harness-clean:$release"
docker build -t "$image" - <<DOCKER
FROM ubuntu:$release
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    libegl1 libgl1 libxkbcommon0 libxkbcommon-x11-0 libfontconfig1 libdbus-1-3 libxcb-cursor0 \
    libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 \
 && rm -rf /var/lib/apt/lists/*
DOCKER
docker run --rm --network none -e QT_QPA_PLATFORM=offscreen -v "$deb":/pkg.deb:ro "$image" sh -c '
  dpkg -i /pkg.deb && harness-design-studio --version && harness --version && harness-design-studio-gui --selftest && echo CLEAN-MACHINE-TEST-OK'
