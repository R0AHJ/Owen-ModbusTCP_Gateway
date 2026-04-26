#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

if [[ "${EUID}" -eq 0 ]]; then
  RUN_AS_ROOT=()
else
  if ! command -v sudo >/dev/null 2>&1; then
    echo "sudo is required when install.sh is not run as root" >&2
    exit 1
  fi
  RUN_AS_ROOT=(sudo)
fi

APP_DIR="${APP_DIR:-/opt/owen-gateway}"
CONFIG_DIR="${CONFIG_DIR:-/etc/owen-gateway}"
SERVICE_NAME="${SERVICE_NAME:-owen-gateway}"
SERVICE_USER="${SERVICE_USER:-owen}"
SERVICE_GROUP="${SERVICE_GROUP:-dialout}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_ARGS="${VENV_ARGS:---system-site-packages}"
CONFIG_SOURCE="${CONFIG_SOURCE:-${REPO_DIR}/owen_config.linux.json}"
SERVICE_TEMPLATE="${SERVICE_TEMPLATE:-${REPO_DIR}/deploy/linux/owen-gateway.service.template}"
CONFIG_WRAPPER_TEMPLATE="${CONFIG_WRAPPER_TEMPLATE:-${REPO_DIR}/deploy/linux/gate-config.sh}"
MENU_WRAPPER_TEMPLATE="${MENU_WRAPPER_TEMPLATE:-${REPO_DIR}/deploy/linux/gate-menu.sh}"
STATUS_WRAPPER_TEMPLATE="${STATUS_WRAPPER_TEMPLATE:-${REPO_DIR}/deploy/linux/gate-status.sh}"
SHELL_PROFILE_TEMPLATE="${SHELL_PROFILE_TEMPLATE:-${REPO_DIR}/deploy/linux/owen-shell-profile.sh}"

if [[ ! -f "${REPO_DIR}/requirements.txt" ]]; then
  echo "requirements.txt not found: ${REPO_DIR}" >&2
  exit 1
fi

if [[ ! -f "${CONFIG_SOURCE}" ]]; then
  echo "config source not found: ${CONFIG_SOURCE}" >&2
  exit 1
fi

if [[ ! -f "${SERVICE_TEMPLATE}" ]]; then
  echo "service template not found: ${SERVICE_TEMPLATE}" >&2
  exit 1
fi

if [[ ! -f "${CONFIG_WRAPPER_TEMPLATE}" ]]; then
  echo "config wrapper template not found: ${CONFIG_WRAPPER_TEMPLATE}" >&2
  exit 1
fi

if [[ ! -f "${MENU_WRAPPER_TEMPLATE}" ]]; then
  echo "menu wrapper template not found: ${MENU_WRAPPER_TEMPLATE}" >&2
  exit 1
fi

if [[ ! -f "${STATUS_WRAPPER_TEMPLATE}" ]]; then
  echo "status wrapper template not found: ${STATUS_WRAPPER_TEMPLATE}" >&2
  exit 1
fi

if [[ ! -f "${SHELL_PROFILE_TEMPLATE}" ]]; then
  echo "shell profile template not found: ${SHELL_PROFILE_TEMPLATE}" >&2
  exit 1
fi

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "python binary not found: ${PYTHON_BIN}" >&2
  exit 1
fi

echo "Installing gateway to ${APP_DIR}"
"${RUN_AS_ROOT[@]}" install -d -m 0755 "${APP_DIR}" "${CONFIG_DIR}"

if ! getent group "${SERVICE_GROUP}" >/dev/null 2>&1; then
  "${RUN_AS_ROOT[@]}" groupadd --system "${SERVICE_GROUP}"
fi

if ! id -u "${SERVICE_USER}" >/dev/null 2>&1; then
  "${RUN_AS_ROOT[@]}" useradd \
    --system \
    --gid "${SERVICE_GROUP}" \
    --home-dir "${APP_DIR}" \
    --create-home \
    --shell /usr/sbin/nologin \
    "${SERVICE_USER}"
fi

# Keep the service account attached to the serial device group across repeated
# installs even when the primary group already existed.
"${RUN_AS_ROOT[@]}" usermod -a -G "${SERVICE_GROUP}" "${SERVICE_USER}"

"${RUN_AS_ROOT[@]}" rsync -a \
  --delete \
  --exclude '.git' \
  --exclude '.idea' \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude 'tmp_*' \
  --exclude 'archive' \
  "${REPO_DIR}/" "${APP_DIR}/"

