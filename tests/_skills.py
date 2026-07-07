"""Shared helpers for the skill test suite.

Loads every `.claude/skills/<name>/SKILL.md` and parses its YAML frontmatter
WITHOUT a third-party YAML dependency, so the tests run anywhere `python3`
exists. Path resolution uses ``Path(__file__).resolve()`` so it keeps working
when the repo (or this file) is reached through a symlink — same convention the
skills themselves follow.

Frontmatter shapes seen in this repo and handled here:
  - ``name: ship``                       (bare scalar)
  - ``description: "..."`` / ``'...'``   (quoted scalar)
  - ``description: >-`` + indented body  (YAML folded block scalar)
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"

# Built-in subagent types shipped by Claude Code (no agents/*.md to resolve to).
# Skills reference these via subagent_type / prose, so the "referenced agent
# exists" cross-check (lint A4) must exempt them or it false-positives.
BUILTIN_AGENTS: set[str] = {
    "general-purpose",
    "Explore",
    "Plan",
    "claude",
    "claude-code-guide",
    "statusline-setup",
    "output-style-setup",
}

# Named dirs under skills/ that are intentionally local-only and must not be
# linted as public skills (gitignored, may be present locally without a SKILL.md).
# Dirs starting with `_` or `.` are scaffolds/scratch (e.g. `_template`) and are
# handled separately in is_ignored_dir(). Currently empty.
# Add a name here if a gitignored personal skill is ever placed under skills/
# (otherwise the lint demands a public triggers fixture for it).
IGNORED_SKILL_DIRS: set[str] = set()

_KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):\s?(.*)$")
_BLOCK_INDICATORS = {">", ">-", ">+", "|", "|-", "|+"}


def is_ignored_dir(name: str) -> bool:
    """True for dirs that are not real skills (scaffolds / retired cron dirs)."""
    return name.startswith("_") or name.startswith(".") or name in IGNORED_SKILL_DIRS


def parse_frontmatter(text: str) -> dict:
    """Parse a leading ``--- ... ---`` YAML frontmatter block.

    Returns a dict of top-level keys. Only the subset of YAML used by SKILL.md
    files is supported (scalars + folded/literal block scalars).
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}

    body = lines[1:end]
    result: dict[str, str] = {}
    i = 0
    while i < len(body):
        line = body[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        m = _KEY_RE.match(line)
        if not m:
            i += 1
            continue
        key, raw = m.group(1), m.group(2).strip()

        if raw in _BLOCK_INDICATORS:
            # Collect the indented (or blank) lines that form the block body.
            block: list[str] = []
            i += 1
            while i < len(body):
                bl = body[i]
                if bl.strip() == "":
                    block.append("")
                    i += 1
                    continue
                if bl[:1] in (" ", "\t"):
                    block.append(bl.strip())
                    i += 1
                    continue
                break  # un-indented => next top-level key
            if raw.startswith(">"):
                # Folded: blank lines become paragraph breaks, runs join with space.
                value = " ".join(b for b in block if b != "").strip()
            else:
                # Literal: preserve line breaks.
                value = "\n".join(block).strip()
            result[key] = value
        else:
            if (raw.startswith('"') and raw.endswith('"')) or (
                raw.startswith("'") and raw.endswith("'")
            ):
                raw = raw[1:-1]
            else:
                # YAML: an unquoted scalar ends at " #" (whitespace + hash begins
                # an inline comment). Without this, `name: ship # note` parses as
                # 'ship # note' and trips the name != dir check (E3) on a false
                # positive. Mirrors the line-start `#` skip above.
                hash_at = raw.find(" #")
                if hash_at != -1:
                    raw = raw[:hash_at].rstrip()
            result[key] = raw
            i += 1

    return result


def load_skills() -> list[dict]:
    """Return one record per local skill: dir, name, description, when_to_use, path.

    Scaffold/local-only dirs (see is_ignored_dir) are skipped so a `_template`
    SKILL.md or a gitignored personal skill never counts as a public skill.

    ``when_to_use`` is parsed too because CC's skill listing truncates
    ``description`` + ``when_to_use`` *combined* at a fixed cap (see lint W3), so
    the length guard must sum both fields, not just description.
    """
    skills = []
    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        if is_ignored_dir(skill_md.parent.name):
            continue
        fm = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
        skills.append(
            {
                "dir": skill_md.parent.name,
                "name": fm.get("name", ""),
                "description": fm.get("description", ""),
                "when_to_use": fm.get("when_to_use", ""),
                "path": skill_md,
            }
        )
    return skills


_SUBAGENT_RE = re.compile(r"subagent[_-]type[:=]\s*[\"'`]?([A-Za-z0-9_-]+)")
# ship wires its gate agents in prose as `name` agent, not via subagent_type:.
# Require a hyphen so repo agents (all hyphenated: doc-reviewer, leak-auditor…)
# match while plain backticked tool names (`Read`, `WebSearch`) never do.
_PROSE_AGENT_RE = re.compile(r"`([A-Za-z0-9]+-[A-Za-z0-9_-]+)`\s*(?:agent|エージェント)")


def load_agents() -> list[dict]:
    """Return one record per custom agent: stem, name, description, path.

    Empty when there's no agents/ dir (a skills-only repo like
    claude-forge-personal), so the agent lint degrades to a graceful no-op.
    """
    if not AGENTS_DIR.exists():
        return []
    agents = []
    for md in sorted(AGENTS_DIR.glob("*.md")):
        fm = parse_frontmatter(md.read_text(encoding="utf-8"))
        agents.append(
            {
                "stem": md.stem,
                "name": fm.get("name", ""),
                "description": fm.get("description", ""),
                "path": md,
            }
        )
    return agents


def agent_refs_in_skills() -> dict[str, list[str]]:
    """Map each referenced agent name -> skill dirs that delegate to it.

    Covers both `subagent_type: X` (doc-review / fix-pr / implement-issue) and
    the `X` agent prose form (ship's skill-reviewer / leak-auditor gates).
    Built-in subagent types are dropped — they have no agents/*.md to resolve to.
    """
    refs: dict[str, list[str]] = {}
    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        if is_ignored_dir(skill_md.parent.name):
            continue
        text = skill_md.read_text(encoding="utf-8")
        names = set(_SUBAGENT_RE.findall(text)) | set(_PROSE_AGENT_RE.findall(text))
        for n in names - BUILTIN_AGENTS:
            refs.setdefault(n, []).append(skill_md.parent.name)
    return refs


def find_orphan_dirs() -> list[str]:
    """Skill dirs that exist but contain no SKILL.md (and aren't intentionally ignored).

    Catches the "made a dir + scripts but forgot SKILL.md" mistake, which
    ``glob('*/SKILL.md')`` would otherwise skip in silence. Ignored dirs
    (scaffolds, retired cron dirs) are excluded via is_ignored_dir.
    """
    if not SKILLS_DIR.exists():
        return []
    orphans = []
    for d in sorted(SKILLS_DIR.iterdir()):
        if not d.is_dir() or is_ignored_dir(d.name):
            continue
        if not (d / "SKILL.md").exists():
            orphans.append(d.name)
    return orphans


if __name__ == "__main__":
    for s in load_skills():
        print(f"{s['dir']:24} name={s['name']:24} desc_len={len(s['description'])}")
