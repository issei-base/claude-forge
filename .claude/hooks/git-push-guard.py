#!/usr/bin/env python3
"""PreToolUse hook: main/master への直接 push を harness 層で deny する。

claude-forge の方針 (CLAUDE.md): 「main への直接 push は禁止 (ship skill の hard
guard)」。その守りは今まで ship / create-pr の散文ガードだけで、skill を経由しない
素の `git push origin main` は素通りだった。これを **どの経路 (skill 経由でも素の
Bash でも) でも効く PreToolUse の deny に格上げ**する。

着想は ZOZO SOC Agent の記事 (techblog.zozo.com/entry/soc-claude-agent) の
「危険な tool 呼び出しを PreToolUse hook + 正規表現で機械 deny する」パターン。
あちらは MCP の書き込み系クエリを禁止しているが、ここでは Bash の
「宛先が保護ブランチの git push」だけを禁止する。

**スコープは意図的に最小**:
- `rm -rf` / `rm -fr` / `sudo` / `ssh` / `scp` は既に settings.json の
  permissions.deny でブロック済みなので、ここでは扱わない (重複させない)。
- force push は「ユーザーの明示確認があれば可」(pr-conventions.md) なので
  hard-deny にしない。ただし `git push --force origin main` のように宛先が
  main/master なら、保護ブランチ宛てとしてここで弾かれる。

**限界 (正直に明記)**: hook は実行されるコマンド文字列しか見えない。`git push`
だけ (引数なし) を main 上で実行する形は、文字列に main が現れないので検知でき
ない。その経路は ship 側の「main にいたら先にブランチを切る」運用でカバーする。

挙動:
  - 保護ブランチ宛ての push を検知 → permissionDecision: deny (exit 0 + JSON)
  - それ以外 / 解析不能 / git push でない → 何も出さず exit 0 (通常フローに委ねる)

PreToolUse の deny は `hookSpecificOutput.permissionDecision: "deny"` で返す
(exit 2 ではなく JSON。settings の update-config skill の作法に合わせる)。
"""
import json
import re
import sys

# コマンドを論理セグメントに割る (&&, ||, ;, |, 改行)。複合コマンドの中の
# git push だけを正しく見るため。クォート内の区切りは無視しないが、git push の
# refspec 解析にはこの粒度で十分。
SEGMENT_SPLIT = re.compile(r"&&|\|\||;|\||\n")

# git のグローバルオプションのうち「次のトークンを引数に取る」もの。push が
# サブコマンドかを判定する際に値ごと読み飛ばす (例: `git -c k=v push ...`)。
_GIT_OPTS_WITH_ARG = {"-c", "-C", "--git-dir", "--work-tree", "--namespace", "--exec-path"}


def is_git_push_command(segment: str) -> bool:
    """segment が実際に `git push ...` を **起動** しているか。

    `gh pr create --body "...git push origin main..."` や
    `git commit -m "あとで git push origin main"` のように、git push が
    コマンドではなく引数・メッセージ・本文として現れるだけのケースを誤検知しない
    ため、(1) コマンド語が git か (2) 最初の位置引数 (= サブコマンド) が push か、
    の 2 段で判定する。単純な部分一致 (`\\bgit\\b.*push`) はこの誤検知を起こす。
    """
    toks = segment.strip().split()
    i = 0
    # 先頭の環境変数代入 (FOO=bar git ...) と sudo/exec 系ラッパを読み飛ばす。
    while i < len(toks) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", toks[i]):
        i += 1
    while i < len(toks) and toks[i] in ("sudo", "command", "exec", "nice", "nohup"):
        i += 1
    # コマンド語が git / *(/)git でなければ git push ではない (gh, echo, grep 等を除外)。
    if i >= len(toks) or (toks[i] != "git" and not toks[i].endswith("/git")):
        return False
    # git の最初の位置引数 = サブコマンド。グローバルオプションは読み飛ばす。
    j = i + 1
    while j < len(toks):
        t = toks[j]
        if t in _GIT_OPTS_WITH_ARG:
            j += 2
            continue
        if t.startswith("-"):
            j += 1
            continue
        return t == "push"
    return False


# 宛先 refspec が main / master を指すトークン。
#   main / master            … ブランチ名直指定
#   +main                    … 強制 refspec
#   HEAD:main / local:master … src:dst の dst 側
#   refs/heads/main          … フルパス
# `feature/main` `mymain` `main-thing` のように単なる部分一致は弾かない
# (ref トークンがちょうど main/master で終わる時だけマッチ)。
PROTECTED_REF = re.compile(
    r"(?:^|\s)\+?(?:[^\s:]*:)?(?:refs/heads/)?(?:main|master)(?=\s|$)",
    re.IGNORECASE,
)


def is_push_to_protected(command: str) -> bool:
    """command 内に「宛先が main/master の git push」セグメントがあれば True。

    限界: セグメント分割は &&/||/;/|/改行 で行うため、heredoc 本文の行がそれ単体で
    ちょうど `git push origin main` という形になっている場合は誤検知しうる。PR 本文
    等を渡す時は `--body-file` を使えば回避できる。
    """
    for segment in SEGMENT_SPLIT.split(command):
        if is_git_push_command(segment) and PROTECTED_REF.search(segment):
            return True
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # 解析不能なら通常フローに委ねる (fail open)

    if payload.get("tool_name") != "Bash":
        return 0

    command = (payload.get("tool_input") or {}).get("command", "")
    if not isinstance(command, str) or not command:
        return 0

    if is_push_to_protected(command):
        reason = (
            "main/master への直接 push は claude-forge の方針で禁止です "
            "(CLAUDE.md / ship の hard guard)。feature ブランチを切って PR を出し、"
            "merge は人間が GitHub UI で行ってください。どうしても自分で main に "
            "push する必要があれば、Claude 経由ではなく自分のシェルで実行するか、"
            "このターンだけ /hooks で無効化してください。"
        )
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
