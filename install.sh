#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/dkta-labs/tavernbench"
INSTALL_DIR="${HOME}/.tavernbench"
BIN_DIR="${HOME}/.local/bin"
WITH_MCP="false"

for arg in "$@"; do
  case "$arg" in
    --mcp) WITH_MCP="true" ;;
    -h|--help)
      printf '%s\n' "Usage: install.sh [--mcp]" "Installs the TavernBench Behavior Lab HTTP v1 SDK and concierge CLI."
      exit 0
      ;;
    *) printf 'Unknown option: %s\n' "$arg" >&2; exit 2 ;;
  esac
done

if [ -d "${INSTALL_DIR}/.git" ]; then
  git -C "${INSTALL_DIR}" pull --ff-only
else
  git clone --depth 1 "${REPO}" "${INSTALL_DIR}"
fi

python3 -m venv "${INSTALL_DIR}/.venv"
if [ "${WITH_MCP}" = "true" ]; then
  "${INSTALL_DIR}/.venv/bin/python" -m pip install "${INSTALL_DIR}/sdk[mcp]"
else
  "${INSTALL_DIR}/.venv/bin/python" -m pip install "${INSTALL_DIR}/sdk"
fi

mkdir -p "${BIN_DIR}"
ln -sfn "${INSTALL_DIR}/.venv/bin/tavernbench" "${BIN_DIR}/tavernbench"

printf '%s\n' \
  "TavernBench Behavior Lab installed." \
  "Create a dedicated account-owned API key at https://tavernbench.dkta.dev/dashboard" \
  "At run time, prompt without shell history:" \
  "export TAVERNBENCH_API_KEY=\"\$(python3 -c 'import getpass; print(getpass.getpass(\"TavernBench API key: \"))')\"" \
  "Run: ${BIN_DIR}/tavernbench concierge --participant-code builder-01 --config-label baseline --export tavernbench-evidence.json"

if [ "${WITH_MCP}" = "true" ]; then
  printf '%s\n' \
    "MCP command: ${INSTALL_DIR}/.venv/bin/python" \
    "MCP args: ${INSTALL_DIR}/mcp/server.py" \
    "Transport: stdio"
fi
