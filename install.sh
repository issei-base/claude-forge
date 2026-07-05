#!/usr/bin/env bash
# Symlink every claude-forge skill + agent into the user scope (~/.claude) so the
# toolkit is available in *all* projects, while the single source of truth stays
# here in claude-forge (edit once, every project sees it).
#
# Idempotent: re-run any time. Uses `ln -sfn`, so it refreshes stale links and is
# safe to run after adding a skill. Skips scaffold/retired dirs:
#   - names starting with `_` or `.` (e.g. `_template`)
#   - any dir without a SKILL.md (e.g. `ohayou`, a retired skill kept only for a
#     local cron — it is .gitignored and must not be globally linked)
#
# Usage:
#   ./install.sh            # link skills + agents into ~/.claude
#   ./install.sh --dry-run  # print what would be linked, change nothing
set -euo pipefail

DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1
CONFLICTS=0

# Resolve the repo root from this script's real location (works via symlink too).
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ "$SOURCE" != /* ]] && SOURCE="$DIR/$SOURCE"
done
REPO_ROOT="$(cd -P "$(dirname "$SOURCE")" && pwd)"

SKILLS_SRC="$REPO_ROOT/.claude/skills"
AGENTS_SRC="$REPO_ROOT/.claude/agents"
SKILLS_DST="$HOME/.claude/skills"
AGENTS_DST="$HOME/.claude/agents"

link() {  # link <src> <dst>
  local src="$1" dst="$2"
  # 宛先が「symlink でない実ディレクトリ/ファイル」のとき、ln -sfn はそれを
  # 置き換えずに *中に* ネスト symlink (dst/name → src) を作って成功扱いに
  # なってしまう。黙って壊れた状態を作らないよう、リンクせず conflict として
  # 報告し、最後に非ゼロ終了する (実体の削除はユーザーに委ねる)。
  if [ -e "$dst" ] && [ ! -L "$dst" ]; then
    echo "  [conflict] $(basename "$dst") — $dst は symlink でない実体。リンクせずスキップ" >&2
    echo "             (中身を確認して退避/削除してから再実行: mv \"$dst\" \"$dst.bak\")" >&2
    CONFLICTS=$((CONFLICTS + 1))
    return 0
  fi
  if [ "$DRY_RUN" = 1 ]; then
    echo "  would link $(basename "$dst")"
  else
    ln -sfn "$src" "$dst"
    echo "  linked $(basename "$dst")"
  fi
}

mkdir -p "$SKILLS_DST" "$AGENTS_DST"

echo "skills → $SKILLS_DST"
for dir in "$SKILLS_SRC"/*/; do
  name="$(basename "$dir")"
  case "$name" in _* | .*) echo "  [skip] $name (scaffold)"; continue ;; esac
  if [ ! -f "$dir/SKILL.md" ]; then
    echo "  [skip] $name (no SKILL.md — retired/cron-only)"
    continue
  fi
  link "${dir%/}" "$SKILLS_DST/$name"
done

echo "agents → $AGENTS_DST"
for f in "$AGENTS_SRC"/*.md; do
  [ -e "$f" ] || continue
  link "$f" "$AGENTS_DST/$(basename "$f")"
done

if [ "$CONFLICTS" -gt 0 ]; then
  echo "error: $CONFLICTS 件の conflict をスキップした (上の [conflict] 行を参照)。" >&2
  exit 1
fi
echo "done. user-scope skills inherit ~/.claude/settings.json permissions —"
echo "add codex/gws/aws etc. there if you want them in every project."
