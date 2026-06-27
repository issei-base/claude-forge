# Marp 記法リファレンス（lookup）

スライドを組むとき必要になった項目だけ引く。基本構造は `assets/template.md` を見れば足りるので、ここは「テンプレに無い記法が要るとき」の参照。

## frontmatter（ファイル先頭・必須）

```yaml
---
marp: true            # これが無いと marp が処理しない
theme: forge          # assets/theme.css の /* @theme forge */ と対応
paginate: true        # ページ番号を出す
size: 16:9            # 16:9（既定）/ 4:3 も可
header: '勉強会タイトル'  # 全スライド共通の見出し（任意）
footer: '2026 · 発表者名' # 全スライド共通のフッタ（任意）
math: katex           # 数式エンジン（既定 mathjax。katex は軽量・高速）
headingDivider: 2     # ## が来たら自動でスライドを割る（任意）
style: |              # この deck だけ CSS 上書き（theme.css を触らず色替え）
  :root { --accent: #c15f3c; --accent-deep: #7a3322; }
---
```

- **frontmatter はファイルの一番上**に置く。前に空行・コメント・本文があると無効化され、YAML が本文として表示される。
- 全スライド共通の指定は frontmatter（グローバルディレクティブ）。
- **色を変えるなら `style:` で `:root` 変数を上書き**するのが基本。theme.css 原本は触らない。
- `headingDivider: 2` を使うと `---` を手で打たず `##` 単位で章割りできる（素材→deck 変換が楽）。
- 出典: [Marpit Directives](https://github.com/marp-team/marpit/blob/main/docs/directives.md)

## スライド区切り

- `---`（前後に空行）で次のスライドへ。

## スポットディレクティブ（そのスライドだけに効かせる）

スライド内に HTML コメントで書く。`_` 始まりは**そのスライド単体**、無印は**それ以降全部**に効く。

```markdown
<!-- _class: lead -->        # このスライドだけ lead クラス
<!-- _paginate: skip -->     # 非表示かつ採番から除外（表紙に使う）
<!-- _paginate: hold -->     # 番号は出すが採番を進めない（章扉に使う）
<!-- _header: '' -->         # このスライドだけ共通ヘッダを消す（表紙など）
<!-- _footer: '' -->         # このスライドだけ共通フッタを消す
<!-- _backgroundColor: #000 --> # 背景色を直接指定
<!-- _color: white -->       # 文字色
```

ページ番号は 4 状態（出典: [Marpit Directives](https://github.com/marp-team/marpit/blob/main/docs/directives.md)）:
- `paginate: true` 表示・採番する（本文の既定）
- `paginate: false` 非表示だが**採番は進む**（表紙にこれを使うと本文が 2 始まりになる → **使わない**）
- `paginate: skip` 非表示**かつ採番から除外**（表紙はこれ）
- `paginate: hold` 表示するが**採番を進めない**（章扉はこれ）

forge テーマで使える class（`assets/theme.css` で定義）:
- `lead` — 表紙・タイトル（中央寄せ・グラデ背景）
- `section` — 章扉（濃紺背景・白文字）
- `tight` — 情報量が多いスライド（フォント小さめ）

## 画像

```markdown
![w:600](img.png)           # 幅 600px
![h:300](img.png)           # 高さ 300px
![w:600 h:300](img.png)     # 両方
```

### 背景画像

```markdown
![bg](img.png)               # スライド全面に背景
![bg fit](img.png)           # 収まるように
![bg cover](img.png)         # 覆うように（既定）
![bg left](img.png)          # 左半分に背景、右にテキスト
![bg right:40%](img.png)     # 右 40% に背景
![bg left:33%](a.png)        # 比率で分割
![bg vertical](a.png) ![bg](b.png)   # 複数 bg を縦並び（既定は横）
![bg blur:8px brightness:.8](img.png) # フィルタ（ぼかし・明るさ・sepia 等も可）
```

複数 `![bg]` を並べると分割配置される（既定は横、`vertical` で縦）。出典: [Marpit Image Syntax](https://github.com/marp-team/marpit/blob/main/docs/image-syntax.md)。
**ローカル画像（`./img.png` 等）を PDF/PPTX/PNG に埋めるにはレンダリング時 `--allow-local-files` が必須**（無いとサイレントに欠落）。

## 2 カラム（テンプレ同梱）

Marp に段組み記法は無い。HTML + scoped CSS で組む（`assets/template.md` の「2 カラムで対比」をコピー）:

```markdown
<div class="columns">
<div>左の内容</div>
<div>右の内容</div>
</div>

<style scoped>
.columns { display: grid; grid-template-columns: 1fr 1fr; gap: 2em; }
</style>
```

`<style scoped>` はそのスライドだけに効く。全スライド共通の見た目は `theme.css` に足す（その場限りなら scoped）。

## 自動フィット / 自動縮小（auto-scaling）

forge テーマは先頭に `/* @auto-scaling true */` を宣言済み。これにより Marp Core が:
- `# <!-- fit -->` を付けた見出しを枠幅いっぱいまで**自動拡大**
- **長いコードブロック・KaTeX 数式を横方向に自動縮小**（枠からの横溢れを防ぐ）

```markdown
# <!-- fit --> 大きく見せたい見出し
```

注意: **縮小は横方向のみ**。行数が多くて縦に溢れる場合は分割か `_class: tight` で対処する。出典: [Marp Core README](https://github.com/marp-team/marp-core/blob/main/README.md)。

## 数式

frontmatter で `math: katex`（軽量・高速）か既定の `math: mathjax` を選ぶ。

```markdown
インライン $E = mc^2$ 、ブロック:

$$
\int_0^\infty e^{-x}\,dx = 1
$$
```

## 対応していないもの

- **Mermaid は Marp 標準では非対応**（プラグインが要る）。deck に ` ```mermaid ` を書いても図にならない。図は画像 or 背景画像 or 2カラム/表で代替する。

## 発表者ノート

スライド内の HTML コメント（ディレクティブでない普通の文）はノート扱い。PPTX 書き出し時に発表者ノートへ入る。

```markdown
<!-- これは発表者ノート。スライドには出ない。 -->
```

## 出力コマンド（marp-cli）

theme.css は `--theme` で渡す。出力拡張子は `-o` の拡張子か明示フラグで決まる。

```bash
marp deck.md --theme theme.css --allow-local-files -o deck.html  # HTML（既定）
marp deck.md --theme theme.css --allow-local-files --pdf  -o deck.pdf
marp deck.md --theme theme.css --allow-local-files --pptx -o deck.pptx
marp deck.md --theme theme.css --allow-local-files --images png -o slide.png # 全ページ連番 PNG
marp deck.md --theme theme.css -w              # ウォッチ（保存で自動再生成）
marp deck.md --theme theme.css -s              # ローカルサーバでプレビュー
```

実務で効くフラグ（出典: [Marp CLI README](https://github.com/marp-team/marp-cli/blob/main/README.md)）:
- **`--allow-local-files`** — ローカル画像を埋め込むのに必須。公式は "NOT SECURE" 警告つきなので**信頼できる自分の deck のみ**に使う。
- `--images png` 全ページを連番 PNG（vision QA 用）／ `--image png` 表紙 1 枚だけ。
- `--pdf-notes` 発表者ノートを PDF 注釈に／ `--pdf-outlines` PDF にブックマーク（長い配布資料向け）。
- `--pptx-editable` 編集可能 PPTX（実験的・要 LibreOffice・再現性は通常 PPTX より低い）。通常は `--pptx` で十分（画像埋め込みで再現性高い）。
- `--theme-set <dir|css...>` 複数テーマをまとめて登録（`--theme` は単一）。

- **PDF / PPTX / PNG は Chrome/Chromium が必要**（marp が内部で起動してレンダリングする）。HTML は不要。
- PDF にメモを埋めたいなら `--pdf-notes`、発表者ノート付き PPTX は `--pptx-editable` も検討（要 LibreOffice）。
- 環境の Chrome を明示するなら `CHROME_PATH` 環境変数 or `--browser-path`。

## VS Code でプレビューしながら書く（任意）

拡張機能 **「Marp for VS Code」** を入れると、エディタ右側にライブプレビューが出る。カスタムテーマを使うには settings.json に:

```json
"markdown.marp.themes": [
  "/Users/issei/projects/claude-forge/.claude/skills/make-slides/assets/theme.css"
]
```

を足す（パスは theme.css の絶対パス）。これで VS Code 上でも forge テーマが効く。
