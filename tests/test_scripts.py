#!/usr/bin/env python3
"""Unit tests for the deterministic logic in the harness + skill scripts.

These are the pure, model-free functions whose silent breakage would be hard to
notice: the frontmatter parser (lint depends on it) and the hooks. stdlib ``unittest`` only — same "runs anywhere
python3 exists" constraint as the rest of the harness.

  python3 tests/test_scripts.py
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lint_skills  # noqa: E402
from _skills import (  # noqa: E402
    AGENTS_DIR,
    BUILTIN_AGENTS,
    REPO_ROOT,
    SKILLS_DIR,
    _PROSE_AGENT_RE,
    _SUBAGENT_RE,
    agent_refs_in_skills,
    is_ignored_dir,
    load_agents,
    load_marketplace,
    load_plugins,
    load_skills,
    parse_frontmatter,
    plugin_agents,
    plugin_skills,
    plugin_symlink_drift,
)


def _load(path: Path, name: str):
    """Import a skill script by file path (they live outside tests/)."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

SKILLS = REPO_ROOT / ".claude" / "skills"
slint = _load(REPO_ROOT / ".claude" / "hooks" / "skill-lint.py", "skill_lint")
gpg = _load(REPO_ROOT / ".claude" / "hooks" / "git-push-guard.py", "git_push_guard")


class TestFrontmatter(unittest.TestCase):
    def test_bare_scalar(self):
        self.assertEqual(parse_frontmatter("---\nname: ship\n---\n")["name"], "ship")

    def test_inline_comment_stripped(self):
        # The regression the audit found: `name: ship # note` must parse as 'ship'.
        fm = parse_frontmatter("---\nname: ship # 後で消す\n---\n")
        self.assertEqual(fm["name"], "ship")

    def test_hash_without_space_kept(self):
        # A '#' not preceded by whitespace is NOT a YAML comment.
        fm = parse_frontmatter("---\nname: c#sharp\n---\n")
        self.assertEqual(fm["name"], "c#sharp")

    def test_quoted_scalar_preserves_hash(self):
        fm = parse_frontmatter('---\ndescription: "a # b"\n---\n')
        self.assertEqual(fm["description"], "a # b")

    def test_folded_block(self):
        fm = parse_frontmatter("---\ndescription: >-\n  one\n  two\n---\n")
        self.assertEqual(fm["description"], "one two")

    def test_no_frontmatter(self):
        self.assertEqual(parse_frontmatter("# just a heading\n"), {})


class TestIgnoredDirs(unittest.TestCase):
    def test_underscore_and_dot_scaffolds(self):
        self.assertTrue(is_ignored_dir("_template"))
        self.assertTrue(is_ignored_dir(".scratch"))

    def test_real_skill_not_ignored(self):
        self.assertFalse(is_ignored_dir("ship"))
        # ohayou は skills/ の外 (tools/ohayou/) へ移設済みなので、skills/ 配下の
        # 名前としては例外扱いしない (誤って同名 skill を作ったら lint で気づける)。
        self.assertFalse(is_ignored_dir("ohayou"))


class TestAgentLint(unittest.TestCase):
    """agent 層の lint (A1–A4)。skill と対称に agent の frontmatter・委譲参照を守る。"""

    def test_subagent_type_extraction(self):
        # doc-review / fix-pr / implement-issue 形式 (`subagent_type: X` / `=X`)。
        self.assertEqual(_SUBAGENT_RE.findall("Agent tool（subagent_type: doc-reviewer）"), ["doc-reviewer"])
        self.assertEqual(_SUBAGENT_RE.findall("subagent_type=general-purpose を直接"), ["general-purpose"])

    def test_prose_agent_extraction(self):
        # ship 形式 (`name` agent)。ハイフン必須なので repo agent だけ拾う。
        self.assertEqual(_PROSE_AGENT_RE.findall("`skill-reviewer` agent（Agent tool）を回す"), ["skill-reviewer"])
        self.assertIn("leak-auditor", _PROSE_AGENT_RE.findall("`leak-auditor` agent が無い repo"))
        # backtick のツール名 (ハイフン無し) は agent 参照として拾わない。
        self.assertEqual(_PROSE_AGENT_RE.findall("`WebSearch` は snippet を根拠にしない"), [])

    def test_builtin_agents_excluded(self):
        # explain-article の `claude-code-guide` agent は builtin なので repo 参照に数えない。
        self.assertIn("claude-code-guide", BUILTIN_AGENTS)
        self.assertNotIn("claude-code-guide", agent_refs_in_skills())

    def test_repo_agent_names_match_filename(self):
        # A2: 実 repo の全 agent で name == ファイル名 stem (ズレると委譲が無言で壊れる)。
        for a in load_agents():
            self.assertEqual(a["name"], a["stem"], f"{a['stem']}.md の name がファイル名と不一致")
            self.assertTrue(a["description"], f"{a['stem']}.md に description が無い")

    def test_every_delegated_agent_resolves(self):
        # A4: skill が委譲する subagent_type は全て実在する agent に解決する。
        names = {a["name"] for a in load_agents()}
        for ref, dirs in agent_refs_in_skills().items():
            self.assertIn(ref, names, f"{sorted(set(dirs))} が未定義 agent '{ref}' に委譲している")


