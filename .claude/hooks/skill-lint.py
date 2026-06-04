#!/usr/bin/env python3
"""Stop hook: SKILL.md を編集したターンの終わりに skill lint を強制する。

記事 (zenn dx_pm_product) の「Stop で決定論的ゲート、失敗なら exit 2 でブロック」
パターンを claude-forge 用に最適化したもの。記事の二段構え (PostToolUse で marker →
Stop で重い検査) は採らない: ここの検査 (tests/lint_skills.py) は一瞬なので marker の
性能上の意味がなく、代わりに git で「SKILL.md が working tree で dirty な時だけ」に
スコープする。これなら Claude の編集も外部エディタの編集も拾え、/tmp も汚さない。

挙動:
  - SKILL.md が dirty でない → 何もせず exit 0
  - dirty かつ lint OK        → exit 0
  - dirty かつ lint ERROR     → エラーを stderr に出して exit 2 (ターンの停止をブロック)

脱出口: 環境変数 SKILL_LINT_HOOK=0 でこのフックを無効化。
無限ループ保険: stop_hook_active なら (一度リトライ済みなので) ブロックせず警告のみ。
"""

import json
import os
import subprocess
import sys


def main():
    if os.environ.get("SKILL_LINT_HOOK") == "0":
        return 0

    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}

    project = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
    lint = os.path.join(project, "tests", "lint_skills.py")
    if not os.path.exists(lint):
        return 0  # claude-forge 以外 / lint 不在 → no-op

    # skills/ ツリーが dirty な時だけ動く (git が無ければ保険で常に lint)。
    # `-u` で untracked をファイル単位に展開する: これが無いと新規 skill dir が
    # `?? .claude/skills/<name>/` (末尾スラッシュ) に collapse され、SKILL.md 名で
    # マッチできず lint を取りこぼす — 一番踏みやすい「新規 skill 追加」が素通りする。
    # マッチも SKILL.md 末尾でなく skills/ パス全体に緩め、安いので迷ったら走らせる。
    dirty = True
    try:
        st = subprocess.run(
            ["git", "-C", project, "status", "--porcelain", "-u", "--", ".claude/skills"],
            capture_output=True, text=True, timeout=10,
        )
        if st.returncode == 0:
            dirty = any(
                ".claude/skills/" in line for line in st.stdout.splitlines()
            )
    except Exception:
        pass  # git 不在 → dirty=True のまま (lint は安いので空振りでも害なし)

    if not dirty:
        return 0

    res = subprocess.run(
        [sys.executable, lint], capture_output=True, text=True, timeout=30
    )
    if res.returncode == 0:
        return 0

    sys.stderr.write("⛔ skill lint failed — SKILL.md を直してからターンを終えてください:\n\n")
    sys.stderr.write(res.stdout or res.stderr)
    sys.stderr.write("\n(無効化: 環境変数 SKILL_LINT_HOOK=0)\n")

    if data.get("stop_hook_active"):
        # 既に一度ブロック→リトライ済み。直せていない＝ループ防止のため通す。
        sys.stderr.write("(retry 済みのため今回は停止を許可)\n")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
