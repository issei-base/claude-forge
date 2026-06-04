#!/usr/bin/env python3
"""原典を「生テキスト」で取り出す。doc-illustrate ワークフロー1の決定論版。

要約モデルを一切挟まずに、公式ページから素の本文を吐く。ソース種別を URL で
自動判別する:
  - docs.aws.amazon.com            → main-col-body の本文だけを抽出（一次ソース）
  - docs.claude.com / anthropic    → URL 末尾に .md を付けて整形済み markdown を取得
  - それ以外（発表/マーケ等）       → 生 HTML を取り、タグを剥いだ本文

使い方:
    python3 extract.py <URL>                # stdout に本文
    python3 extract.py <URL> > source.txt   # verify.py に渡す原典として保存

stdlib のみ（依存ゼロ）。文字化けは utf-8/replace で吸収する。
注意: AWS の ja_jp は機械翻訳。技術用語の厳密さは英語原典が正（SKILL.md 参照）。
"""
import sys
import re
import gzip
import html as htmllib
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.error import URLError

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# タグを剥いだ後に消したい定型ノイズ（AWS の noscript 文言など）
NOISE = [
    "翻訳は機械翻訳により提供されています",
    "ブラウザで JavaScript が無効",
    "AWS ドキュメントを使用するには",
    "手順については、使用するブラウザのヘルプページ",
]

BLOCK = {"p", "div", "section", "article", "tr", "br", "ul", "ol",
         "table", "header", "h1", "h2", "h3", "h4", "h5", "h6"}
SKIP = {"script", "style", "noscript", "nav", "svg", "head"}


def fetch(url):
    req = Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with urlopen(req, timeout=30) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
    return raw.decode("utf-8", "replace")


class TextExtractor(HTMLParser):
    """ブロック要素で改行を入れつつ素のテキストを集める。
    only_id を渡すと、その id を持つ要素のサブツリーだけを対象にする（AWS 用）。"""

    def __init__(self, only_id=None):
        super().__init__(convert_charrefs=True)
        self.only_id = only_id
        self.capture = only_id is None  # id 指定が無ければ最初から拾う
        self.depth = 0          # capture 開始要素からのネスト深さ
        self.skip_depth = 0     # script/style 等の中なら >0
        self.out = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if self.only_id and not self.capture and a.get("id") == self.only_id:
            self.capture = True
            self.depth = 0
        if self.capture:
            self.depth += 1
            if tag in SKIP:
                self.skip_depth += 1
            elif self.skip_depth == 0:
                if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                    self.out.append("\n\n## ")
                elif tag == "li":
                    self.out.append("\n- ")
                elif tag in BLOCK:
                    self.out.append("\n")

    def handle_endtag(self, tag):
        if not self.capture:
            return
        if tag in SKIP and self.skip_depth > 0:
            self.skip_depth -= 1
        self.depth -= 1
        if self.only_id and self.depth <= 0:
            self.capture = False  # 対象サブツリーを抜けた

    def handle_data(self, data):
        if self.capture and self.skip_depth == 0:
            self.out.append(data)

    def text(self):
        t = htmllib.unescape("".join(self.out))
        t = re.sub(r"[ \t]+\n", "\n", t)
        t = re.sub(r"\n{3,}", "\n\n", t)
        lines = [ln.rstrip() for ln in t.splitlines()]
        lines = [ln for ln in lines if not any(n in ln for n in NOISE)]
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def to_md_url(url):
    """Mintlify (docs.claude.com / docs.anthropic.com) は .md を付けると素の markdown。"""
    m = re.match(r"(https?://[^?#]+?)(/?)([?#].*)?$", url)
    base = m.group(1)
    if base.endswith(".md"):
        return url
    return base.rstrip("/") + ".md"


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: extract.py <URL>")
    url = sys.argv[1]
    try:
        if re.search(r"docs\.(claude\.com|anthropic\.com)", url):
            # 整形済み markdown をそのまま（要約モデルを挟まない一次ソース）
            print(fetch(to_md_url(url)))
        elif "docs.aws.amazon.com" in url:
            p = TextExtractor(only_id="main-col-body")
            p.feed(fetch(url))
            out = p.text()
            if not out:  # 構造が変わっていたら全文フォールバック
                p2 = TextExtractor()
                p2.feed(fetch(url))
                out = p2.text()
            print(out)
        else:
            p = TextExtractor()
            p.feed(fetch(url))
            print(p.text())
    except URLError as e:
        sys.exit(f"fetch failed: {e}")


if __name__ == "__main__":
    main()