class TestSymlinkDrift(unittest.TestCase):
    """skill-lint.py の global symlink drift 検知 (取りこぼし防止ゲート)。"""

    def _make_repo(self, base, names, scaffolds=()):
        skills = os.path.join(base, "repo", ".claude", "skills")
        os.makedirs(skills)
        for n in names:
            os.makedirs(os.path.join(skills, n))
            Path(skills, n, "SKILL.md").write_text(f"---\nname: {n}\n---\n")
        for s in scaffolds:  # _template 等: SKILL.md があっても authored に数えない
            os.makedirs(os.path.join(skills, s))
            Path(skills, s, "SKILL.md").write_text("---\nname: x\n---\n")
        home = os.path.join(base, "home", ".claude", "skills")
        os.makedirs(home)
        return skills, home

    def _link(self, skills, home, name):
        os.symlink(os.path.join(skills, name), os.path.join(home, name))

    def test_authored_skips_scaffolds_and_orphans(self):
        with tempfile.TemporaryDirectory() as base:
            skills, _ = self._make_repo(base, ["a", "b"], scaffolds=["_template"])
            os.makedirs(os.path.join(skills, "noskill"))  # SKILL.md 無し = skill でない
            self.assertEqual(slint._authored_skills(skills), ["a", "b"])

    def test_gate_off_when_not_globally_installed(self):
        # 1 つも symlink されていない = global install 運用に乗っていない → 誤検知しない。
        with tempfile.TemporaryDirectory() as base:
            skills, home = self._make_repo(base, ["a", "b", "c"])
            missing, linked = slint.symlink_drift(skills, home)
            self.assertEqual(linked, [])
            self.assertEqual(missing, ["a", "b", "c"])  # linked 空なので呼び出し側は無視

    def test_partial_install_flags_missing(self):
        # a,b はリンク済・c だけ未リンク (部分 install) → c を検出。
        with tempfile.TemporaryDirectory() as base:
            skills, home = self._make_repo(base, ["a", "b", "c"])
            self._link(skills, home, "a")
            self._link(skills, home, "b")
            missing, linked = slint.symlink_drift(skills, home)
            self.assertEqual(linked, ["a", "b"])
            self.assertEqual(missing, ["c"])

    def test_all_linked_no_drift(self):
        with tempfile.TemporaryDirectory() as base:
            skills, home = self._make_repo(base, ["a", "b"])
            self._link(skills, home, "a")
            self._link(skills, home, "b")
            missing, linked = slint.symlink_drift(skills, home)
            self.assertEqual(missing, [])
            self.assertEqual(linked, ["a", "b"])

    def test_link_pointing_elsewhere_is_not_counted(self):
        # 同名だが別 repo を指す link は「この repo にリンク済」と見なさない。
        with tempfile.TemporaryDirectory() as base:
            skills, home = self._make_repo(base, ["a"])
            other = os.path.join(base, "other")
            os.makedirs(other)
            os.symlink(other, os.path.join(home, "a"))
            missing, linked = slint.symlink_drift(skills, home)
            self.assertEqual(linked, [])
            self.assertEqual(missing, ["a"])


