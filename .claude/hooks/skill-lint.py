#!/usr/bin/env python3
"""Stop hook: SKILL.md を編集したターンの終わりに skill ゲートを強制する。

2 つのゲートを持つ:

  1. **決定論的 lint** (`tests/lint_skills.py`) — name↔dir ズレ / description 欠落 /
     名前重複 / SKILL.md 欠落ディレクトリ。記事 (zenn dx_pm_product) の「Stop で
     決定論的ゲート、失敗なら exit 2 でブロック」パターン。`.claude/skills` か
     `tests` が working tree で dirty な時だけ走らせ、/tmp も汚さない。

  2. **global symlink drift** — claude-forge の skill を 1 つでも `~/.claude/skills`
     に symlink して global install していると、新しい skill を足したのに
     `install.sh` を再実行し忘れるとその skill だけ symlink されず、ダッシュボードの
     インベントリや他プロジェクトから見えなくなる (= 取りこぼし)。これを発生源で
     ブロックする。**この検査は local 限定** (`~/.claude/skills` が無い CI / fork
     では空振りして無害)。`tests/lint_skills.py` には入れない — GitHub Actions に
     `~/.claude` が無く必ず落ちるため、ローカルの hook 側にだけ置く。

挙動:
  - 問題なし                          → exit 0
  - lint NG / symlink drift あり      → 問題を stderr に出して exit 2 (停止をブロック)

脱出口: 環境変数 SKILL_LINT_HOOK=0 でこのフックを無効化。
無限ループ保険: stop_hook_active なら (一度リトライ済みなので) ブロックせず警告のみ。
"""

import json
import os
import subprocess
import sys


def _authored_skills(skills_dir):
    """`<repo>/.claude/skills/<name>/SKILL.md` を持つ skill 名 (scaffold は除外)。

    install.sh / tests の is_ignored_dir と同じ規則: `_`/`.` 始まりは scaffold、
    SKILL.md 無しの dir (retired/cron-only) は skill ではない。
    """
    names = []
    if not os.path.isdir(skills_dir):
        return names
    for name in sorted(os.listdir(skills_dir)):
        if name.startswith(("_", ".")):
            continue
        if os.path.isfile(os.path.join(skills_dir, name, "SKILL.md")):
            names.append(name)
    return names


def symlink_drift(skills_dir, home_skills_dir):
    """global symlink drift を (missing, linked) の skill 名リストで返す。

    `linked`  = `~/.claude/skills/<name>` がこの repo の skill dir を指している分。
    `missing` = この repo の skill だが上記に未リンクの分。

    呼び出し側は **`linked` が非空のときだけ** `missing` をエラー扱いすること
    (= このユーザーが「この repo を global install する」運用に乗っている時だけ)。
    project スコープのみの checkout / fork を誤検知しないためのゲート。realpath で
    比較するので symlink でも実体一致を見る (絶対パスのズレや別 repo への link は
    未リンク扱い)。
    """
    linked, missing = [], []
    for name in _authored_skills(skills_dir):
        src = os.path.realpath(os.path.join(skills_dir, name))
        dst = os.path.realpath(os.path.join(home_skills_dir, name))
        if dst == src:
            linked.append(name)
        else:
            missing.append(name)
    return missing, linked


def _skills_or_tests_dirty(project):
    """`.claude/skills` か `tests` が working tree で dirty か (git 不在なら True)。

    `-u` は新規 skill dir を `?? .claude/skills/<name>/` に collapse させずファイル
    単位で確実に拾うため (一番踏みやすい「新規 skill 追加」の取りこぼし防止)。
    tests/ も含めるのは lint ロジック/fixtures を tests/ 側だけ編集したターンでも
    ローカルゲートを効かせるため (CI と Codex hook は元々 tests/ も対象)。
    """
    try:
        st = subprocess.run(
            ["git", "-C", project, "status", "--porcelain", "-u", "--",
             ".claude/skills", "tests"],
            capture_output=True, text=True, timeout=10,
        )
        if st.returncode == 0:
            return bool(st.stdout.strip())
    except Exception:
        pass  # git 不在 → True (lint は安いので空振りでも害なし)
    return True


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

    problems = []  # (title, body) のリスト

    # ゲート 1: 決定論的 lint — skills/ か tests/ が dirty な時だけ (安い・スコープ済)。
    if _skills_or_tests_dirty(project):
        res = subprocess.run(
            [sys.executable, lint], capture_output=True, text=True, timeout=30
        )
        if res.returncode != 0:
            problems.append((
                "skill lint NG — SKILL.md を直してからターンを終えてください",
                res.stdout or res.stderr,
            ))

    # ゲート 2: global symlink drift — 毎ターン検査 (drift は working tree が clean
    # でも残るため dirty ゲートに乗せない)。stat 十数回なので毎回でも軽い。
    home = os.path.join(os.path.expanduser("~"), ".claude", "skills")
    missing, linked = symlink_drift(os.path.join(project, ".claude", "skills"), home)
    if linked and missing:
        problems.append((
            "global symlink が古い — 足した skill が ~/.claude/skills に未リンク",
            "未リンク: " + ", ".join(missing) + "\n"
            "→ `./install.sh` を実行して global symlink を同期してください。"
            "未リンクのままだと、ダッシュボードのインベントリや他プロジェクトから"
            "その skill が見えません (= 取りこぼし)。",
        ))

    if not problems:
        return 0

    sys.stderr.write("⛔ skill ゲート:\n\n")
    for title, body in problems:
        sys.stderr.write(f"■ {title}\n{body}\n\n")
    sys.stderr.write("(無効化: 環境変数 SKILL_LINT_HOOK=0)\n")

    if data.get("stop_hook_active"):
        # 既に一度ブロック→リトライ済み。直せていない＝ループ防止のため通す。
        sys.stderr.write("(retry 済みのため今回は停止を許可)\n")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
