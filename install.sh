#!/usr/bin/env bash
# Wire ~/.claude/{skills,agents,hooks} → this repo's directories.
# Idempotent: existing real directories are backed up to *.bak-<timestamp>,
# existing symlinks pointing here are left alone, anything else aborts.
#
# Note: ~/.claude/commands は **意図的に管理外**。すべて Skills に統合する方針
# (Anthropic の最近のガイドライン)。slash command が欲しい場合は対応する skill を
# `/skill-name` で明示呼びすればよい。古い ~/.claude/commands のシンボリックリンクは
# `rm ~/.claude/commands` で手動削除してください (broken link を放置すると無害だが
# 混乱の元)。

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
for d in skills agents hooks; do
  link_dir "$d"
done

# 旧版で ~/.claude/commands を symlink していた場合、broken link を掃除
if [[ -L "$CLAUDE_DIR/commands" ]]; then
  current="$(readlink "$CLAUDE_DIR/commands")"
  if [[ "$current" == "$REPO_DIR/commands" ]]; then
    echo "  [cleanup] $CLAUDE_DIR/commands は broken symlink (本 repo の commands/ は削除済)。rm します"
    rm "$CLAUDE_DIR/commands"
  fi
fi

echo
echo "Done. ~/.claude is wired to:"
ls -la "$CLAUDE_DIR" | grep -E ' -> ' || true

echo
echo "Note: ~/.claude/settings.json is NOT symlinked (Claude Code rewrites it at runtime)."
echo "See settings/settings.example.json for a template you can hand-merge."
