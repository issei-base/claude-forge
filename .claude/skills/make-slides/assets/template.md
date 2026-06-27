---
marp: true
theme: forge
paginate: true
size: 16:9
# header: '勉強会タイトル'      # 全スライド共通の見出し（不要なら行ごと消す）
# footer: '2026 · 発表者名'     # 全スライド共通のフッタ
# style: |                      # この deck だけ色を変える（theme.css は触らない）
#   :root { --accent: #c15f3c; --accent-deep: #7a3322; }
---

<!--
  Marp スライドの雛形。この .md をコピーして中身を差し替える。
  frontmatter は必ずファイル先頭（上の --- ブロック）に置く。前に何か書くと無効化される。
  レンダリングは marp-cli に theme.css を渡す（SKILL.md のワークフロー参照）:
    marp deck.md --theme <skill>/assets/theme.css --allow-local-files -o deck.pdf
  frontmatter の theme: forge は theme.css 先頭の /* @theme forge */ と対応。
-->

<!-- _class: lead -->
<!-- _paginate: skip -->
<!-- _header: '' -->
<!-- _footer: '' -->

# プレゼンのタイトル

## サブタイトル / 一文サマリ

発表者・日付

---

## アジェンダ

1. 背景・課題
2. 提案
3. 詳細
4. まとめ

---

<!-- _class: section -->
<!-- _paginate: hold -->

# 1. 背景・課題

---

## 課題の整理

- 箇条書きは **1 枚 5〜6 行まで**。詰め込まない
- 1 スライド 1 メッセージ
- 詳細は口頭・補足資料へ委ねる

> 引用・補足はこの形で。

---

## 2 カラムで対比

<div class="columns">

<div>

### Before
- 手作業
- 属人的
- 遅い

</div>
<div>

### After
- 自動化
- 標準化
- 速い

</div>

</div>

<style scoped>
.columns { display: grid; grid-template-columns: 1fr 1fr; gap: 2em; }
</style>

---

## コード例

```python
def greet(name: str) -> str:
    return f"Hello, {name}!"
```

行数が多いコードは `<!-- _class: tight -->` でフォントを落とす。

---

## 図を貼る

<!-- 画像は ![w:600](path) や背景 ![bg right](path) で配置 -->
<!-- 詳しい記法は references/marp-syntax.md を参照 -->

![w:560](https://example.com/diagram.png)

---

<!-- _class: section -->
<!-- _paginate: hold -->

# まとめ

---

## まとめ

- ポイント 1
- ポイント 2
- ポイント 3

**次のアクション**: ...
