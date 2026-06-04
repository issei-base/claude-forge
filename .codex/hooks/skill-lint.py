#!/usr/bin/env python3
"""Codex Stop hook: run the deterministic skill lint when skill files changed."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if res.returncode == 0:
            return Path(res.stdout.strip())
    except Exception:
        pass
    return Path.cwd()


def _skills_are_dirty(root: Path) -> bool:
    try:
        res = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "status",
                "--porcelain",
                "-u",
                "--",
                ".claude/skills",
                "tests",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if res.returncode == 0:
            return bool(res.stdout.strip())
    except Exception:
        pass
    return True


def main() -> int:
    if os.environ.get("SKILL_LINT_HOOK") == "0":
        return 0

    root = _repo_root()
    lint = root / "tests" / "lint_skills.py"
    if not lint.exists() or not _skills_are_dirty(root):
        return 0

    res = subprocess.run(
        [sys.executable, str(lint)],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if res.returncode == 0:
        return 0

    sys.stderr.write("skill lint failed. Fix SKILL.md before ending the turn:\n\n")
    sys.stderr.write(res.stdout or res.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
