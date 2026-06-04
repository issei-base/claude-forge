#!/usr/bin/env python3
"""x-buzz の投稿候補を決定的に検証し、dedup する。

モデルの目検に任せず「文字数・ハッシュタグ過多・本文内 URL・エンゲージ乞食・
過去投稿との重複」を機械的に弾く。reach を削る要因 (本文 URL ~30-50% 減、
3+ ハッシュタグ ~40% 減、丸コピ/連投の spam 判定) を投稿前に潰すのが目的。

標準ライブラリのみ。cwd が repo 直下でなくても動くよう、ログは既定で
リポジトリ root からの相対 (data/x_buzz_posted.jsonl) を解決する。

使い方:
  # 検証 (候補 JSON を渡す。配列 of string か 配列 of {id?,text})
  python3 validate_post.py candidates.json
  cat candidates.json | python3 validate_post.py -

  # 投稿/予約したものを dedup ログに記録 (翌回ダブらせない)
  python3 validate_post.py --mark candidates.json

入力フォーマット (どちらでも可):
  ["本文1", "本文2 ..."]
  [{"id": "a", "text": "本文..."}, ...]

スレッドは Typefully の慣習に合わせ「空行4連続 (\\n\\n\\n\\n)」で分割して
各ツイートを個別に検証する。
"""

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

# --- X の weighted length (CJK 等は 2 カウント、上限 280 = 日本語 ~140 字) ---
# https://developer.x.com/en/docs/counting-characters の weighted ranges。
_WIDE_RANGES = [
    (0x1100, 0x115F), (0x2E80, 0x303E), (0x3041, 0x33FF), (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF), (0xA000, 0xA4CF), (0xAC00, 0xD7A3), (0xF900, 0xFAFF),
    (0xFE30, 0xFE4F), (0xFF00, 0xFF60), (0xFFE0, 0xFFE6),
]
TWEET_LIMIT = 280  # 標準アカウント。X Premium は更に長いが安全側で 280 を基準にする。

# URL は 23 文字固定でカウントされる (t.co 短縮)。
_URL_RE = re.compile(r"https?://\S+")
_HASHTAG_RE = re.compile(r"(?:^|\s)#\w[\w぀-ヿ一-鿿]*")
_THREAD_SPLIT_RE = re.compile(r"\n{4,}")

# エンゲージ乞食 / spam フラグ語 (JP X で spam 判定されやすい)。
_BAIT_PATTERNS = [
    (r"いいね.{0,4}(で|したら|くれたら).{0,8}(配布|プレゼント|無料)", "いいね乞食 (配布系)"),
    (r"(RT|リポスト|拡散).{0,4}(で|したら|お願い).{0,8}(配布|プレゼント|抽選)", "RT乞食"),
    (r"フォロー\s*[&＆と]\s*(RT|リポスト|いいね)", "フォロー&RT 乞食"),
    (r"(抽選|プレゼント企画).{0,8}(フォロー|RT|いいね)", "懸賞ばら撒き"),
]


def weighted_len(text: str) -> int:
    """X 仕様の重み付き文字数。URL は 23 固定、CJK 等は 2。"""
    # URL を 23 文字のプレースホルダに置換してからカウント。
    stripped = _URL_RE.sub("x" * 23, text)
    total = 0
    for ch in stripped:
        cp = ord(ch)
        if any(lo <= cp <= hi for lo, hi in _WIDE_RANGES):
            total += 2
        else:
            total += 1
    return total


def split_tweets(text: str) -> list:
    return [t.strip() for t in _THREAD_SPLIT_RE.split(text.strip()) if t.strip()]


def _normalize(text: str) -> str:
    """dedup 用の正規化シグネチャ素材: NFKC・小文字・記号/空白除去。"""
    t = unicodedata.normalize("NFKC", text).lower()
    t = _URL_RE.sub("", t)
    t = re.sub(r"[\s\W_]+", "", t, flags=re.UNICODE)
    return t


def _tokens(text: str) -> set:
    t = unicodedata.normalize("NFKC", text).lower()
    t = _URL_RE.sub("", t)
    # 日本語は分かち書きしないので 2-gram + ラテン語単語の混在で粗く近似。
    words = set(re.findall(r"[a-z0-9]+", t))
    cjk = re.sub(r"[^぀-ヿ一-鿿]", "", t)
    bigrams = {cjk[i:i + 2] for i in range(len(cjk) - 1)}
    return words | bigrams


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _sig(text: str) -> str:
    return hashlib.sha256(_normalize(text).encode("utf-8")).hexdigest()[:16]


def repo_root() -> Path:
    """scripts/ から 4 つ上が repo root (.claude/skills/x-buzz/scripts/ → repo root)。"""
    return Path(__file__).resolve().parents[4]


