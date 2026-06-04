# tests — skill harness regression + trigger eval

claude-forge は「skill = 小さなハーネス」の集合体。ハーネスエンジニアリングの肝は
**生成と評価の分離** と **フィードバックループ** で、ここはその「評価」側を 2 層で持つ。

| 層 | ファイル | 何を保証するか | 性質 |
|---|---|---|---|
| **構造 lint** | `lint_skills.py` | SKILL.md が壊れていない（frontmatter・`name`↔dir 一致・description 必須・重複なし） | 決定的・ネットワーク無し・依存なし。常時回す回帰ガード |
| **発火 eval** | `eval_triggers.py` + `triggers.json` | description が *意図どおり発火* する（代表クエリ→期待 skill にルーティング） | モデル判定・非決定的・トークン消費。チューニング時に回す |

`_skills.py` は両方が使う共通ローダ（`>-` block scalar 込みで frontmatter を依存なしパース）。

## 使い方

```sh
# 常時: 構造の回帰チェック（CI / pre-commit 向き）
python3 tests/lint_skills.py            # ERROR があれば exit 1
python3 tests/lint_skills.py --strict   # WARN も失敗扱い

# 随時: 発火品質チェック（description を直したら回す）
python3 tests/eval_triggers.py --dry-run   # プロンプトだけ確認（モデル呼ばない）
python3 tests/eval_triggers.py             # `claude -p` で実評価（claude CLI 必須）
python3 tests/eval_triggers.py --verbose   # 全ケース表示
```

## 切り分け — lint と eval は別物

- **lint は「発火するか」を証明しない**。構造の健全性だけ。SKILL.md を雑に編集して
  `name` と dir がズレた / description を消した、を即検出する用。
- **eval は本物のルーターそのものではない**。description をモデルに渡して
  「どれが発火すべきか」を一発分類させる *近似*。非決定的でトークンも食うので、
  毎コミットではなく description チューニング時に回す。

## fixtures を育てる（P3 と噛み合わせる）

`triggers.json` の `cases` は `{query, expect}`。`expect` は skill の dir 名か `"NONE"`。
運用で **誤発火 / 不発** を見つけたら、その実クエリを fixture に足して回帰させる。
「実際にどの skill が発火しているか」は usage dashboard（`tools/claude-usage-dashboard`、
SessionEnd hook が `Skill` tool 発火を skill 名つきで集計）から拾える — そこで見えた
ズレを eval の種にすると、テレメトリ → eval → description 修正のループが閉じる。
