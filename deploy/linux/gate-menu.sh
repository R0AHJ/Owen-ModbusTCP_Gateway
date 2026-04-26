#!/usr/bin/env bash
set -euo pipefail

APP_DIR="@APP_DIR@"
CONFIG_PATH="@CONFIG_DIR@/owen_config.json"

if [[ ! -x "${APP_DIR}/.venv/bin/python" ]]; then
  echo "python venv not found: ${APP_DIR}/.venv/bin/python" >&2
  exit 1
fi

export PYTHONPATH="${APP_DIR}"
exec "${APP_DIR}/.venv/bin/python" -m owen_gateway config menu --config "${CONFIG_PATH}"