class TestPluginSymlinks(unittest.TestCase):
    """E7: plugins/ bodies <-> .claude/ symlinks stay 1:1 (both directions)."""

    def _make_tree(self, base, skills, agents=()):
        """Build plugins/<plugin>/skills|agents bodies + an empty link dir."""
        plugins = os.path.join(base, "plugins")
        for name, plugin in skills.items():
            d = os.path.join(plugins, plugin, "skills", name)
            os.makedirs(d)
            Path(d, "SKILL.md").write_text(f"---\nname: {name}\n---\n")
        for stem, plugin in agents.items() if isinstance(agents, dict) else {}:
            d = os.path.join(plugins, plugin, "agents")
            os.makedirs(d, exist_ok=True)
            Path(d, f"{stem}.md").write_text(f"---\nname: {stem}\n---\n")
        links = os.path.join(base, ".claude", "skills")
        os.makedirs(links)
        return plugins, links

    def test_real_repo_has_no_drift(self):
        # 実 repo: 全 plugin skill/agent が .claude/ に正しく symlink されている。
        self.assertEqual(plugin_symlink_drift(plugin_skills(), SKILLS_DIR, False), ([], []))
        self.assertEqual(plugin_symlink_drift(plugin_agents(), AGENTS_DIR, True), ([], []))

    def test_missing_symlink_flagged(self):
        with tempfile.TemporaryDirectory() as base:
            plugins, links = self._make_tree(base, {"ship": "gh", "spike": "ws"})
            os.symlink(os.path.join(plugins, "gh", "skills", "ship"),
                       os.path.join(links, "ship"))
            # spike の symlink を張り忘れた → missing で検出、orphan は無し。
            missing, orphan = plugin_symlink_drift(
                {"ship": "gh", "spike": "ws"}, links, False, plugins_dir=plugins)
            self.assertEqual(missing, ["spike"])
            self.assertEqual(orphan, [])

    def test_orphan_symlink_flagged(self):
        with tempfile.TemporaryDirectory() as base:
            plugins, links = self._make_tree(base, {"ship": "gh"})
            os.symlink(os.path.join(plugins, "gh", "skills", "ship"),
                       os.path.join(links, "ship"))
            # plugins 外を指す symlink と、消えた body を指す dangling symlink。
            outside = os.path.join(base, "elsewhere")
            os.makedirs(outside)
            os.symlink(outside, os.path.join(links, "stray"))
            os.symlink(os.path.join(plugins, "gh", "skills", "gone"),
                       os.path.join(links, "gone"))
            missing, orphan = plugin_symlink_drift(
                {"ship": "gh"}, links, False, plugins_dir=plugins)
            self.assertEqual(missing, [])
            self.assertEqual(orphan, ["gone", "stray"])

    def test_wrong_target_counts_missing_and_orphan(self):
        # ship の symlink が別 plugin(の存在しない)を指す → missing かつ orphan。
        with tempfile.TemporaryDirectory() as base:
            plugins, links = self._make_tree(base, {"ship": "gh"})
            os.symlink(os.path.join(plugins, "ws", "skills", "ship"),  # 存在しない
                       os.path.join(links, "ship"))
            missing, orphan = plugin_symlink_drift(
                {"ship": "gh"}, links, False, plugins_dir=plugins)
            self.assertEqual(missing, ["ship"])
            self.assertEqual(orphan, ["ship"])

    def test_underscore_shared_symlink_not_orphan(self):
        # _shared は source_map に無い(scaffold 扱い)が、plugins 内を指す symlink
        # なので orphan にはしない。
        with tempfile.TemporaryDirectory() as base:
            plugins = os.path.join(base, "plugins")
            shared = os.path.join(plugins, "gh", "skills", "_shared")
            os.makedirs(shared)
            Path(shared, "pr.md").write_text("x")
            links = os.path.join(base, ".claude", "skills")
            os.makedirs(links)
            os.symlink(shared, os.path.join(links, "_shared"))
            missing, orphan = plugin_symlink_drift({}, links, False, plugins_dir=plugins)
            self.assertEqual((missing, orphan), ([], []))


class TestPluginManifests(unittest.TestCase):
    """E8: marketplace.json plugins[] <-> plugins/ dirs, and plugin.json shape."""

    def test_marketplace_declares_every_plugin_dir(self):
        mkt = load_marketplace()
        self.assertIsNotNone(mkt, "marketplace.json missing/unparseable")
        declared = {p["name"] for p in mkt["plugins"]}
        on_disk = {p["dir"] for p in load_plugins()}
        self.assertEqual(declared, on_disk)

    def test_marketplace_source_paths_match(self):
        for p in load_marketplace()["plugins"]:
            self.assertEqual(p["source"], f"./plugins/{p['name']}")

    def test_every_plugin_manifest_named_and_versioned(self):
        for p in load_plugins():
            self.assertTrue(p["has_manifest"], f"plugins/{p['dir']} lacks a valid plugin.json")
            self.assertEqual(p["name"], p["dir"], f"plugins/{p['dir']} name mismatch")
            self.assertTrue(p["version"], f"plugins/{p['dir']} plugin.json missing version")


