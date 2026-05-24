# claude-forge

Personal Claude Code customization assets, managed in git.

```
claude-forge/
├── commands/   # slash commands → ~/.claude/commands/
├── skills/     # custom skills  → ~/.claude/skills/
├── agents/     # custom agents  → ~/.claude/agents/
├── hooks/      # hook scripts   → ~/.claude/hooks/
├── settings/
│   └── settings.example.json  # template for ~/.claude/settings.json (hand-merged)
└── install.sh  # idempotent symlink installer
```

## Setup on a new machine

```sh
git clone <this-repo-url> ~/projects/claude-forge
cd ~/projects/claude-forge
./install.sh
```

`install.sh` symlinks the four directories above into `~/.claude/`. Existing real directories there are backed up to `*.bak-<timestamp>` first, and their contents are merged forward into this repo.

`settings.json` is **not** symlinked because Claude Code rewrites it at runtime (UI preferences, oauth state, etc.). Hand-merge from `settings/settings.example.json` instead, or use the `/permissions` UI.

## What goes here

| Directory | What |
|---|---|
| `commands/` | Markdown files invoked as `/<filename>` slash commands |
| `skills/` | `<skill-name>/SKILL.md` directories that Claude can invoke |
| `agents/` | `<agent-name>.md` custom subagents |
| `hooks/` | Shell scripts referenced from `settings.json` `hooks` blocks |

## What does NOT go here

- `~/.claude/settings.json` / `settings.local.json` — runtime-mutable, machine-specific
- `~/.claude/projects/` — per-project memory and session state
- `~/.claude/plugins/` — installed via plugin marketplace, not source-controlled
- Anything containing secrets (API keys, tokens)

## Current commands

- `commands/codex-review.md` — `/codex-review` runs OpenAI Codex against the current git diff for a second-opinion review

## Current skills

- `skills/ship/` — model-invoked when you say "ship it" / "PR出して". Creates a branch if needed, generates commit + PR title/body from the diff, pushes, and opens the PR via `gh`.
