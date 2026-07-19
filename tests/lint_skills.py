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
      half-built skill; ignored scaffolds like `_template` and local-only dirs
      are exempt — see _skills.is_ignored_dir)
  W1  description carries explicit trigger guidance (example phrases / when-to-use)
  W2  every skill has at least one fixture in triggers.json (so a new skill can't
      land without a firing test; --strict turns this into an error in CI)
  W3  `description` + `when_to_use` stays under the skill-listing cap. CC truncates
      the combined text at DESC_LISTING_CAP chars in the listing the router sees
      (docs.claude.com/.../skills); past it, trailing trigger phrases are dropped
      and auto-firing silently degrades. Warns approaching the cap, before it bites.
  W4  a SKILL.md that cross-references `_shared/<file>.md` also carries the
      path-resolution note. The reference is written `../_shared/...` relative to
      the SKILL.md's own directory; the kernel resolves the symlink before `..`,
      so the literal path lands on the real body even when the skill is reached
      through `~/.claude/skills/<name>`. A reader that folds `<name>/..`
      *lexically* first lands on `~/.claude/skills/_shared/`, which does not
      exist — so the note ("don't fold the path") is what keeps the reference
      readable in the deployments this repo actually ships to.
  W5  that note is not a machine-local absolute path (`~/projects/<repo>/...`),
      in a repo that ships as a plugin. Only applies when plugins/ exists: a
      `claude plugin install` user has no such directory, so a local path is a
      dead end for them. A plugins-less repo may legitimately use one (see the
      PLUGINS_DIR gate on E7–E8 for the same repo-shape reasoning).

