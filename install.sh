#!/usr/bin/env bash
# Wire ~/.claude/{commands,skills,agents,hooks} → this repo's directories.
# Idempotent: existing real directories are backed up to *.bak-<timestamp>,
# existing symlinks pointing here are left alone, anything else aborts.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$CLAUDE_DIR"

link_dir() {
  local name="$1"
  local target="$REPO_DIR/$name"
  local link="$CLAUDE_DIR/$name"

  mkdir -p "$target"

  if [[ -L "$link" ]]; then
    local current
    current="$(readlink "$link")"
    if [[ "$current" == "$target" ]]; then
      echo "  [skip] $link → already linked"
      return
    fi
    echo "  [warn] $link points to $current — leaving as is. Remove manually if you want to relink."
    return
  fi

  if [[ -d "$link" ]]; then
    local backup="${link}.bak-${TIMESTAMP}"
    echo "  [backup] $link → $backup"
    mv "$link" "$backup"
    # carry over any existing files into the repo (one-time merge)
    if [[ -n "$(ls -A "$backup" 2>/dev/null || true)" ]]; then
      echo "  [merge] copying contents of $backup into $target (skipping conflicts)"
      cp -n -R "$backup"/. "$target/" 2>/dev/null || true
    fi
  elif [[ -e "$link" ]]; then
    echo "  [error] $link exists and is not a directory or symlink — aborting"
    exit 1
  fi

  ln -s "$target" "$link"
  echo "  [link]  $link → $target"
}

echo "Linking Claude Code customization directories..."
for d in commands skills agents hooks; do
  link_dir "$d"
done

echo
echo "Done. ~/.claude is wired to:"
ls -la "$CLAUDE_DIR" | grep -E ' -> ' || true

echo
echo "Note: ~/.claude/settings.json is NOT symlinked (Claude Code rewrites it at runtime)."
echo "See settings/settings.example.json for a template you can hand-merge."
