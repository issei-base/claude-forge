#!/usr/bin/env python3
"""Deterministic regression guard for claude-forge skills.

This is the always-on layer of the skill harness's feedback loop: it does NOT
prove a skill *fires* (see eval_triggers.py for that model-judged check) — it
proves each SKILL.md is structurally sound so a careless edit can't silently
break auto-firing. No network, no model, no third-party deps; safe for CI and
pre-commit.

Checks (ERROR = non-zero exit; WARN = printed, still exits 0 if no errors):
  E1  SKILL.md has parseable frontmatter
  E2  `name` is present
  E3  `name` matches its directory (the dir name is what `/slash` and the
      Skill tool resolve, so a mismatch makes the skill unreachable)
  E4  `description` is present and >= MIN_DESC_LEN chars
  E5  no two skills share a `name`
  E6  no skill dir is missing its SKILL.md (a dir + scripts but no SKILL.md is a
      half-built skill; ignored scaffolds like `_template` / retired `ohayou`
      are exempt — see _skills.is_ignored_dir)
  W1  description carries explicit trigger guidance (example phrases / when-to-use)
  W2  every skill has at least one fixture in triggers.json (so a new skill can't
      land without a firing test; --strict turns this into an error in CI)

Usage:
  python3 tests/lint_skills.py [--strict]   # --strict: treat warnings as errors
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from _skills import SKILLS_DIR, find_orphan_dirs, load_skills

MIN_DESC_LEN = 40
FIXTURES = Path(__file__).resolve().parent / "triggers.json"
# Soft signal that a description tells the router WHEN to fire. Any one hit
# silences W1. Kept broad on purpose — this is a nudge, not a gate.
TRIGGER_MARKERS = ("「", "発動", "使用", "トリガ", "use ", "when ", "trigger", "/", "など")


def _fixture_expectations() -> set | None:
    """Set of skill names that triggers.json expects to fire, or None if unreadable.

    Returning None (missing/corrupt fixtures) makes W2 a no-op rather than a hard
    failure — the fixture file is the eval's concern, not the structural lint's.
    """
    try:
        cases = json.loads(FIXTURES.read_text(encoding="utf-8"))["cases"]
    except (OSError, ValueError, KeyError):
        return None
    return {c.get("expect") for c in cases if isinstance(c, dict)}


def lint() -> int:
    skills = load_skills()
    errors: list[str] = []
    warns: list[str] = []

    if not skills:
        print(f"FATAL: no skills found under {SKILLS_DIR}", file=sys.stderr)
        return 2

    by_name: dict[str, list[str]] = {}
    for s in skills:
        d, name, desc = s["dir"], s["name"], s["description"]

        if not name:
            errors.append(f"[{d}] E2 missing `name` in frontmatter")
        else:
            by_name.setdefault(name, []).append(d)
            if name != d:
                errors.append(f"[{d}] E3 name '{name}' != directory '{d}' (skill unreachable)")

        if not desc:
            errors.append(f"[{d}] E4 missing `description`")
        elif len(desc) < MIN_DESC_LEN:
            errors.append(f"[{d}] E4 description too short ({len(desc)} < {MIN_DESC_LEN} chars)")
        elif not any(mark in desc for mark in TRIGGER_MARKERS):
            warns.append(f"[{d}] W1 description has no obvious trigger guidance (when-to-use / examples)")

    for name, dirs in by_name.items():
        if len(dirs) > 1:
            errors.append(f"E5 duplicate name '{name}' in dirs: {', '.join(dirs)}")

    for orphan in find_orphan_dirs():
        errors.append(f"[{orphan}] E6 directory has no SKILL.md (half-built skill?)")

    # W2: every skill should be exercised by at least one triggers.json fixture.
    covered = _fixture_expectations()
    if covered is not None:
        for s in skills:
            if s["name"] and s["name"] not in covered:
                warns.append(f"[{s['dir']}] W2 no fixture in triggers.json (add a firing test)")

    strict = "--strict" in sys.argv
    print(f"Linted {len(skills)} skills under {SKILLS_DIR.relative_to(SKILLS_DIR.parents[2])}")
    for w in warns:
        print(f"  WARN  {w}")
    for e in errors:
        print(f"  ERROR {e}")

    fail = len(errors) + (len(warns) if strict else 0)
    if fail:
        print(f"\nFAILED: {len(errors)} error(s)" + (f", {len(warns)} warning(s) [strict]" if strict else ""))
        return 1
    print(f"\nOK: {len(skills)} skills valid" + (f" ({len(warns)} warning(s))" if warns else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(lint())
