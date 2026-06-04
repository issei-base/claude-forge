#!/usr/bin/env python3
"""生成 HTML の逐語ブロックを原典と機械照合する。doc-illustrate ワークフロー3.5の自動版。

`.quote` ブロックと `td.num`（数値セル）を生成 HTML から抜き出し、原典テキストに
そのまま在るかを確認する。「だいたい合ってる」を弾くための保存前ゲート。

照合は 2 段:
  - ハードトークン（数値+単位 / 「…」で括った語 / 英数字の識別子）… 原典に無ければ FAIL
    （上限・モデル ID・API 名・価格など、幻覚すると致命的なもの）
  - フラグメント全体 … 無ければ WARN（言い回しの差はありうるので人手確認をうながす）
空白は両側とも除去して比較する（AWS の「第 7 層」と「第7層」を同一視）。

使い方:
    python3 extract.py <URL> > source.txt
    python3 verify.py <generated.html> source.txt
終了コード: ハードトークンの欠落が 1 つでもあれば 1（CI 的に弾ける）。WARN だけなら 0。
"""
import sys
import re
import html as htmllib
from html.parser import HTMLParser

if sys.stdout.isatty():
    GREEN, RED, YEL, DIM, RST = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"
else:  # パイプ/キャプチャ時は色コードを出さない
    GREEN = RED = YEL = DIM = RST = ""


def norm(s):
    """空白（半角/全角/改行）をすべて落として比較しやすくする。"""
    return re.sub(r"\s+", "", htmllib.unescape(s))


class Picker(HTMLParser):
    """class に 'quote' を含む要素と、td.num のテキストを回収する。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []          # (kind, buf)
        self.quotes = []
        self.nums = []

    def handle_starttag(self, tag, attrs):
        cls = dict(attrs).get("class", "")
        kind = None
        if "quote" in cls.split():
            kind = "quote"
        elif tag == "td" and "num" in cls.split():
            kind = "num"
        if kind:
            self.stack.append([kind, []])

    def handle_data(self, data):
        if self.stack:
            self.stack[-1][1].append(data)

    def handle_endtag(self, tag):
        # quote/td.num はネストしない前提で、閉じ要素が来たら先頭を確定する
        if not self.stack:
            return
        if tag in ("div", "td", "blockquote", "pre", "p"):
            kind, buf = self.stack.pop()
            text = "".join(buf).strip()
            if text:
                (self.quotes if kind == "quote" else self.nums).append(text)


def hard_tokens(text):
    """欠落すると致命的なトークンを抜く: 数値+単位 / 「…」『…』 / 英数字識別子。"""
    toks = []
    for m in re.finditer(r"「([^」]+)」|『([^』]+)』", text):
        toks.append(m.group(1) or m.group(2))
    # 数値（単位付き許容）
    for m in re.finditer(r"\d[\d,\.]*\s*(?:TB|GB|MB|KB|PB|時間|分|秒|%|層|倍|回|個|ms)?", text):
        toks.append(m.group(0))
    # 英数字の識別子・API 名・コマンド（2 文字以上、日本語の助詞混入を避ける）
    for m in re.finditer(r"[A-Za-z][A-Za-z0-9_./:\-]{1,}", text):
        toks.append(m.group(0))
    # 重複除去、短すぎる純記号は捨てる
    seen, out = set(), []
    for t in toks:
        t = t.strip()
        if len(norm(t)) >= 2 and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def split_fragments(text):
    return [f for f in re.split(r"[／/|;\n]", text) if f.strip()]


def check(blocks, src_n, label):
    fails, warns = 0, 0
    for i, block in enumerate(blocks, 1):
        print(f"\n{label} #{i}: {DIM}{block[:90]}{RST}")
        for frag in split_fragments(block):
            frag_ok = norm(frag) in src_n
            tag = f"{GREEN}✓ verbatim{RST}" if frag_ok else f"{YEL}⚠ 要確認{RST}"
            print(f"  {tag}  {frag.strip()[:80]}")
            if not frag_ok:
                warns += 1
            for tok in hard_tokens(frag):
                if norm(tok) not in src_n:
                    print(f"      {RED}✗ FAIL token{RST} 「{tok}」 が原典に無い")
                    fails += 1
    return fails, warns


def _read(path):
    try:
        return open(path, encoding="utf-8").read()
    except FileNotFoundError:
        sys.exit(f"{RED}file not found: {path}{RST}")


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: verify.py <generated.html> <source.txt>")
    html_text = _read(sys.argv[1])
    src_n = norm(_read(sys.argv[2]))

    p = Picker()
    p.feed(html_text)

    if not p.quotes and not p.nums:
        # 逐語ブロックが 1 つも無い HTML は「検証していない」のと同じ。素通り (exit 0)
        # させると無検証の図解が保存前ゲートを通ってしまうので、失敗扱いにする。
        print(f"{RED}照合対象なし（.quote / td.num が見つからない）— 逐語ブロックを入れること{RST}")
        sys.exit(1)

    f1, w1 = check(p.quotes, src_n, ".quote")
    f2, w2 = check(p.nums, src_n, "td.num")
    fails, warns = f1 + f2, w1 + w2

    print(f"\n{'='*48}")
    print(f"FAIL(ハードトークン欠落): {fails}   WARN(要人手確認): {warns}")
    if fails:
        print(f"{RED}→ 数値/識別子が原典に無い。消すか原典の表記に直すこと。{RST}")
    elif warns:
        print(f"{YEL}→ ⚠ は言い回し差の可能性。原典と目視で照合してから保存。{RST}")
    else:
        print(f"{GREEN}→ すべて原典に逐語で存在。OK。{RST}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
