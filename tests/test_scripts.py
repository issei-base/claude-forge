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
        self.assertTrue(is_ignored_dir("ohayou"))
        self.assertTrue(is_ignored_dir("lesson-homework"))
        self.assertTrue(is_ignored_dir("x-buzz"))

    def test_real_skill_not_ignored(self):
        self.assertFalse(is_ignored_dir("ship"))


class TestVerifyTokens(unittest.TestCase):
    def test_norm_strips_whitespace(self):
        self.assertEqual(vfy.norm("第 7 層"), "第7層")

    def test_hard_tokens_quotes_and_nums(self):
        toks = vfy.hard_tokens("上限は「100GB」で API は GetObject")
        self.assertIn("100GB", toks)
        self.assertIn("GetObject", toks)


if __name__ == "__main__":
    unittest.main()