Agent layer (only when a .claude/agents/ dir exists — no-op in skills-only repos):
  A1  each agents/*.md has a `name` in frontmatter
  A2  agent `name` matches its filename stem (subagent_type resolves by file name,
      so a mismatch makes the agent unreachable and delegation fails silently)
  A3  agent has a `description` (delegation is description-driven, per README)
  A4  every agent a skill delegates to (subagent_type: X or `X` agent prose) is
      defined by some agents/*.md — guards hardcoded delegation from breaking
      silently when an agent is renamed or removed

Plugin-marketplace layer (only when a plugins/ dir exists — no-op otherwise):
  E7  every real skill/agent body under plugins/<plugin>/{skills,agents}/ has a
      matching .claude/{skills,agents} symlink resolving to it, and every such
      symlink resolves to an existing body inside plugins/. Guards the two failure
      modes of the "body in plugins/, symlink in .claude/" layout: a body added
      without its symlink (invisible to auto-fire/install) and a dangling/orphan
      symlink left behind by a rename or delete.
  E8  marketplace.json plugins[] match the plugins/ subdirectories 1:1, and each
      plugin.json has name == its directory and a non-empty version (+ source
      pointing at ./plugins/<name>). Guards a plugin that ships but isn't declared
      (or vice-versa) and a mis-named/unversioned manifest.

Usage:
  python3 tests/lint_skills.py [--strict]   # --strict: treat warnings as errors
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from _skills import (
    AGENTS_DIR,
    PLUGINS_DIR,
    SKILLS_DIR,
    agent_refs_in_skills,
    find_orphan_dirs,
    load_agents,
    load_marketplace,
    load_plugins,
    load_skills,
    plugin_agents,
    plugin_skills,
    plugin_symlink_drift,
)

MIN_DESC_LEN = 40
# CC truncates `description` + `when_to_use` combined at this many chars in the
# skill listing the router matches against (docs.claude.com/.../skills). Past it,
# trailing trigger phrases are silently dropped and auto-firing degrades.
DESC_LISTING_CAP = 1536
# Warn before the cap actually bites, so there's runway to trim (~85%).
DESC_WARN_AT = 1300
FIXTURES = Path(__file__).resolve().parent / "triggers.json"
# Soft signal that a description tells the router WHEN to fire. Any one hit
# silences W1. Kept broad on purpose — this is a nudge, not a gate.
TRIGGER_MARKERS = ("「", "発動", "使用", "トリガ", "use ", "when ", "trigger", "/", "など")

# A cross-reference into the shared-rules dir (see W4 in the module docstring).
SHARED_REF_RE = re.compile(r"_shared/[A-Za-z0-9._-]+\.md")
# Soft signal that the path-resolution note is present. Broad on purpose, same
# spirit as TRIGGER_MARKERS — keyed on the operative instruction ("don't fold the
# path"), so a reword that drops the instruction also drops the marker.
PATH_NOTE_MARKERS = ("字句的に畳", "lexically fold")
# A machine-local path pointing *at a _shared file* (`~/projects/<repo>/…/_shared/x.md`).
# Deliberately not a bare `~/projects/` match: several skills legitimately name
# `~/projects/<リポジトリ名>` as the place to look for the *target* repo to clone
# (pr-conventions §6), which has nothing to do with resolving `_shared`.
LOCAL_SHARED_ABS_RE = re.compile(r"~/projects/\S*_shared/[A-Za-z0-9._-]+\.md")


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


def _shared_ref_warns(skills: list[dict], distributed: bool) -> list[str]:
    """W4/W5: `_shared/<file>.md` cross-references stay resolvable for the reader.

    The reference is relative to the SKILL.md's own directory (`../_shared/...`),
    which is correct in every layout this repo ships: project scope, the
    ``~/.claude/skills/<name>`` symlink, and a ``claude plugin install`` copy.
    The kernel resolves the symlink before ``..``, so the literal path always
    lands on the real body. What breaks is a reader that folds ``<name>/..``
    lexically *before* reading: that yields ``~/.claude/skills/_shared/``, which
    does not exist. W4 requires the note that tells the reader not to fold.

    W5 additionally rejects a machine-local ``~/projects/<repo>/...`` path as the
    remedy, but only when this repo ships as a plugin (``distributed``) — a
    plugin user has no such directory. A plugins-less repo may use one, so the
    check no-ops there for the same reason E7–E8 do.
    """
    def _w5(label: str, text: str) -> list[str]:
        return [
            f"[{label}:{n}] W5 points at _shared/ via a machine-local `~/projects/...` "
            "path — absent in a `claude plugin install` checkout"
            for n, line in enumerate(text.splitlines(), 1)
            if LOCAL_SHARED_ABS_RE.search(line)
        ]

    warns: list[str] = []
    for s in skills:
        try:
            text = s["path"].read_text(encoding="utf-8")
        except OSError:
            continue  # unreadable body is E1's problem, not this check's
        if not SHARED_REF_RE.search(text):
            continue
        lines = text.splitlines()
        note_at = next((i for i, ln in enumerate(lines)
                        if any(m in ln for m in PATH_NOTE_MARKERS)), None)
        # The note names `_shared/…md` itself, so skip its own line when locating
        # the first *real* reference — otherwise every file looks mis-ordered.
        ref_at = next((i for i, ln in enumerate(lines)
                       if SHARED_REF_RE.search(ln) and i != note_at), None)
        if note_at is None:
            warns.append(
                f"[{s['dir']}] W4 references _shared/ without a path-resolution note "
                "— a reader that folds `<skill>/..` lexically lands on a dir that "
                "doesn't exist (add the `_shared/` の読み方 note near the top)"
            )
        elif ref_at is not None and note_at > ref_at:
            # Presence alone is not enough: a reader that acts on the reference
            # the moment it reads it never reaches a note placed further down.
            warns.append(
                f"[{s['dir']}:{note_at + 1}] W4 path-resolution note sits *after* the "
                f"first _shared/ reference (line {ref_at + 1}) — move it above"
            )
        if distributed:
            warns.extend(_w5(s["dir"], text))

    # W5 covers the _shared bodies themselves too: they carry their own "how to
    # read me" prose, and load_skills() skips `_` dirs — which is exactly how the
    # machine-local path inside pr-conventions.md stayed invisible.
    if distributed:
        for md in sorted((SKILLS_DIR / "_shared").glob("*.md")):
            warns.extend(_w5(f"_shared/{md.name}", md.read_text(encoding="utf-8")))
    return warns


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
        else:
            wtu = s["when_to_use"]
            # The router matches against description + when_to_use combined, so
            # evaluate trigger guidance (W1) and the length cap (W3) on the same
            # combined text — not description alone.
            listing = f"{desc}\n{wtu}" if wtu else desc
            if not any(mark in listing for mark in TRIGGER_MARKERS):
                warns.append(f"[{d}] W1 description has no obvious trigger guidance (when-to-use / examples)")
            # W3: keep description+when_to_use under the listing cap (see module docstring).
            combined = len(desc) + len(wtu)
            if combined > DESC_LISTING_CAP:
                warns.append(
                    f"[{d}] W3 description+when_to_use {combined} chars > {DESC_LISTING_CAP} listing cap "
                    "— trailing trigger phrases get truncated (auto-firing degrades)"
                )
            elif combined > DESC_WARN_AT:
                warns.append(
                    f"[{d}] W3 description+when_to_use {combined} chars approaching {DESC_LISTING_CAP} cap "
                    "— trim before trigger phrases truncate"
                )

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

    # W4/W5: `_shared/` cross-references stay resolvable (see the helper's docstring).
    warns.extend(_shared_ref_warns(skills, PLUGINS_DIR.exists()))

    # Agent layer (A1–A4). load_agents() is empty in a skills-only repo, so the
    # whole block is a no-op there — skills stay the only concern.
    agents = load_agents()
    agent_names: set[str] = set()
    for a in agents:
        stem, name, desc = a["stem"], a["name"], a["description"]
        if not name:
            errors.append(f"[agents/{stem}.md] A1 missing `name` in frontmatter")
        else:
            agent_names.add(name)
            if name != stem:
                errors.append(
                    f"[agents/{stem}.md] A2 name '{name}' != file '{stem}' "
                    "(subagent_type unresolvable — delegation fails silently)"
                )
        if not desc:
            errors.append(f"[agents/{stem}.md] A3 missing `description` (delegation is description-driven)")
    if agents:  # A4: only cross-check when this repo actually ships agents.
        for ref, dirs in sorted(agent_refs_in_skills().items()):
            if ref not in agent_names:
                errors.append(
                    f"A4 skill(s) {', '.join(sorted(set(dirs)))} delegate to '{ref}' "
                    "but no agents/*.md defines it (delegation fails silently)"
                )

    # Plugin-marketplace layer (E7–E8). No-op when there's no plugins/ dir, so a
    # plugins-less checkout/fork (claude-forge-personal) is never false-flagged.
    if PLUGINS_DIR.exists():
        # E7: plugins/ bodies <-> .claude/ symlinks, both directions, skills + agents.
        sk_missing, sk_orphan = plugin_symlink_drift(plugin_skills(), SKILLS_DIR, is_agent=False)
        ag_missing, ag_orphan = plugin_symlink_drift(plugin_agents(), AGENTS_DIR, is_agent=True)
        for n in sk_missing:
            errors.append(f"E7 plugin skill '{n}' has no matching .claude/skills/{n} symlink (add: ln -s ../../plugins/<plugin>/skills/{n} .claude/skills/{n})")
        for n in sk_orphan:
            errors.append(f"E7 .claude/skills/{n} is a symlink that doesn't resolve into plugins/ (orphan — target renamed/removed?)")
        for n in ag_missing:
            errors.append(f"E7 plugin agent '{n}' has no matching .claude/agents/{n}.md symlink")
        for n in ag_orphan:
            errors.append(f"E7 .claude/agents/{n} is a symlink that doesn't resolve into plugins/ (orphan)")

        # E8: marketplace.json plugins[] <-> plugins/ subdirs, and each plugin.json.
        mkt = load_marketplace()
        plugins = load_plugins()
        if mkt is None:
            errors.append("E8 .claude-plugin/marketplace.json missing or unparseable")
            declared = {}
        else:
            declared = {p.get("name"): p for p in mkt.get("plugins", []) if isinstance(p, dict)}
        on_disk = {p["dir"] for p in plugins}
        for name in sorted(set(declared) - on_disk):
            errors.append(f"E8 marketplace.json declares plugin '{name}' but plugins/{name}/ does not exist")
        for name in sorted(on_disk - set(declared)):
            errors.append(f"E8 plugins/{name}/ exists but marketplace.json does not declare it")
        for name, entry in sorted(declared.items()):
            want = f"./plugins/{name}"
            if name in on_disk and entry.get("source") != want:
                errors.append(f"E8 marketplace plugin '{name}' source '{entry.get('source')}' != '{want}'")
        for p in sorted(plugins, key=lambda r: r["dir"]):
            if not p["has_manifest"]:
                errors.append(f"[plugins/{p['dir']}] E8 missing or unparseable .claude-plugin/plugin.json")
                continue
            if p["name"] != p["dir"]:
                errors.append(f"[plugins/{p['dir']}] E8 plugin.json name '{p['name']}' != directory '{p['dir']}'")
            if not p["version"]:
                errors.append(f"[plugins/{p['dir']}] E8 plugin.json missing `version`")

    strict = "--strict" in sys.argv
    n_plugins = len(load_plugins()) if PLUGINS_DIR.exists() else 0
    scope = f"{len(skills)} skills" + (f" + {len(agents)} agents" if agents else "") + (
        f" + {n_plugins} plugins" if n_plugins else "")
    print(f"Linted {scope} under {SKILLS_DIR.relative_to(SKILLS_DIR.parents[2])}")
    for w in warns:
        print(f"  WARN  {w}")
    for e in errors:
        print(f"  ERROR {e}")

    fail = len(errors) + (len(warns) if strict else 0)
    if fail:
        print(f"\nFAILED: {len(errors)} error(s)" + (f", {len(warns)} warning(s) [strict]" if strict else ""))
        return 1
    print(f"\nOK: {scope} valid" + (f" ({len(warns)} warning(s))" if warns else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(lint())
