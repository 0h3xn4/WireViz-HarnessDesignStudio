#!/bin/sh
# Install Harness Design Studio for the current user (no administrator rights), or system-wide with --system.
# Usage: ./install.sh [--prefix DIR] [--system]
set -eu
here=$(cd "$(dirname "$0")" && pwd)
mode=user
prefix=""
prefix_set=0
while [ $# -gt 0 ]; do
  case "$1" in
    --system) mode=system ;;
    --prefix) [ $# -ge 2 ] || { echo "--prefix needs a folder" >&2; exit 2; }; shift; prefix="$1"; prefix_set=1 ;;
    -h|--help) sed -n '2,3p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done
if [ ! -x "$here/harness-design-studio-gui" ] || [ ! -d "$here/_internal" ]; then
  echo "This folder ($here) has no built program, so there is nothing to install." >&2
  echo "Run install.sh from the unpacked harness-design-studio-<version>-linux-<arch>.tar.gz," >&2
  echo "or install the .deb. To build the package from source: python -m tools.build_installer" >&2
  echo "(it writes dist/harness-design-studio/ with this script inside)." >&2
  exit 1
fi
if [ "$prefix_set" = 1 ] && [ -z "$prefix" ]; then
  echo "--prefix needs a folder name, not an empty text" >&2; exit 2
fi
if [ -z "$prefix" ]; then
  # /opt/harness-design-studio belongs to the .deb; a local system install must not touch its files
  if [ "$mode" = system ]; then prefix=/usr/local/lib/harness-design-studio; else prefix="${HOME}/.local/opt/harness-design-studio"; fi
