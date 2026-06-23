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

# そのセグメントが git push を起動しているか (`git push`, `/usr/bin/git push`,
# `git -c foo=bar push` 等を許容)。
GIT_PUSH = re.compile(r"\bgit\b[^\n]*?\bpush\b", re.IGNORECASE)

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
    """command 内に「宛先が main/master の git push」セグメントがあれば True。"""
    for segment in SEGMENT_SPLIT.split(command):
        if GIT_PUSH.search(segment) and PROTECTED_REF.search(segment):
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
