#!/bin/bash
# Install (or refresh) the weekly skill-reflect cron as a macOS LaunchAgent.
#
# Generates the launchd plist LOCALLY (absolute paths are machine-specific, so
# the plist is NOT committed) pointing at this repo's scripts/cron-run.sh, then
# bootstraps it. Idempotent — re-run any time. Use --uninstall to remove.
#
# Schedule defaults to Monday 09:00 (local time); override with env:
#   SKILL_REFLECT_WEEKDAY (0/7=Sun .. 1=Mon .. 6=Sat)  SKILL_REFLECT_HOUR (0-23)
#
# IMPORTANT — bypassPermissions: the weekly run executes `claude` with permission
# gates OFF (an unattended cron can't answer prompts). Only install if you accept
# that. skill-reflect's autonomous mode is read-only + issue-filing (no edits or
# commits), but the gate is still off. Kill switch: touch ~/.skill-reflect-auto/PAUSED
set -euo pipefail

LABEL="com.iseeeei.skill-reflect"
WEEKDAY="${SKILL_REFLECT_WEEKDAY:-1}"   # 1 = Monday
HOUR="${SKILL_REFLECT_HOUR:-9}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN="$SCRIPT_DIR/cron-run.sh"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
STATE="$HOME/.skill-reflect-auto"

mkdir -p "$STATE" "$HOME/Library/LaunchAgents"
chmod +x "$RUN"

if [ "${1:-}" = "--uninstall" ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  echo "uninstalled $LABEL (state dir $STATE kept)"
  exit 0
fi

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$RUN</string></array>
  <key>StartCalendarInterval</key>
  <dict><key>Weekday</key><integer>$WEEKDAY</integer><key>Hour</key><integer>$HOUR</integer><key>Minute</key><integer>0</integer></dict>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>$STATE/launchd.out.log</string>
  <key>StandardErrorPath</key><string>$STATE/launchd.err.log</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "installed $LABEL -> weekday=$WEEKDAY hour=$HOUR :00  (run: $RUN)"
launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1 && echo "launchd: loaded OK" || echo "launchd: NOT loaded (check the plist)"