class TestSharedRefResolution(unittest.TestCase):
    """W4/W5: `_shared/<file>.md` 参照が読み手側で解決できる形になっているか。

    `../_shared/x.md` というリテラルは symlink 経由でも実体側に着地する (カーネルが
    `..` より先に symlink を解決するため)。壊れるのは読み手が `<skill>/..` を字句的に
    畳んでから Read したときで、畳んだ先の `~/.claude/skills/_shared/` は存在しない。
    W4 はそれを防ぐ注記を要求し、W5 は「注記の代わりにマシン固有の絶対パスを書く」
    という誤った解 (plugin install 先には無いパス) を弾く。
    """

    NOTE = ("パスを字句的に畳まず `<この SKILL.md のディレクトリ>/../_shared/"
            "pr-conventions.md` の形のまま Read する")
    REF = "[`_shared/pr-conventions.md`](../_shared/pr-conventions.md) **§0 が唯一の定義**"

    def _skill(self, base, name, body):
        d = Path(base, name)
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(body, encoding="utf-8")
        return {"dir": name, "path": d / "SKILL.md"}

    def _warns(self, body, distributed=True):
        with tempfile.TemporaryDirectory() as base:
            s = self._skill(base, "ship", body)
            return lint_skills._shared_ref_warns([s], distributed)

    def test_ref_without_note_is_flagged(self):
        # これが直した本体のバグ: 参照はあるが畳むなという指示が無い。
        warns = self._warns(self.REF)
        self.assertEqual(len(warns), 1, warns)
        self.assertIn("W4", warns[0])

    def test_ref_with_note_is_clean(self):
        self.assertEqual(self._warns(f"{self.NOTE}\n\n{self.REF}"), [])

    def test_note_after_first_reference_is_flagged(self):
        # 存在するだけでは足りない: 参照を見た時点で動く読み手は、後ろにある注記に
        # 到達しない。weekly-plan で実際に踏んだ配置ミス (skill-reviewer が検出)。
        warns = self._warns(f"{self.REF}\n\n{self.NOTE}")
        self.assertEqual(len(warns), 1, warns)
        self.assertIn("W4", warns[0])
        self.assertIn("after", warns[0])

    def test_note_before_reference_is_clean(self):
        # 注記自身も `_shared/...md` を含むが、それを「最初の参照」と誤認しない。
        self.assertEqual(self._warns(f"{self.NOTE}\n\n{self.REF}"), [])

    def test_no_shared_ref_no_warn(self):
        # _shared を参照しない skill には何も要求しない。
        self.assertEqual(self._warns("ただの skill 本文。`~/projects/x` に触れる。"), [])

    def test_machine_local_path_to_shared_flagged_when_distributed(self):
        # create-pr にあった実際の leak。plugin install したユーザに
        # ~/projects/claude-forge/ は存在しない。
        body = (f"{self.NOTE}\n\n{self.REF}（原本: `~/projects/claude-forge/"
                f".claude/skills/_shared/pr-conventions.md`）")
        warns = self._warns(body)
        self.assertEqual(len(warns), 1, warns)
        self.assertIn("W5", warns[0])

    def test_machine_local_path_allowed_when_not_distributed(self):
        # plugins/ を持たない repo (claude-forge-personal) では絶対パス併記が正解なので
        # W5 は no-op。E7-E8 が PLUGINS_DIR で gate されているのと同じ repo 形状判定。
        body = (f"{self.NOTE}\n\n{self.REF}（原本: `~/projects/claude-forge-personal/"
                f".claude/skills/_shared/pr-conventions.md`）")
        self.assertEqual(self._warns(body, distributed=False), [])

    def test_clone_target_path_not_flagged(self):
        # pr-conventions §6 の「`~/projects/<リポジトリ名>` を探索」は clone 先の話で
        # _shared の解決とは無関係。bare な ~/projects/ で誤爆させない (実測した誤検知)。
        body = (f"{self.NOTE}\n\n{self.REF} §6（カレント確認 → `~/projects/<リポジトリ名>`"
                f" 探索 → 無ければ `gh repo clone`）")
        self.assertEqual(self._warns(body), [])

    def test_shared_body_itself_scanned_for_local_paths(self):
        # _shared/*.md 自身も W5 の対象。load_skills() は `_` 始まりを飛ばすので、
        # ここを見ないと pr-conventions.md 内の絶対パスが素通りする (実際にしていた)。
        warns = lint_skills._shared_ref_warns([], distributed=True)
        self.assertEqual(warns, [], "\n".join(warns))

    def test_real_skills_all_resolve(self):
        # 実 repo の全 skill が W4/W5 を満たす (8 本の _shared 参照 skill を含む)。
        warns = lint_skills._shared_ref_warns(load_skills(), lint_skills.PLUGINS_DIR.exists())
        self.assertEqual(warns, [], "\n".join(warns))

    def test_every_shared_referencing_skill_carries_the_note(self):
        # 参照サイトが実際に 8 skill あることを固定する。参照を増やした skill が
        # 注記なしで入ってきたら test_real_skills_all_resolve が落ちる。
        refs = [s["dir"] for s in load_skills()
                if lint_skills.SHARED_REF_RE.search(s["path"].read_text(encoding="utf-8"))]
        self.assertEqual(sorted(refs), [
            "create-issue", "create-pr", "fix-pr", "implement-issue",
            "orchestrate", "plan-issue", "ship", "weekly-plan",
        ])


