#!/usr/bin/env python3
"""Model-judged firing eval for claude-forge skills.

The deterministic lint proves a SKILL.md is well-formed; it cannot tell you
whether the `description` actually causes the skill to fire for the phrases it
claims to cover (or, worse, mis-fires on unrelated ones). That decision is made
by a model from the descriptions, so we test it the same way: feed every local
skill's name+description to `claude -p` as a one-shot router and check that each
fixture in triggers.json routes to the expected skill.

This is the SLOW, NON-DETERMINISTIC, token-costing layer — a periodic
trigger-quality check, not a per-commit gate. It is an approximation of the real
router (it asks a model to imitate the routing decision from the descriptions),
which is exactly the signal you want when tuning a `description`.

Usage:
  python3 tests/eval_triggers.py            # run the eval via `claude -p`
  python3 tests/eval_triggers.py --dry-run  # build prompts only, no model calls
  python3 tests/eval_triggers.py --model claude-sonnet-4-6
  python3 tests/eval_triggers.py --verbose  # show every case, not just misses

Exit code: number of mismatches (0 = all fixtures routed as expected).
Skips cleanly (exit 0) if the `claude` CLI is not on PATH.
Fails fast (exit 2) if the `claude` CLI is not logged in (`claude auth status`
→ loggedIn: false) — every probe would MISS with "Not logged in", which reads
as a routing failure but is a harness failure. Run `claude auth login` first.
(A logged-in CLI works fine even when the eval is run from inside a Claude
Code session.)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from _skills import load_skills

FIXTURES = Path(__file__).resolve().parent / "triggers.json"


def build_prompt(skills: list[dict], query: str) -> str:
    # Feed the judge the same text the real router sees: description +
    # when_to_use combined (CC concatenates both in the skill listing).
    catalog = "\n".join(
        f"- {s['name']}: {s['description']}" + (f" {s['when_to_use']}" if s.get("when_to_use") else "")
        for s in skills
        if s["name"]
    )
    return (
        "You are the skill router for a Claude Code project. Below is the catalog "
        "of available skills with the description that governs when each one should "
        "auto-activate.\n\n"
        f"{catalog}\n\n"
        "Decide which SINGLE skill should auto-activate for the user message below. "
        "If no skill clearly applies, answer NONE.\n"
        "Respond with EXACTLY one line: one skill name from the catalog above verbatim, "
        "or NONE. Names that appear only inside a description (e.g. a delegated agent) "
        "are not valid answers — when a description says such a request should be "
        "handled by an agent or plain response instead of firing the skill, the "
        "correct answer is NONE. No other text.\n\n"
        f"User message: {query}"
    )


def ask_claude(prompt: str, model: str | None) -> str:
    cmd = ["claude", "-p", prompt]
    if model:
        cmd += ["--model", model]
    # These router probes are synthetic, not real usage. Mark them so the
    # dashboard's SessionEnd hook (session-uploader.py) skips uploading a
    # session row per probe; otherwise a single eval run floods the Sessions
    # list with ~1-turn, ~44K-token entries.
    env = {**os.environ, "CLAUDE_CODE_USAGE_DASHBOARD_SKIP": "1"}
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=180, env=env)
    combined = out.stdout + out.stderr
    if "Not logged in" in combined or "Please run /login" in combined:
        print(
            "FATAL: `claude` CLI is not logged in — every probe would MISS with "
            "'Not logged in' (a harness failure, not a routing failure). Run "
            "`claude auth login` and retry.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    # Take the last non-empty line and trim trailing punctuation/quotes.
    lines = [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
    return (lines[-1] if lines else "").strip().strip("`\"'.").strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="build prompts only, no model calls")
    ap.add_argument("--model", default=None, help="model id passed to `claude --model`")
    ap.add_argument("--verbose", action="store_true", help="print every case, not only misses")
    args = ap.parse_args()

    skills = load_skills()
    valid_names = {s["name"] for s in skills if s["name"]} | {"NONE"}
    cases = json.loads(FIXTURES.read_text(encoding="utf-8"))["cases"]

    # Validate fixtures reference real skills before spending any tokens.
    bad = [c for c in cases if c["expect"] not in valid_names]
    if bad:
        for c in bad:
            print(f"FATAL: fixture expects unknown skill '{c['expect']}': {c['query']}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(f"[dry-run] {len(cases)} fixtures, {len(skills)} skills in catalog\n")
        print(build_prompt(skills, cases[0]["query"]))
        return 0

    if shutil.which("claude") is None:
        print("SKIP: `claude` CLI not found on PATH — cannot run the model-judged eval.")
        return 0

    misses = 0
    for c in cases:
        raw = ask_claude(build_prompt(skills, c["query"]), args.model)
        # An answer outside the catalog (e.g. an agent name quoted inside a
        # description, like "doc-reviewer") cannot fire as a skill — the real
        # router falls through to no-skill. Score it as NONE, but keep the raw
        # answer visible so a description that keeps baiting it still shows up.
        got = raw if raw in valid_names else "NONE"
        shown = got if got == raw else f"{got}<-{raw}"
        ok = got == c["expect"]
        if not ok:
            misses += 1
        if args.verbose or not ok:
            mark = "ok  " if ok else "MISS"
            print(f"  {mark}  expect={c['expect']:20} got={shown:20} | {c['query']}")

    total = len(cases)
    print(f"\n{total - misses}/{total} routed as expected" + (f"  ({misses} miss)" if misses else ""))
    return misses


if __name__ == "__main__":
    raise SystemExit(main())
