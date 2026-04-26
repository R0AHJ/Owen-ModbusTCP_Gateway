#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-owen-gateway}"

if ! systemctl is-active --quiet "${SERVICE_NAME}"; then
  echo "${SERVICE_NAME} is not active"
  exit 0
fi

main_pid="$(systemctl show -p MainPID --value "${SERVICE_NAME}")"
if [[ -z "${main_pid}" || "${main_pid}" == "0" ]]; then
  echo "${SERVICE_NAME} has no main pid"
  exit 0
fi

fd_listing="$(ls -l "/proc/${main_pid}/fd" 2>/dev/null || true)"
serial_lines="$(printf '%s\n' "${fd_listing}" | grep -E '/dev/(tty|serial)' || true)"

if [[ -z "${serial_lines}" ]]; then
  echo "no serial file descriptors found for ${SERVICE_NAME}, restarting"
  systemctl restart "${SERVICE_NAME}"
  exit 0
fi

if printf '%s\n' "${serial_lines}" | grep -q '(deleted)'; then
  echo "stale serial file descriptor detected for ${SERVICE_NAME}, restarting"
  systemctl restart "${SERVICE_NAME}"
  exit 0
fi

echo "${SERVICE_NAME} serial descriptors are healthy"