fi
case "$prefix" in /*) ;; *) prefix="$(pwd)/$prefix" ;; esac   # links and the launcher need an absolute path
prefix=$(printf '%s' "$prefix" | sed 's://*:/:g; s:/$::')
if [ -z "$prefix" ]; then
  echo "The install folder must not be the root folder." >&2
  exit 2
fi
# compare real paths, so a link to the unpacked folder is caught too
here_real=$(cd "$here" && pwd -P)
if [ -d "$prefix" ]; then prefix_real=$(cd "$prefix" && pwd -P); else prefix_real="$prefix"; fi
if [ "$prefix_real" = "$here_real" ]; then
  echo "The install folder must not be the folder the package was unpacked in." >&2
  exit 2
fi
items="harness-design-studio-gui _internal cli LICENSES"
legacy_gui="harness-design-studio"   # the program file of version 1.0.0 (now harness-design-studio-gui)
marker="$prefix/.harness-design-studio-install"
for item in $items; do   # installing would delete the package this script is running from
  case "$here_real/" in
    "$prefix_real/$item/"*)
      echo "The package is unpacked inside $prefix/$item, which the install would replace." >&2
      echo "Unpack it somewhere else (for example under /tmp) or choose another --prefix." >&2
      exit 2 ;;
  esac
done
if [ "$mode" = system ]; then
  bindir=/usr/local/bin; appdir=/usr/share/applications; icondir=/usr/share/icons/hicolor/scalable/apps
else
  base="${XDG_DATA_HOME:-$HOME/.local/share}"
  bindir="${HOME}/.local/bin"; appdir="$base/applications"; icondir="$base/icons/hicolor/scalable/apps"
fi
# --prefix with an explicit test root keeps links inside it
if [ -n "${HARNESS_INSTALL_ROOT:-}" ]; then
  bindir="$HARNESS_INSTALL_ROOT/bin"; appdir="$HARNESS_INSTALL_ROOT/share/applications"; icondir="$HARNESS_INSTALL_ROOT/share/icons"
fi
# never replace a program the user put there themselves: only links to our own programs are replaced
# (the second shape of a name is the link that version 1.0.0 made, replaced when upgrading)
is_ours() {   # LINK_TEXT SHAPE...
  target=$1; shift
  for shape in "$@"; do
    case "$target" in $shape) return 0 ;; esac
  done
  return 1
}
for pair in "harness-design-studio:*/cli/harness-design-studio:*/harness-design-studio" \
            "harness-design-studio-gui:*/harness-design-studio-gui:*/harness-design-studio-gui" \
            "harness:*/cli/harness-design-studio:*/cli/harness"; do
  name=${pair%%:*}; shapes=${pair#*:}; shape1=${shapes%%:*}; shape2=${shapes#*:}
  if [ -e "$bindir/$name" ] || [ -L "$bindir/$name" ]; then
    if [ ! -L "$bindir/$name" ]; then
      echo "$bindir/$name exists and is not a link made by this installer; not touching it." >&2
      exit 1
    fi
    if ! is_ours "$(readlink "$bindir/$name")" "$shape1" "$shape2"; then
      echo "$bindir/$name is a link to something else, not made by this installer; not touching it." >&2
      exit 1
    fi
  fi
done
# a folder this installer did not make is never replaced or removed
for item in $items; do
  if [ -e "$prefix/$item" ] || [ -L "$prefix/$item" ]; then
    if [ ! -f "$marker" ] || ! grep -qx "$item" "$marker"; then
      echo "$prefix/$item exists and was not installed by this installer; not touching it." >&2
      echo "Choose another --prefix, or move that folder away first." >&2
      exit 1
    fi
  fi
done
mkdir -p "$prefix" "$bindir" "$appdir" "$icondir"
# copy to a temporary name first, so a failed copy leaves the old install and the package intact
for item in $items; do
  [ -e "$here/$item" ] || continue
  rm -rf "${prefix:?}/.$item.new"
  cp -R --preserve=mode,timestamps "$here/$item" "$prefix/.$item.new"
  chmod -R u+rwX,go+rX,go-w "$prefix/.$item.new"
  # files belong to root in a root install, not to whoever unpacked the package
  if [ "$(id -u)" = 0 ]; then chown -hR root:root "$prefix/.$item.new"; fi
done
# an upgrade from 1.0.0: its program file is listed in the old marker and is now named -gui
legacy_old=0
if [ -f "$marker" ] && grep -qx "$legacy_gui" "$marker" && [ -f "$prefix/$legacy_gui" ] && [ ! -L "$prefix/$legacy_gui" ]; then
  legacy_old=1
fi
: > "$marker.new"
echo "# Made by install.sh of Harness Design Studio; uninstall.sh removes only the items listed here." >> "$marker.new"
for item in $items; do
  [ -e "$prefix/.$item.new" ] || continue
  rm -rf "${prefix:?}/$item"
  mv "$prefix/.$item.new" "$prefix/$item"
  echo "$item" >> "$marker.new"
done
if [ "$legacy_old" = 1 ]; then rm -f "${prefix:?}/$legacy_gui"; fi
mv "$marker.new" "$marker"
ln -sfn "$prefix/cli/harness-design-studio" "$bindir/harness-design-studio"
ln -sfn "$prefix/harness-design-studio-gui" "$bindir/harness-design-studio-gui"
ln -sfn "$prefix/cli/harness-design-studio" "$bindir/harness"   # short alias of the command line tool
# the launcher line must survive spaces and special characters in the path (desktop entry quoting)
quoted=$(printf '%s' "$prefix/harness-design-studio-gui" | sed 's/[\\"`$]/\\&/g; s/\\/\\\\/g; s/%/%%/g')
: > "$appdir/harness-design-studio.desktop"
while IFS= read -r line; do
  case "$line" in
    *@EXEC@*) line="${line%%@EXEC@*}\"$quoted\"${line#*@EXEC@}" ;;
  esac
  case "$line" in
    *@ICON@*) line="${line%%@ICON@*}harness-design-studio${line#*@ICON@}" ;;
  esac
  printf '%s\n' "$line" >> "$appdir/harness-design-studio.desktop"
done < "$here/harness-design-studio.desktop.in"
cp "$here/harness-design-studio.svg" "$icondir/harness-design-studio.svg"
echo "Installed to $prefix. Start it from the application menu or run: harness-design-studio-gui"
echo "The command line tool is harness-design-studio (the short name harness works too)."
case ":$PATH:" in
  *":$bindir:"*) ;;
  *)
    echo "Note: $bindir is not on your PATH, so the commands harness-design-studio-gui, harness-design-studio and harness are not found yet."
    echo "  Run now:     $bindir/harness-design-studio-gui"
    echo "  Fix for good: echo 'export PATH=\"$bindir:\$PATH\"' >> ~/.bashrc && . ~/.bashrc"
    echo "  (or log out and in again; Ubuntu adds ~/.local/bin at login when it exists)"
    ;;
esac