def default_log() -> Path:
    return repo_root() / "data" / "x_buzz_posted.jsonl"


def load_log(log_path: Path) -> list:
    if not log_path.exists():
        return []
    out = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def load_candidates(src: str) -> list:
    raw = sys.stdin.read() if src == "-" else Path(src).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError(
            f"トップレベルは配列であること (got {type(data).__name__})。"
            ' 形式: ["本文1", ...] か [{"text": "本文"}, ...]'
        )
    posts = []
    for i, item in enumerate(data):
        if isinstance(item, str):
            posts.append({"id": str(i), "text": item})
        elif isinstance(item, dict) and "text" in item:
            posts.append({"id": str(item.get("id", i)), "text": item["text"]})
        else:
            raise ValueError(f"候補 {i} が string でも {{text}} でもない")
    return posts


def validate(posts: list, log: list, sim_threshold: float = 0.55, recent: int = 200) -> dict:
    log_recent = log[-recent:]
    log_sigs = {e.get("sig") for e in log_recent}
    log_tokens = [(e.get("text", ""), _tokens(e.get("text", ""))) for e in log_recent]

    results = []
    for p in posts:
        text = p["text"]
        tweets = split_tweets(text)
        issues = []

        for n, tw in enumerate(tweets, 1):
            wl = weighted_len(tw)
            if wl > TWEET_LIMIT:
                issues.append(f"tweet{n}: {wl}/{TWEET_LIMIT} 字超過 (日本語 ~140字)")

        hashtags = _HASHTAG_RE.findall(text)
        if len(hashtags) > 1:
            issues.append(f"ハッシュタグ {len(hashtags)}個 (推奨 0-1。3+ で spam 判定 ~40% reach 減)")

        urls = _URL_RE.findall(text)
        if urls:
            issues.append(f"本文に URL {len(urls)}個 (~30-50% reach 減。リンクは返信に回す)")

        for pat, label in _BAIT_PATTERNS:
            if re.search(pat, text):
                issues.append(f"エンゲージ乞食検出: {label}")

        # dedup
        sig = _sig(text)
        exact = sig in log_sigs
        toks = _tokens(text)
        max_sim, similar_to = 0.0, None
        for ltext, ltoks in log_tokens:
            s = _jaccard(toks, ltoks)
            if s > max_sim:
                max_sim, similar_to = s, ltext[:40]
        near_dup = (not exact) and max_sim >= sim_threshold

        if exact:
            issues.append("過去投稿と完全重複")
        elif near_dup:
            issues.append(f"過去投稿に類似 (Jaccard {max_sim:.2f}): 「{similar_to}…」")

        results.append({
            "id": p["id"],
            "tweet_count": len(tweets),
            "weighted_lengths": [weighted_len(t) for t in tweets],
            "issues": issues,
            "ok": not issues,
            "sig": sig,
            "exact_dup": exact,
            "max_similarity": round(max_sim, 3),
        })

    return {
        "total": len(results),
        "ok": sum(1 for r in results if r["ok"]),
        "flagged": sum(1 for r in results if not r["ok"]),
        "results": results,
    }


def mark(posts: list, log_path: Path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    with log_path.open("a", encoding="utf-8") as f:
        for p in posts:
            rec = {"sig": _sig(p["text"]), "text": p["text"], "marked_at": now}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser(description="x-buzz 投稿候補の検証 / dedup")
    ap.add_argument("source", nargs="?", default="-",
                    help="候補 JSON のパス。'-' で stdin (既定)")
    ap.add_argument("--mark", action="store_true",
                    help="検証せず、候補を dedup ログに記録する (投稿/予約後に呼ぶ)")
    ap.add_argument("--log", default=None, help="dedup ログのパス (既定: data/x_buzz_posted.jsonl)")
    ap.add_argument("--sim", type=float, default=0.55, help="類似重複とみなす Jaccard 閾値")
    args = ap.parse_args()

    log_path = Path(args.log) if args.log else default_log()
    try:
        posts = load_candidates(args.source)
    except FileNotFoundError:
        sys.exit(f"入力ファイルが無い: {args.source}")
    except json.JSONDecodeError as e:
        sys.exit(f"候補 JSON のパースに失敗: {e}")
    except ValueError as e:
        sys.exit(str(e))

    if args.mark:
        mark(posts, log_path)
        print(json.dumps({"marked": len(posts), "log": str(log_path)}, ensure_ascii=False))
        return

    report = validate(posts, load_log(log_path), sim_threshold=args.sim)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    # flagged があれば非ゼロ終了 (cron / 呼び出し側が気づけるように)。
    sys.exit(1 if report["flagged"] else 0)


if __name__ == "__main__":
    main()
