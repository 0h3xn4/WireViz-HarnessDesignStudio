#!/bin/sh
# Build everything for a harness project and stop at the first problem.
# Usage: sh build.sh PROJECT_FOLDER
#
# Exit codes of every `harness` command: 0 ok, 1 the project has errors or a step is blocked,
# 2 usage error or unreadable project. `set -e` makes this script stop on any non-zero code.
set -eu

DIR="${1:?usage: sh build.sh PROJECT_FOLDER}"

harness check "$DIR"       # errors, leftover Git merge markers, released harnesses that were edited
harness generate "$DIR"    # make or update the harnesses (not saved if there are errors)
harness verify "$DIR"      # independent check of the result against the interfaces
REPORT="$(mktemp)"
harness drc "$DIR" > "$REPORT" || {
    # exit 1 means unwaived errors; the report says which
    cat "$REPORT"
    rm -f "$REPORT"
    exit 1
}
rm -f "$REPORT"
harness export "$DIR"      # drawings, tables and exports, verified before they are written
harness verify "$DIR" --outputs
echo "build ok: $DIR/outputs"
