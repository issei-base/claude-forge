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

**設計方針 — fail-closed**: これは user 設定の `Bash(git:*)` allow を素通りした
push を止める唯一の機械ゲートなので、「すり抜け < 誤 deny」に倒す。
セグメント分割はクォートの内側でも容赦なく行うため、クォート文字列の中に
制御演算子ごと `git push origin main` が埋まっていると誤 deny しうる
(例: `git commit -m "x && git push origin main"`)。その場合はメッセージを
言い換えるか `--file` / `--body-file` 系で本文をファイル渡しにすれば回避できる。

**限界 (正直に明記)**: hook は実行されるコマンド文字列しか見えない。
- `git push` だけ (引数なし) を main 上で実行する形は、文字列に main が現れない
  ので検知できない。ship 側の「main にいたら先にブランチを切る」運用でカバー。
- `git push origin "$BRANCH"` のような変数展開後の値も見えない (展開前に判定)。
- スクリプトファイル経由 (`./deploy.sh` の中の push) も見えない。

挙動:
  - 保護ブランチ宛ての push を検知 → permissionDecision: deny (exit 0 + JSON)
  - それ以外 / 解析不能 / git push でない → 何も出さず exit 0 (通常フローに委ねる)

PreToolUse の deny は `hookSpecificOutput.permissionDecision: "deny"` で返す
(exit 2 ではなく JSON。settings の update-config skill の作法に合わせる)。
"""
import json
import re
import shlex
import sys

# コマンドを論理セグメントに割る: 制御演算子 (&&, ||, ;, |, &, 改行) に加え、
# サブシェル/コマンド置換の括弧・バッククォート、リダイレクト (>, <) も区切る。
# `(cd x && git push origin main)` の閉じ括弧や `... main >log` のリダイレクトが
# ref トークンに癒着して検知を外すのを防ぐ。クォートの内側でも割る (fail-closed、
# 上の設計方針を参照)。
SEGMENT_SPLIT = re.compile(r"&&|\|\||;|\||\n|&|\(|\)|`|[<>]+")

# git のグローバルオプションのうち「次のトークンを引数に取る」もの。push が
# サブコマンドかを判定する際に値ごと読み飛ばす (例: `git -c k=v push ...`)。
_GIT_OPTS_WITH_ARG = {"-c", "-C", "--git-dir", "--work-tree", "--namespace", "--exec-path"}

# コマンド語の前に透過的に挟まるラッパ。読み飛ばして実コマンドを見る。
_TRANSPARENT_WRAPPERS = {
    "sudo", "command", "exec", "nice", "nohup", "env", "time", "builtin",
    "xargs", "stdbuf", "caffeinate",
}
# 数値/時間の位置引数を 1 つ取ってから実コマンドが来るラッパ (timeout 60 git ...)。
_DURATION_WRAPPERS = {"timeout", "gtimeout"}
# -c '<コマンド文字列>' を実行するシェル。引数文字列を再帰的に検査する。
_SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish"}

_ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

PROTECTED_BRANCHES = {"main", "master"}


def _tokens(segment):
    """segment を shell 風にトークン化する。クォート (`"main"` / `'main'`) と
    バックスラッシュ (`\\git`) は shlex が解決する。SEGMENT_SPLIT の巻き添えで
    クォートが千切れて shlex が失敗したら、クォート記号を剥がす粗いフォール
    バックで続行する (fail-closed 方向)。"""
    try:
        return shlex.split(segment, posix=True)
    except ValueError:
        return [t.strip("\"'") for t in segment.split()]


def _command_index(toks):
    """環境変数代入 (FOO=bar) とラッパ (env/sudo/time/timeout...) を読み飛ばし、
    実コマンド語の index を返す。見つからなければ None。"""
    i = 0
    while i < len(toks):
        t = toks[i]
        if _ENV_ASSIGN.match(t):
            i += 1
            continue
        base = t.rsplit("/", 1)[-1]
        if base in _TRANSPARENT_WRAPPERS:
            i += 1
            # ラッパ自身のオプションを読み飛ばす (env -u NAME は引数ごと)。
            while i < len(toks) and toks[i].startswith("-"):
                i += 2 if (base == "env" and toks[i] == "-u") else 1
            continue
        if base in _DURATION_WRAPPERS:
            i += 1
            while i < len(toks) and toks[i].startswith("-"):
                i += 1
            i += 1  # duration の位置引数 (timeout 60 → "60")
            continue
        return i
    return None


def _ref_is_protected(tok):
    """push の位置引数 1 トークンが main/master を宛先に含むか。
    `+main` / `HEAD:main` / `refs/heads/main` / それらの複合を解決する。
    `feature/main-thing` `mymain` のような部分一致は弾かない。"""
    tok = tok.lstrip("+")
    if ":" in tok:
        tok = tok.rsplit(":", 1)[-1]  # src:dst の dst 側
    if tok.startswith("refs/heads/"):
        tok = tok[len("refs/heads/"):]
    return tok.lower() in PROTECTED_BRANCHES


def is_git_push_command(segment):
    """segment が実際に `git push ...` を **起動** しているか。

    `gh pr create --body "...git push origin main..."` や
    `git commit -m "あとで git push origin main"` のように、git push が
    コマンドではなく引数・メッセージ・本文として現れるだけのケースを誤検知しない
    ため、(1) コマンド語が git か (2) 最初の位置引数 (= サブコマンド) が push か、
    の 2 段で判定する。単純な部分一致 (`\\bgit\\b.*push`) はこの誤検知を起こす。
    """
    return _push_arg_start(_tokens(segment)) is not None


def _push_arg_start(toks):
    """toks が git push の起動なら push 引数の開始 index、でなければ None。"""
    i = _command_index(toks)
    if i is None:
        return None
    base = toks[i].rsplit("/", 1)[-1]
    if base != "git":
        return None
    j = i + 1
    while j < len(toks):
        t = toks[j]
        if t in _GIT_OPTS_WITH_ARG:
            j += 2
            continue
        if t.startswith("-"):
            j += 1
            continue
        return j + 1 if t == "push" else None
    return None


def _segment_pushes_protected(toks, depth):
    i = _command_index(toks)
    if i is None:
        return False
    base = toks[i].rsplit("/", 1)[-1]
    # `bash -c "git push origin main"` — シェルに渡すコマンド文字列を再帰検査。
    if base in _SHELLS and depth < 3:
        for k in range(i + 1, len(toks) - 1):
            if toks[k] == "-c" and _is_push_to_protected(toks[k + 1], depth + 1):
                return True
        return False
    start = _push_arg_start(toks)
    if start is None:
        return False
    for t in toks[start:]:
        if t.startswith("-"):
            continue  # push のオプション (--force / --repo=x 等) は ref でない
        if _ref_is_protected(t):
            return True
    return False


def _is_push_to_protected(command, depth):
    for segment in SEGMENT_SPLIT.split(command):
        if _segment_pushes_protected(_tokens(segment), depth):
            return True
    return False


def is_push_to_protected(command):
    """command 内に「宛先が main/master の git push」セグメントがあれば True。

    ラッパ (env/time/timeout/sudo...)・サブシェルの括弧・クォートされた ref
    (`"main"`)・`bash -c "..."`・リダイレクト付きも検知する。誤 deny 側の限界は
    冒頭 docstring「設計方針 — fail-closed」を参照。
    """
    return _is_push_to_protected(command, 0)


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
