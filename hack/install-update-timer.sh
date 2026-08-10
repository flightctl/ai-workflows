#!/usr/bin/env bash
# Install (or refresh) the systemd --user timer that checks for ai-workflows updates.
#
# Usage:
#   ./hack/install-update-timer.sh           # enable + start
#   ./hack/install-update-timer.sh --remove  # disable + remove units
#   ./hack/install-update-timer.sh --once    # run the check once now

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/systemd/user"
BIN_DIR="${HOME}/.local/bin"

ACTION=install
for arg in "$@"; do
  case "$arg" in
    --remove) ACTION=remove ;;
    --once) ACTION=once ;;
    -h|--help)
      sed -n '2,10p' "$0"
      exit 0
      ;;
  esac
done

chmod +x "${REPO_DIR}/hack/update-check.sh" "${REPO_DIR}/hack/aiw-update.sh"

case "$ACTION" in
  once)
    exec "${REPO_DIR}/hack/update-check.sh"
    ;;
  remove)
    systemctl --user disable --now ai-workflows-update-check.timer 2>/dev/null || true
    rm -f "${UNIT_DIR}/ai-workflows-update-check.service" \
          "${UNIT_DIR}/ai-workflows-update-check.timer"
    systemctl --user daemon-reload
    rm -f "${BIN_DIR}/aiw-update"
    echo "Removed ai-workflows update timer."
    exit 0
    ;;
esac

mkdir -p "$UNIT_DIR" "$BIN_DIR"
cp "${REPO_DIR}/hack/systemd/ai-workflows-update-check.service" "$UNIT_DIR/"
cp "${REPO_DIR}/hack/systemd/ai-workflows-update-check.timer" "$UNIT_DIR/"

# Convenience command on PATH
ln -sfn "${REPO_DIR}/hack/aiw-update.sh" "${BIN_DIR}/aiw-update"

systemctl --user daemon-reload
systemctl --user enable --now ai-workflows-update-check.timer

echo "Installed ai-workflows update timer (daily, ~00:00)."
echo "  status:  systemctl --user status ai-workflows-update-check.timer"
echo "  logs:    journalctl --user -u ai-workflows-update-check.service -f"
echo "  update:  aiw-update"
echo "  remove:  ${REPO_DIR}/hack/install-update-timer.sh --remove"
echo
echo "Note: Linger is off — the timer runs while your user session is active."
echo "Persistent=true will catch a missed daily run on next login."
echo
echo "Running an initial check now (notification only if you are behind main)..."
"${REPO_DIR}/hack/update-check.sh" || true