"${RUN_AS_ROOT[@]}" "${PYTHON_BIN}" -m venv ${VENV_ARGS} "${APP_DIR}/.venv"
"${RUN_AS_ROOT[@]}" "${APP_DIR}/.venv/bin/pip" install --upgrade pip
"${RUN_AS_ROOT[@]}" "${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

"${RUN_AS_ROOT[@]}" install -m 0644 "${CONFIG_SOURCE}" "${CONFIG_DIR}/owen_config.json"

TMP_UNIT="$(mktemp)"
sed \
  -e "s|@APP_DIR@|${APP_DIR}|g" \
  -e "s|@CONFIG_DIR@|${CONFIG_DIR}|g" \
  -e "s|@SERVICE_USER@|${SERVICE_USER}|g" \
  -e "s|@SERVICE_GROUP@|${SERVICE_GROUP}|g" \
  "${SERVICE_TEMPLATE}" > "${TMP_UNIT}"
"${RUN_AS_ROOT[@]}" install -m 0644 "${TMP_UNIT}" "/etc/systemd/system/${SERVICE_NAME}.service"
rm -f "${TMP_UNIT}"

TMP_WRAPPER="$(mktemp)"
sed \
  -e "s|@APP_DIR@|${APP_DIR}|g" \
  -e "s|@CONFIG_DIR@|${CONFIG_DIR}|g" \
  "${CONFIG_WRAPPER_TEMPLATE}" > "${TMP_WRAPPER}"
"${RUN_AS_ROOT[@]}" install -m 0755 "${TMP_WRAPPER}" "/usr/local/bin/gate-config.sh"
"${RUN_AS_ROOT[@]}" ln -sf "/usr/local/bin/gate-config.sh" "/usr/local/bin/gate-config"
rm -f "${TMP_WRAPPER}"

TMP_MENU="$(mktemp)"
sed \
  -e "s|@APP_DIR@|${APP_DIR}|g" \
  -e "s|@CONFIG_DIR@|${CONFIG_DIR}|g" \
  "${MENU_WRAPPER_TEMPLATE}" > "${TMP_MENU}"
"${RUN_AS_ROOT[@]}" install -m 0755 "${TMP_MENU}" "/usr/local/bin/gate-menu.sh"
"${RUN_AS_ROOT[@]}" ln -sf "/usr/local/bin/gate-menu.sh" "/usr/local/bin/gate-menu"
rm -f "${TMP_MENU}"

TMP_STATUS="$(mktemp)"
sed \
  -e "s|@APP_DIR@|${APP_DIR}|g" \
  -e "s|@CONFIG_DIR@|${CONFIG_DIR}|g" \
  "${STATUS_WRAPPER_TEMPLATE}" > "${TMP_STATUS}"
"${RUN_AS_ROOT[@]}" install -m 0755 "${TMP_STATUS}" "/usr/local/bin/gate-status.sh"
"${RUN_AS_ROOT[@]}" ln -sf "/usr/local/bin/gate-status.sh" "/usr/local/bin/gate-status"
rm -f "${TMP_STATUS}"

"${RUN_AS_ROOT[@]}" install -m 0644 "${SHELL_PROFILE_TEMPLATE}" "/etc/profile.d/owen-gateway.sh"

"${RUN_AS_ROOT[@]}" chown -R "${SERVICE_USER}:${SERVICE_GROUP}" "${APP_DIR}" "${CONFIG_DIR}"

"${RUN_AS_ROOT[@]}" systemctl daemon-reload
"${RUN_AS_ROOT[@]}" systemctl enable "${SERVICE_NAME}.service"

echo
echo "Installed successfully."
echo "Config: ${CONFIG_DIR}/owen_config.json"
echo "Config tool:    /usr/local/bin/gate-config.sh"
echo "Menu tool:      /usr/local/bin/gate-menu.sh"
echo "Status tool:    /usr/local/bin/gate-status.sh"
echo "Short commands: /usr/local/bin/gate-config, /usr/local/bin/gate-menu, /usr/local/bin/gate-status"
echo "Shell aliases:  /etc/profile.d/owen-gateway.sh"
echo "Start service: sudo systemctl start ${SERVICE_NAME}"
echo "Status:        systemctl status ${SERVICE_NAME}"
echo "Logs:          journalctl -u ${SERVICE_NAME} -f"