class TestGitPushGuard(unittest.TestCase):
    """PreToolUse hook: main/master への直接 push を harness 層で deny する。"""

    def test_denies_direct_push_to_protected(self):
        for cmd in [
            "git push origin main",
            "git push origin master",
            "git push -f origin main",
            "git push --force origin master",
            "git push origin HEAD:main",
            "git push origin local:master",
            "git push --set-upstream origin main",
            "git push origin +refs/heads/main",
            # 複合コマンドの末尾に紛れていても拾う (if フィルタを使わない理由)
            "git add -A && git commit -m x && git push origin main",
        ]:
            self.assertTrue(gpg.is_push_to_protected(cmd), cmd)

    def test_allows_non_protected_pushes(self):
        for cmd in [
            "git push origin HEAD",          # 文字列に main/master が出ない
            "git push -u origin HEAD",
            "git push origin develop",
            "git push origin feature/login",
            "git push origin feature/main-thing",  # 部分一致は誤爆させない
            "git push origin mymain",
        ]:
            self.assertFalse(gpg.is_push_to_protected(cmd), cmd)

    def test_allows_non_push_commands_mentioning_main(self):
        for cmd in [
            "git checkout main",
            "git rebase main",
            "cat main.py",
            "echo main && ls",
            "git commit -m 'fix main bug'",
        ]:
            self.assertFalse(gpg.is_push_to_protected(cmd), cmd)

    def test_allows_git_push_as_string_argument(self):
        # git push がコマンドではなく引数・メッセージ・本文として現れるだけのケースは
        # deny しない (この hook 自身の PR 作成を gh pr create がブロックした回帰)。
        for cmd in [
            'gh pr create --title x --body "see: git push origin main"',
            'echo "git push origin main"',
            'git commit -m "あとで git push origin main する"',
            'grep "git push origin main" notes.txt',
            'printf "%s" "git push origin master"',
        ]:
            self.assertFalse(gpg.is_push_to_protected(cmd), cmd)

    def test_detects_push_with_git_global_options(self):
        # サブコマンド前にグローバルオプションが挟まっても push と判定する。
        for cmd in [
            "git -c http.sslVerify=false push origin main",
            "git --no-pager push origin master",
            "git -C /repo push origin main",
        ]:
            self.assertTrue(gpg.is_push_to_protected(cmd), cmd)

    def test_denies_wrapped_and_quoted_variants(self):
        # 2026-07 の監査で実測されたすり抜けパターン群。ラッパ・サブシェルの
        # 括弧・クォートされた ref・shell -c・リダイレクトを全て検知する。
        for cmd in [
            "(cd /tmp/x && git push origin main)",
            "true && (git push origin main)",
            "env git push origin main",
            "env -u GIT_DIR git push origin main",
            "time git push origin main",
            "timeout 60 git push origin main",
            'git push origin "main"',
            "git push origin 'main'",
            'bash -c "git push origin main"',
            "sh -c 'git push origin master'",
            "\\git push origin main",
            "git push origin main >/tmp/push.log 2>&1",
        ]:
            self.assertTrue(gpg.is_push_to_protected(cmd), cmd)

    def test_allows_wrapped_non_protected(self):
        # ラッパ・シェル経由でも、宛先が保護ブランチでなければ deny しない。
        for cmd in [
            "env git push origin feature/x",
            "timeout 60 git push origin HEAD",
            "bash -c 'git push origin develop'",
            "time git status",
        ]:
            self.assertFalse(gpg.is_push_to_protected(cmd), cmd)

    def test_fail_closed_on_operator_inside_quotes(self):
        # クォート文字列の中に制御演算子ごと push コマンドが埋まっている場合は
        # 誤 deny を許容する (fail-closed の設計方針。docstring 参照)。この挙動が
        # 変わったら意図的な設計変更なのでテストも一緒に見直すこと。
        self.assertTrue(gpg.is_push_to_protected(
            'git commit -m "x && git push origin main"'))


if __name__ == "__main__":
    unittest.main()
