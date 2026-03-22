#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"
. "${PROJECT_ROOT}/.venv/bin/activate"

exec python3 -m owen_gateway.probe --config owen_probe.linux.json --log-level INFO
