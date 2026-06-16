#!/bin/bash
# skill-reflect weekly self-improvement cron (github-managed; safe for a public repo).
# Loaded by scripts/install-cron.sh, which generates the launchd plist that runs this.
#
# Runs a headless `claude -p "/skill-reflect …"` that mines the last 7 days of
# LOCAL session logs (~/.claude/projects/*/*.jsonl — a cloud Routine can't see
# these, hence this is a LOCAL cron) for claude-forge skill mis-fires, and files
# high-value SKILL.md improvement proposals as a GitHub issue in THIS repo.
# It NEVER edits skills or commits — proposals only; the human reviews the issue.
#
# bypassPermissions: an unattended cron can't answer permission prompts, so it
# runs with gates OFF. Only installed after per-user authorization (see
# install-cron.sh). skill-reflect's autonomous mode is read-only + issue-filing.
#
# Paths are resolved dynamically (no hardcoded absolute paths). Machine-local
# state/controls live in ~/.skill-reflect-auto/ (NOT committed):
#   PAUSED  present -> skip entirely (kill switch)
#   MODEL   model id (default claude-sonnet-4-6)
# Usage: cron-run.sh [--dry-run]   (--dry-run: analyze + print; never file an issue)
set -uo pipefail

: "${HOME:?HOME must be set}"
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# scripts -> skill-reflect -> skills -> .claude -> repo root
REPO="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
DIR="$HOME/.skill-reflect-auto"          # machine-local state/logs
LOG="$DIR/run.log"
PROMPT_FILE="$SCRIPT_DIR/cron-prompt.md"
mkdir -p "$DIR"

log(){ echo "[$(date '+%Y-%m-%d %H:%M:%S %z')] $*" >> "$LOG"; }

# --- kill switch ---
if [ -f "$DIR/PAUSED" ]; then log "PAUSED present -> exit"; exit 0; fi

DRYRUN="${1:-}"
MODEL="$(cat "$DIR/MODEL" 2>/dev/null || echo claude-sonnet-4-6)"
TODAY="$(date '+%Y-%m-%d')"
log "start (model=$MODEL today=$TODAY dryrun=${DRYRUN:-no} repo=$REPO)"

# --- build the headless prompt (header injects TODAY + optional dry-run) ---
HEADER="TODAY is ${TODAY} (JST)."
if [ "$DRYRUN" = "--dry-run" ]; then
  HEADER="${HEADER}
DRY_RUN: 分析と提案の出力だけ行う。issue は絶対に作らない。最後に RESULT: dry-run(<件数> 件の案) を出して終了。"
fi
PROMPT="${HEADER}

$(cat "$PROMPT_FILE")"

# --- run headless claude in the repo (skills + create-issue resolve to this repo) ---
cd "$REPO" || { log "cannot cd $REPO"; exit 1; }
log "invoking claude (headless)…"
OUT="$(claude -p "$PROMPT" \
  --add-dir "$REPO" \
  --permission-mode bypassPermissions \
  --model "$MODEL" \
  --max-budget-usd 3.00 \
  --output-format text \
  --no-session-persistence 2>>"$LOG")"
rc=$?
echo "$OUT" | grep -E '^RESULT:' >> "$LOG" || log "no RESULT line (rc=$rc); tail: $(echo "$OUT" | tail -c 400 | tr '\n' ' ')"
log "done (rc=$rc)"
exit 0
