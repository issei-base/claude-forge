#!/usr/bin/env python3
"""SessionStart hook: live な skill / agent が既定ブランチ以外から供給されていたら警告する。

install.sh は `~/.claude/{skills,agents}/*` を repo の working tree への symlink にする。
実体が working tree なので、その repo が feature branch を checkout している間は
**全プロジェクトの live な skill がそのブランチの内容に化ける**。skill が丸ごと消えれば
気づけるが、節が 1 つ欠けただけ（例: ship の push 前レビューゲート）だと気づけない。

source repo は symlink を辿って動的に発見するので、この hook は repo 名を知らない。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

LINK_DIRS = ("skills", "agents", "commands")


def git(repo: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(
            ("git", "-C", str(repo), *args),
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def source_repos() -> list[Path]:
    """~/.claude/{skills,agents,commands}/* の symlink 先を git repo root に畳む。"""
    roots = set()
    for name in LINK_DIRS:
        d = Path.home() / ".claude" / name
        if not d.is_dir():
            continue
        for entry in d.iterdir():
            if not entry.is_symlink():
                continue
            try:
                target = entry.resolve(strict=True)
            except OSError:
                continue  # 壊れた symlink はここでは扱わない
            root = git(target.parent, "rev-parse", "--show-toplevel")
            if root:
                roots.add(Path(root))
    return sorted(roots)


def default_branch(repo: Path) -> str:
    head = git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if head and "/" in head:
        return head.split("/", 1)[1]
    return "main"


def main() -> int:
    offenders = []
    for repo in source_repos():
        expected = default_branch(repo)
        current = git(repo, "symbolic-ref", "--short", "HEAD")
        if current is None:
            sha = git(repo, "rev-parse", "--short", "HEAD") or "?"
            offenders.append(f"{repo.name}: detached HEAD ({sha})")
        elif current != expected:
            offenders.append(f"{repo.name}: {current} (期待は {expected})")

    if not offenders:
        return 0

    lines = "\n".join(f"  - {o}" for o in offenders)
    warning = (
        "live な skill / agent が既定ブランチ以外から読まれています:\n"
        f"{lines}\n"
        "この間 ~/.claude/skills/* の内容はそのブランチのものに化けます"
        "（ship の Codex 事前レビューゲートが消える等）。"
        "意図した dogfooding でなければ既定ブランチに戻してください。"
    )
    print(json.dumps({
        "systemMessage": warning,
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": warning,
        },
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # hook の失敗でセッションを止めない
