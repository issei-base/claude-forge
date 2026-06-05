#!/usr/bin/env python3
"""make-kadai: 受講生カリキュラムシートの「次回までの宿題（課題欄）」を
決定的に特定し、Sheets API 経由で読み書きするスクリプト。

課題文そのものの生成はモデル側（SKILL.md のワークフロー）がやる。ここがやるのは
「どのセルに書くか」の特定と、実際の read/write という、目視に任せると事故る部分の
固定。ohayou の detect_lessons.py と同じ思想（検知をモデルに委ねず決定的に）。

シート構造の前提（SAMURAI ENGINEER カリキュラムシート・実データで確認）:
  - ある行に「1回目レッスン」「2回目レッスン」… のヘッダが並ぶ → これが lesson→列 の対応。
  - 別の行の先頭セルが「次回までの宿題…」 → これが課題行。
  - 課題セル = (課題行, N回目レッスンの列)。受講生ごとに行がズレても、ラベルで引くので壊れない。

認証: Google Sheets API は gws CLI 経由で叩く（gws は独自の検証済み OAuth
  クライアントを使うので、gcloud 既定クライアントの spreadsheets スコープ
  ブロックを回避できる）。未認証/失効なら `gws auth login` を促して止まる
  （破壊的操作の前で勝手に進めない）。

使い方:
  python3 sheet_kadai.py auth-check
  python3 sheet_kadai.py read  --url <URL> [--lesson N]
  python3 sheet_kadai.py write --url <URL> (--lesson N | --cell A1) --value-file <path> [--overwrite]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

# zenkaku → hankaku 数字（「１回目」のような全角表記に備える）
_Z2H = str.maketrans("０１２３４５６７８９", "0123456789")
LESSON_HDR_RE = re.compile(r"^\s*(\d+)\s*回目")
KADAI_LABEL = "次回までの宿題"
PLAN_LABEL = "次回レッスンの内容"      # その回のレッスンで扱う予定 → 宿題を整合させるヒント
TAUGHT_LABEL = "レッスンで指導した内容"  # 直近に教えた内容 → 自然な次ステップのヒント


class SkillError(Exception):
    """ユーザーに見せるべき、復旧手順つきのエラー。"""


# ---------------------------------------------------------------------------
# 純粋関数（ネットワーク非依存・unittest 対象）
# ---------------------------------------------------------------------------

def parse_sheet_url(url: str) -> tuple[str, int | None]:
    """スプレッドシート URL から (spreadsheet_id, gid) を取り出す。gid 無しは None。"""
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    if not m:
        # 素の ID をそのまま渡されたケースも許す
        if re.fullmatch(r"[a-zA-Z0-9_-]{20,}", url.strip()):
            return url.strip(), None
        raise SkillError(f"スプレッドシート URL から ID を取り出せません: {url!r}")
    sid = m.group(1)
    gm = re.search(r"[#&?]gid=(\d+)", url)
    return sid, (int(gm.group(1)) if gm else None)


def col_to_letters(col0: int) -> str:
    """0始まりの列番号を A1 表記の列文字へ（0→A, 25→Z, 26→AA）。"""
    if col0 < 0:
        raise ValueError("col index must be >= 0")
    s = ""
    n = col0 + 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def quote_title_for_a1(title: str) -> str:
    """A1 レンジ用にシート名をクォート。英数字と _ だけ・数字始まりでなければ素のまま。"""
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", title):
        return title
    return "'" + title.replace("'", "''") + "'"


def _norm(s: str) -> str:
    return (s or "").translate(_Z2H).strip()


def find_lesson_columns(values: list[list[str]]) -> dict[int, int]:
    """「N回目」ヘッダが最も多く並ぶ行を採用し、{lesson_number: col0} を返す。"""
    best: dict[int, int] = {}
    for row in values:
        found: dict[int, int] = {}
        for ci, cell in enumerate(row):
            m = LESSON_HDR_RE.match(_norm(cell))
            if m:
                found.setdefault(int(m.group(1)), ci)
        if len(found) > len(best):
            best = found
    return best


def find_row_by_label(values: list[list[str]], label: str) -> int:
    """先頭付近のセルに label を含む最初の行の 0始まり index。無ければ -1。"""
    for ri, row in enumerate(values):
        for cell in row[:3]:  # ラベルは行頭の数セルに入る
            if label in (cell or ""):
                return ri
    return -1


def find_kadai_row(values: list[list[str]]) -> int:
    """「次回までの宿題」課題行の 0始まり index。無ければ -1。"""
    return find_row_by_label(values, KADAI_LABEL)


def cell_at(values: list[list[str]], row0: int, col0: int) -> str:
    """ragged な values から安全にセル値を取る（範囲外は空文字）。"""
    if 0 <= row0 < len(values) and 0 <= col0 < len(values[row0]):
        return values[row0][col0] or ""
    return ""


def resolve_target(values: list[list[str]], lesson: int | None) -> dict:
    """課題行・lesson 列・対象セル・テンプレ（直近に埋まった課題）をまとめて返す。"""
    lesson_cols = find_lesson_columns(values)
    if not lesson_cols:
        raise SkillError("「N回目レッスン」ヘッダ行が見つかりません（対象シートの gid を確認）。")
    krow = find_kadai_row(values)
    if krow < 0:
        raise SkillError(f"「{KADAI_LABEL}」を含む課題行が見つかりません（対象シートの gid を確認）。")

    filled = [n for n in sorted(lesson_cols) if cell_at(values, krow, lesson_cols[n]).strip()]
    if lesson is None:
        empties = [n for n in sorted(lesson_cols) if not cell_at(values, krow, lesson_cols[n]).strip()]
        if not empties:
            raise SkillError("空きの課題セルがありません（全レッスン分が埋まっている）。--lesson で明示指定を。")
        lesson = empties[0]
    if lesson not in lesson_cols:
        raise SkillError(f"{lesson}回目レッスンの列がヘッダ行にありません。存在する列: {sorted(lesson_cols)}")

    col0 = lesson_cols[lesson]
    target_cell = f"{col_to_letters(col0)}{krow + 1}"
    template_lesson = filled[-1] if filled else None
    template_text = cell_at(values, krow, lesson_cols[template_lesson]) if template_lesson else ""

    # 文脈ヒント: 直前レッスンの「指導内容 / 次回レッスン予定」。宿題を整合させる材料。
    # （課題行と同じブロックの最初の出現を採用。複数月ブロックでも先頭=第1ブロック。）
    plan_row = find_row_by_label(values, PLAN_LABEL)
    taught_row = find_row_by_label(values, TAUGHT_LABEL)
    prev = lesson - 1
    prev_col = lesson_cols.get(prev)
    hints = {
        "prev_lesson": prev if prev_col is not None else None,
        # 直前回に書かれた「次回レッスンの内容」= このレッスンで扱う予定 → 宿題の主題
        "plan_for_this_lesson": cell_at(values, plan_row, prev_col) if (plan_row >= 0 and prev_col is not None) else "",
        # 直前回に教えた内容 → 自然な次ステップを選ぶ材料
        "prev_taught": cell_at(values, taught_row, prev_col) if (taught_row >= 0 and prev_col is not None) else "",
    }
    return {
        "kadai_row": krow + 1,
        "lesson_columns": {n: col_to_letters(c) for n, c in sorted(lesson_cols.items())},
        "filled_lessons": filled,
        "template_lesson": template_lesson,
        "template_text": template_text,
        "hints": hints,
        "target": {
            "lesson": lesson,
            "cell": target_cell,
            "empty": not cell_at(values, krow, col0).strip(),
        },
    }


# ---------------------------------------------------------------------------
# ネットワーク層（gws CLI 経由）
#
# gws は独自の検証済み OAuth クライアントを使うので、gcloud 既定クライアントが
# spreadsheets スコープを弾く問題（"このアプリはブロックされます" / scope blocked）
# を回避できる。トークン管理・更新は gws に任せ、ここは sheets サブコマンドを叩く。
# ---------------------------------------------------------------------------

GWS_LOGIN_HINT = (
    "gws の認証が必要です（トークン失効 or 未認証）。一度だけ次を実行してください:\n\n"
    "  gws auth login\n\n"
    "（ブラウザが開くので受講生シートを編集できる Google アカウントで承認）\n"
    "その後もう一度このスキルを実行。"
)


def _gws(args: list[str], params: dict | None = None, json_body: dict | None = None) -> dict:
    """`gws sheets <args>` を叩いて JSON を返す。auth / API エラーは SkillError に変換。"""
    cmd = ["gws", "sheets", *args, "--format", "json"]
    if params is not None:
        cmd += ["--params", json.dumps(params, ensure_ascii=False)]
    if json_body is not None:
        cmd += ["--json", json.dumps(json_body, ensure_ascii=False)]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        raise SkillError("gws が見つかりません。Google Workspace CLI を入れてください。")

    # 本文 JSON は stdout、"Using keyring backend" 等の雑音は stderr に出る想定。
    data = None
    if out.stdout.strip():
        try:
            data = json.loads(out.stdout)
        except json.JSONDecodeError:
            data = None
    if data is None:
        blob = (out.stdout + "\n" + out.stderr).strip()
        if any(s in blob for s in ("expired or revoked", "invalid_grant", "authError")):
            raise SkillError(GWS_LOGIN_HINT + f"\n\n[gws] {blob[:300]}")
        raise SkillError(f"gws 実行に失敗しました:\n{blob[:500]}")

    if isinstance(data, dict) and "error" in data:
        err = data["error"] if isinstance(data["error"], dict) else {"message": str(data["error"])}
        msg, code = err.get("message", ""), err.get("code")
        if code == 401 or any(s in msg for s in ("expired or revoked", "invalid_grant")):
            raise SkillError(GWS_LOGIN_HINT + f"\n\n[gws] {msg[:300]}")
        if code == 403:
            raise SkillError(
                "このシートへの編集権限が無い可能性があります（403）。承認したアカウントが"
                f"対象シートを編集できるか確認してください。\n[gws] {msg}"
            )
        if code == 404:
            raise SkillError("スプレッドシートが見つかりません（404）。URL / 共有設定を確認してください。")
        raise SkillError(f"Sheets API エラー（{code}）: {msg}")
    return data


def check_auth() -> dict:
    """gws が oauth2 で認証済み＆トークンが生きているかを確認。ダメなら SkillError。

    注意: `gws auth status` は `--format` 引数を取らない（付けると 400 エラー）。
    プレーン出力が JSON なのでそのままパースする。access token が期限切れでも
    refresh token が生きていれば実 API 呼び出し時に gws が更新するので ok 扱い。
    refresh token 自体が revoked/expired のときだけ再ログインを促す。
    """
    try:
        out = subprocess.run(["gws", "auth", "status"],
                             capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        raise SkillError("gws が見つかりません。Google Workspace CLI を入れてください。")
    try:
        st = json.loads(out.stdout)
    except json.JSONDecodeError:
        st = {}
    if st.get("auth_method") != "oauth2" or not st.get("has_refresh_token"):
        raise SkillError(GWS_LOGIN_HINT)
    err = st.get("token_error") or ""
    if not st.get("token_valid") and any(s in err for s in ("expired", "revoked", "invalid_grant")):
        raise SkillError(GWS_LOGIN_HINT + (f"\n\n[gws] {err}" if err else ""))
    return {"auth": "ok", "token_valid": bool(st.get("token_valid"))}


def resolve_gid_title(sid: str, gid: int | None) -> str:
    meta = _gws(["spreadsheets", "get"],
                params={"spreadsheetId": sid, "fields": "sheets(properties(sheetId,title))"})
    sheets = [s["properties"] for s in meta.get("sheets", [])]
    if not sheets:
        raise SkillError("シート（タブ）が1つもありません。")
    if gid is None:
        return sheets[0]["title"]
    for p in sheets:
        if p.get("sheetId") == gid:
            return p["title"]
    raise SkillError(
        f"gid={gid} のタブが見つかりません。存在するタブ: "
        + ", ".join(f"{p['title']}(gid={p['sheetId']})" for p in sheets)
    )


def read_grid(sid: str, title: str) -> list[list[str]]:
    data = _gws(["spreadsheets", "values", "get"],
                params={"spreadsheetId": sid, "range": quote_title_for_a1(title),
                        "majorDimension": "ROWS"})
    return data.get("values", [])


def write_cell(sid: str, title: str, a1: str, value: str) -> dict:
    rng = f"{quote_title_for_a1(title)}!{a1}"
    return _gws(["spreadsheets", "values", "update"],
                params={"spreadsheetId": sid, "range": rng, "valueInputOption": "USER_ENTERED"},
                json_body={"values": [[value]]})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_auth_check(_args) -> int:
    print(json.dumps(check_auth(), ensure_ascii=False))
    return 0


def cmd_read(args) -> int:
    sid, gid = parse_sheet_url(args.url)
    title = resolve_gid_title(sid, gid)
    values = read_grid(sid, title)
    info = resolve_target(values, args.lesson)
    out = {
        "spreadsheet_id": sid,
        "gid": gid,
        "sheet_title": title,
        **info,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_write(args) -> int:
    if not args.cell and args.lesson is None:
        raise SkillError("--lesson N か --cell A1 のどちらかを指定してください。")
    with open(args.value_file, encoding="utf-8") as f:
        value = f.read()
    if not value.strip():
        raise SkillError(f"書き込む内容が空です: {args.value_file}")

    sid, gid = parse_sheet_url(args.url)
    title = resolve_gid_title(sid, gid)
    values = read_grid(sid, title)

    if args.cell:
        cell = args.cell.upper()
        lesson = None
    else:
        info = resolve_target(values, args.lesson)
        cell = info["target"]["cell"]
        lesson = info["target"]["lesson"]

    # クロバー防止: 既存セルが空でなければ --overwrite 必須
    m = re.fullmatch(r"([A-Z]+)(\d+)", cell)
    if not m:
        raise SkillError(f"セル指定が不正です: {cell}")
    col0 = sum((ord(ch) - 64) * 26 ** i for i, ch in enumerate(reversed(m.group(1)))) - 1
    row0 = int(m.group(2)) - 1
    existing = cell_at(values, row0, col0)
    if existing.strip() and not args.overwrite:
        raise SkillError(
            f"{cell} は既に埋まっています（先頭: {existing.strip()[:40]}…）。"
            "上書きするなら --overwrite を付けてください。"
        )

    write_cell(sid, title, cell, value)
    link = f"https://docs.google.com/spreadsheets/d/{sid}/edit"
    if gid is not None:
        link += f"#gid={gid}&range={cell}"
    print(json.dumps({
        "written": True, "cell": cell, "lesson": lesson,
        "chars": len(value), "overwrote": bool(existing.strip()), "link": link,
    }, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="受講生カリキュラムシートの課題欄を read/write する")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("auth-check", help="gws が認証済みか確認")

    pr = sub.add_parser("read", help="課題行・対象セル・テンプレを JSON で返す")
    pr.add_argument("--url", required=True)
    pr.add_argument("--lesson", type=int, default=None, help="対象レッスン番号。省略時は最初の空き")

    pw = sub.add_parser("write", help="課題セルに書き込む")
    pw.add_argument("--url", required=True)
    pw.add_argument("--lesson", type=int, default=None)
    pw.add_argument("--cell", default=None, help="A1 直接指定（--lesson の代わり）")
    pw.add_argument("--value-file", required=True)
    pw.add_argument("--overwrite", action="store_true")

    args = ap.parse_args(argv)
    handler = {"auth-check": cmd_auth_check, "read": cmd_read, "write": cmd_write}[args.cmd]
    try:
        return handler(args)
    except SkillError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
