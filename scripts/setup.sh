#!/bin/sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
JOB_UTILS_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

case "$(uname -s)" in
  Darwin)
    SETUP_PLATFORM=macos
    ;;
  Linux)
    if [ -r /etc/os-release ] && /usr/bin/grep -qi '^[[:space:]]*ID=ubuntu' /etc/os-release; then
      SETUP_PLATFORM=ubuntu
    else
      echo "job-utils setup: this Linux distribution is not Ubuntu" >&2
      exit 1
    fi
    ;;
  *)
    echo "job-utils setup: supported hosts are macOS and Ubuntu" >&2
    exit 1
    ;;
esac

if [ -n "${JOBUTILS_PYTHON:-}" ]; then
  PYTHON_COMMAND=$JOBUTILS_PYTHON
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_COMMAND=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON_COMMAND=python
else
  echo "job-utils setup: Python 3.8 or newer was not found" >&2
  exit 1
fi

if ! "$PYTHON_COMMAND" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)' >/dev/null 2>&1; then
  echo "job-utils setup: Python 3.8 or newer is required" >&2
  exit 1
fi

VENV_ROOT="$JOB_UTILS_ROOT/.venv"
VENV_PYTHON="$VENV_ROOT/bin/python"
if [ ! -x "$VENV_PYTHON" ]; then
  echo "job-utils setup: creating $VENV_ROOT"
  "$PYTHON_COMMAND" -m venv "$VENV_ROOT"
fi

echo "job-utils setup: installing the local package"
"$VENV_PYTHON" -m pip install --editable "$JOB_UTILS_ROOT"
exec "$VENV_PYTHON" -m jobutils setup init \
  --job-utils-root "$JOB_UTILS_ROOT" \
  --platform "$SETUP_PLATFORM" \
  "$@"
