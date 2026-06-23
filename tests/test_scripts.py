#!/usr/bin/env python3
"""Unit tests for the deterministic logic in the harness + skill scripts.

These are the pure, model-free functions whose silent breakage would be hard to
notice: the frontmatter parser (lint depends on it) and the doc-illustrate
verbatim checker's tokenizer. stdlib ``unittest`` only — same "runs anywhere
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
from _skills import REPO_ROOT, is_ignored_dir, parse_frontmatter  # noqa: E402


def _load(path: Path, name: str):
    """Import a skill script by file path (they live outside tests/)."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

SKILLS = REPO_ROOT / ".claude" / "skills"
vfy = _load(SKILLS / "doc-illustrate" / "scripts" / "verify.py", "verify")
skd = _load(SKILLS / "make-kadai" / "scripts" / "sheet_kadai.py", "sheet_kadai")
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


class TestVerifyTokens(unittest.TestCase):
    def test_norm_strips_whitespace(self):
        self.assertEqual(vfy.norm("第 7 層"), "第7層")

    def test_hard_tokens_quotes_and_nums(self):
        toks = vfy.hard_tokens("上限は「100GB」で API は GetObject")
        self.assertIn("100GB", toks)
        self.assertIn("GetObject", toks)


class TestSheetKadai(unittest.TestCase):
    # 1ヘッダ行 + 課題行(1-5埋,6空) + 指導内容 + 次回予定 を持つ合成グリッド
    GRID = [
        ["インストラクター記入欄", "1回目レッスン", "2回目レッスン", "3回目レッスン",
         "4回目レッスン", "5回目レッスン", "6回目レッスン", "7回目レッスン"],
        ["レッスンで指導した内容", "t1", "t2", "t3", "t4", "t5", "", ""],
        ["次回までの宿題 ※...", "IAM課題", "VPC課題", "EC2課題", "ASG課題", "AutoScaling課題", "", ""],
        ["次回レッスンの内容", "p1", "p2", "p3", "p4", "ALBの予定", "", ""],
    ]

    def test_parse_url_with_gid(self):
        sid, gid = skd.parse_sheet_url(
            "https://docs.google.com/spreadsheets/d/AbC_1-2/edit?gid=42#gid=42")
        self.assertEqual((sid, gid), ("AbC_1-2", 42))

    def test_parse_url_bare_id(self):
        self.assertEqual(skd.parse_sheet_url("AbCdEfGhIjKlMnOpQrSt"), ("AbCdEfGhIjKlMnOpQrSt", None))

    def test_parse_url_bad(self):
        with self.assertRaises(skd.SkillError):
            skd.parse_sheet_url("https://example.com/not-a-sheet")

    def test_col_to_letters(self):
        self.assertEqual([skd.col_to_letters(i) for i in (0, 6, 25, 26, 52)],
                         ["A", "G", "Z", "AA", "BA"])

    def test_quote_title(self):
        self.assertEqual(skd.quote_title_for_a1("Sheet1"), "Sheet1")
        self.assertEqual(skd.quote_title_for_a1("シート 1"), "'シート 1'")
        self.assertEqual(skd.quote_title_for_a1("a'b"), "'a''b'")

    def test_find_lesson_columns_zenkaku(self):
        cols = skd.find_lesson_columns([["x", "１回目レッスン", "２回目レッスン"]])
        self.assertEqual(cols, {1: 1, 2: 2})

    def test_resolve_next_empty(self):
        r = skd.resolve_target(self.GRID, None)
        self.assertEqual(r["target"], {"lesson": 6, "cell": "G3", "empty": True})
        self.assertEqual(r["filled_lessons"], [1, 2, 3, 4, 5])
        self.assertEqual(r["template_lesson"], 5)
        self.assertEqual(r["template_text"], "AutoScaling課題")

    def test_resolve_hints(self):
        r = skd.resolve_target(self.GRID, None)
        self.assertEqual(r["hints"]["prev_lesson"], 5)
        self.assertEqual(r["hints"]["plan_for_this_lesson"], "ALBの予定")
        self.assertEqual(r["hints"]["prev_taught"], "t5")

    def test_resolve_explicit_lesson(self):
        self.assertEqual(skd.resolve_target(self.GRID, 3)["target"]["cell"], "D3")

    def test_resolve_no_kadai_row(self):
        with self.assertRaises(skd.SkillError):
            skd.resolve_target([["a", "1回目レッスン"]], None)  # 課題行なし


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
        # a,b はリンク済・c だけ未リンク = 今回の make-kadai と同じ状況 → c を検出。
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


if __name__ == "__main__":
    unittest.main()
