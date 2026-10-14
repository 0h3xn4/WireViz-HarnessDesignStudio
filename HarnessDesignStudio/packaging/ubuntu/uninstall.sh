#!/bin/sh
# Remove what install.sh installed. Usage: ./uninstall.sh [--prefix DIR] [--system]
set -eu
mode=user
prefix=""
prefix_set=0
while [ $# -gt 0 ]; do
  case "$1" in
    --system) mode=system ;;
    --prefix) [ $# -ge 2 ] || { echo "--prefix needs a folder" >&2; exit 2; }; shift; prefix="$1"; prefix_set=1 ;;
    -h|--help) sed -n '2p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done
if [ "$prefix_set" = 1 ] && [ -z "$prefix" ]; then
  echo "--prefix needs a folder name, not an empty text" >&2; exit 2
fi
if [ -z "$prefix" ]; then
  if [ "$mode" = system ]; then prefix=/usr/local/lib/harness-design-studio; else prefix="${HOME}/.local/opt/harness-design-studio"; fi
fi
case "$prefix" in /*) ;; *) prefix="$(pwd)/$prefix" ;; esac
prefix=$(printf '%s' "$prefix" | sed 's://*:/:g; s:/$::')
if [ "$mode" = system ]; then
  bindir=/usr/local/bin; appdir=/usr/share/applications; icondir=/usr/share/icons/hicolor/scalable/apps
else
  base="${XDG_DATA_HOME:-$HOME/.local/share}"
  bindir="${HOME}/.local/bin"; appdir="$base/applications"; icondir="$base/icons/hicolor/scalable/apps"
fi
if [ -n "${HARNESS_INSTALL_ROOT:-}" ]; then
  bindir="$HARNESS_INSTALL_ROOT/bin"; appdir="$HARNESS_INSTALL_ROOT/share/applications"; icondir="$HARNESS_INSTALL_ROOT/share/icons"
fi
removed=0
marker="$prefix/.harness-design-studio-install"
if [ ! -f "$marker" ]; then   # a folder this installer did not make is never touched
  for item in harness-design-studio-gui harness-design-studio _internal cli LICENSES; do   # the second is the program file of 1.0.0
    if [ -e "$prefix/$item" ] || [ -L "$prefix/$item" ]; then
      echo "$prefix/$item was not installed by this installer (no .harness-design-studio-install file); not touching it." >&2
      exit 1
    fi
  done
fi
# remove a link only if it points into this install; never delete a program that is not ours
remove_link() {   # NAME TARGET...  (the last targets are the links that version 1.0.0 made)
  name=$1; shift
  [ -L "$bindir/$name" ] || return 0
  current=$(readlink "$bindir/$name")
  for target in "$@"; do
    if [ "$current" = "$target" ]; then rm -f "$bindir/$name"; removed=1; return 0; fi
  done
}
remove_link harness-design-studio "$prefix/cli/harness-design-studio" "$prefix/harness-design-studio"
remove_link harness-design-studio-gui "$prefix/harness-design-studio-gui"
remove_link harness "$prefix/cli/harness-design-studio" "$prefix/cli/harness"
# the launcher and icon are shared by all installs: remove them only when they belong to this one
# (the text also matches the launcher of 1.0.0, which pointed at $prefix/harness-design-studio)
desktop="$appdir/harness-design-studio.desktop"
if [ -e "$desktop" ] && grep -qF -- "$prefix/harness-design-studio" "$desktop" 2>/dev/null; then
  rm -f "$desktop"; removed=1
  [ -e "$icondir/harness-design-studio.svg" ] && rm -f "$icondir/harness-design-studio.svg"
elif [ ! -e "$desktop" ] && [ -e "$icondir/harness-design-studio.svg" ]; then
  rm -f "$icondir/harness-design-studio.svg"; removed=1
fi
# only what the installer listed in its marker file; anything else in the folder stays
if [ -n "$prefix" ] && [ "$prefix" != "/" ]; then
  if [ -f "$marker" ]; then
    while IFS= read -r item; do
      case "$item" in
        harness-design-studio-gui|harness-design-studio|_internal|cli|LICENSES)
          [ -e "$prefix/$item" ] && { rm -rf "${prefix:?}/$item"; removed=1; } ;;
      esac
    done < "$marker"
    rm -f "$marker"; removed=1
    rmdir "$prefix" 2>/dev/null || true
  fi
fi
if [ "$removed" = 1 ]; then
  echo "Removed. Your projects are not touched."
else
  echo "Nothing to remove: Harness Design Studio is not installed there (looked in $prefix)."
fi
