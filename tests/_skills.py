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

import json
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"
# Plugin-marketplace layout: real skill/agent/hook bodies live under plugins/,
# and .claude/skills|agents hold *relative symlinks* into them (E7 guards the
# 1:1 correspondence). marketplace.json declares which plugins ship (E8).
PLUGINS_DIR = REPO_ROOT / "plugins"
MARKETPLACE_FILE = REPO_ROOT / ".claude-plugin" / "marketplace.json"

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


def find_orphan_dirs(skills_dir=SKILLS_DIR) -> list[str]:
    """Skill dirs that hold contents but no SKILL.md (and aren't intentionally ignored).

    Catches the "made a dir + scripts but forgot SKILL.md" mistake, which
    ``glob('*/SKILL.md')`` would otherwise skip in silence. Ignored dirs
    (scaffolds, retired cron dirs) are excluded via is_ignored_dir.

    *Empty* dirs are skipped: that is exactly how an uninitialized git submodule
    presents itself (for a submodule mounted under skills/, ``git worktree add``
    and a clone without ``--recurse-submodules`` both leave the mount point as a
    bare empty dir), and flagging it made E6 block the Stop hook on every
    worktree that touched a skill. Detection power is unaffected: git does not track empty
    dirs, so a half-built skill that can actually reach a commit always has
    contents.

    ``skills_dir`` is injectable so the check is unit testable against a
    synthetic tree (same convention as plugin_symlink_drift).
    """
    skills_dir = Path(skills_dir)
    if not skills_dir.exists():
        return []
    orphans = []
    for d in sorted(skills_dir.iterdir()):
        if not d.is_dir() or is_ignored_dir(d.name):
            continue
        if not any(d.iterdir()):
            continue  # empty => uninitialized submodule / stray mkdir, never a committed skill
        if not (d / "SKILL.md").exists():
            orphans.append(d.name)
    return orphans


def plugin_skills() -> dict[str, str]:
    """Map ``skill name -> plugin dir`` for every real skill under
    ``plugins/<plugin>/skills/<name>/SKILL.md``.

    Scaffold/shared dirs (``_shared`` / ``_template`` — any ``_``/``.`` prefix,
    see is_ignored_dir) are excluded: they are not standalone skills and E7 does
    not require a matching symlink for them.
    """
    out: dict[str, str] = {}
    if not PLUGINS_DIR.exists():
        return out
    for plugin in sorted(PLUGINS_DIR.iterdir()):
        skills_dir = plugin / "skills"
        if not skills_dir.is_dir():
            continue
        for d in sorted(skills_dir.iterdir()):
            if not d.is_dir() or is_ignored_dir(d.name):
                continue
            if (d / "SKILL.md").exists():
                out[d.name] = plugin.name
    return out


def plugin_agents() -> dict[str, str]:
    """Map ``agent stem -> plugin dir`` for every ``plugins/<plugin>/agents/*.md``."""
    out: dict[str, str] = {}
    if not PLUGINS_DIR.exists():
        return out
    for plugin in sorted(PLUGINS_DIR.iterdir()):
        agents_dir = plugin / "agents"
        if not agents_dir.is_dir():
            continue
        for md in sorted(agents_dir.glob("*.md")):
            out[md.stem] = plugin.name
    return out


def plugin_symlink_drift(source_map, link_dir, is_agent, plugins_dir=PLUGINS_DIR):
    """Cross-check plugin bodies against the ``.claude`` symlinks that expose them.

    ``source_map`` = ``{name: plugin}`` of real bodies under ``plugins/`` (from
    plugin_skills / plugin_agents). ``link_dir`` = ``.claude/skills`` or
    ``.claude/agents``. ``is_agent`` selects the ``<stem>.md`` file shape vs the
    ``<name>/`` dir shape. ``plugins_dir`` is injectable so the check is unit
    testable against a synthetic tree.

    Returns ``(missing, orphan)``:
      - ``missing`` = a plugin body with no ``.claude`` symlink resolving to it
        (someone added a skill under plugins/ but forgot to link it — it won't
        auto-fire or install).
      - ``orphan``  = a symlink under ``link_dir`` that does not resolve to an
        existing path inside ``plugins/`` (a dangling link, or one pointing
        outside the plugin tree — e.g. a renamed/removed plugin skill).

    realpath is used both ways so a link is only "correct" when it truly lands on
    the expected body (a link to the wrong plugin counts as missing + orphan).
    Whole-repo checkouts without a ``plugins/`` dir yield empty maps → no-op, so a
    plugins-less repo (claude-forge-personal) is never false-flagged.
    """
    link_dir = Path(link_dir)
    plugins_dir = Path(plugins_dir)
    plugins_real = os.path.realpath(plugins_dir)
    missing: list[str] = []
    for name, plugin in sorted(source_map.items()):
        link_name = f"{name}.md" if is_agent else name
        link = link_dir / link_name
        subdir = "agents" if is_agent else "skills"
        expected = plugins_dir / plugin / subdir / link_name
        if not link.is_symlink() or os.path.realpath(link) != os.path.realpath(expected):
            missing.append(name)

    orphan: list[str] = []
    if link_dir.exists():
        for entry in sorted(link_dir.iterdir()):
            if not entry.is_symlink():
                continue
            if is_agent and entry.suffix != ".md":
                continue
            real = os.path.realpath(entry)
            inside = real == plugins_real or real.startswith(plugins_real + os.sep)
            if not (inside and os.path.exists(real)):
                orphan.append(entry.name)
    return missing, orphan


def load_marketplace():
    """Parsed ``.claude-plugin/marketplace.json`` dict, or None if missing/corrupt."""
    try:
        return json.loads(MARKETPLACE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def load_plugins() -> list[dict]:
    """One record per ``plugins/<dir>``: dir, name, version, source, has_manifest.

    ``has_manifest`` is False when ``.claude-plugin/plugin.json`` is absent or
    unparseable (E8 turns that into an error). Empty when there's no ``plugins/``
    dir, so E8 degrades to a no-op in a plugins-less repo.
    """
    out: list[dict] = []
    if not PLUGINS_DIR.exists():
        return out
    for d in sorted(PLUGINS_DIR.iterdir()):
        if not d.is_dir():
            continue
        manifest = d / ".claude-plugin" / "plugin.json"
        rec = {"dir": d.name, "name": "", "version": "", "source": f"./plugins/{d.name}",
               "has_manifest": False}
        if manifest.exists():
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                rec["name"] = data.get("name", "")
                rec["version"] = str(data.get("version", ""))
                rec["has_manifest"] = True
            except ValueError:
                pass  # unparseable manifest → has_manifest stays False (E8 error)
        out.append(rec)
    return out


if __name__ == "__main__":
    for s in load_skills():
        print(f"{s['dir']:24} name={s['name']:24} desc_len={len(s['description'])}")
