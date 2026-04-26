#!/usr/bin/env bash
set -euo pipefail

APP_DIR="@APP_DIR@"
CONFIG_PATH="@CONFIG_DIR@/owen_config.json"
SERVICE_NAME="${SERVICE_NAME:-owen-gateway}"

PYTHON_BIN="${APP_DIR}/.venv/bin/python"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "python venv not found: ${PYTHON_BIN}" >&2
  exit 1
fi

export PYTHONPATH="${APP_DIR}"

echo "== systemd =="
systemctl status "${SERVICE_NAME}" --no-pager -l || true
echo

echo "== serial =="
"${PYTHON_BIN}" -m owen_gateway config list-serial || true
echo

echo "== config =="
if [[ -f "${CONFIG_PATH}" ]]; then
  "${PYTHON_BIN}" -m owen_gateway config list-config --config "${CONFIG_PATH}" || true
else
  echo "config not found: ${CONFIG_PATH}"
fi
echo

echo "== modbus =="
"${PYTHON_BIN}" - <<'PY'
from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient("127.0.0.1", port=15020)
print("connect", client.connect())
try:
    response = client.read_holding_registers(address=1, count=10, slave=1)
    print("service_hr1_10", getattr(response, "registers", None))
finally:
    client.close()
PY
echo

echo "== recent logs =="
journalctl -u "${SERVICE_NAME}" -n 30 --no-pager || true
