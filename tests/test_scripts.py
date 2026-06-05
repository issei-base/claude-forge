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
import sys
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
    def test_underscore_and_retired(self):
        self.assertTrue(is_ignored_dir("_template"))
        self.assertTrue(is_ignored_dir(".scratch"))
        self.assertTrue(is_ignored_dir("x-buzz"))

    def test_real_skill_not_ignored(self):
        self.assertFalse(is_ignored_dir("ship"))
        # ohayou は skills/ から tools/ohayou/ へ移設済み。skills/ 配下の名前としては
        # もう例外扱いしない (誤って ohayou という skill を作ったら lint で気づける)。
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


if __name__ == "__main__":
    unittest.main()
