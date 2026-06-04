---
name: lesson-homework
description: Google スプレッドシートで管理しているレッスン記録の「次回までの宿題」（行 5）を、過去の指導履歴と次回レッスン予定を読み解いて自動で考え、書き込む。ユーザー(インストラクター)が「次回の宿題考えて」「ハンズオン課題提案して」「<spreadsheet URL> の宿題を考えて」「lesson-homework」など、受講生のレッスン記録シートに対する次回ハンズオン課題の生成・記入を求めたときに発動する。読み取りは認証不要 (CSV export 経由) だが、書き込みは `gws` CLI の OAuth 認証が必要。
---

# lesson-homework

レッスン記録スプレッドシートの **行 5「次回までの宿題」** に次回ハンズオン課題のドラフトを書き込む skill。インストラクターが毎回手動で考えていた作業を自動化する。

## 前提知識: スプレッドシートの構造

```
       | A (ラベル)         | B (第1回) | C (第2回) | ... | BI (第60回)
-------+-------------------+----------+----------+-----+-----------
行 3   | インストラクター記入欄 | 1回目     | 2回目     | ... | 60回目
行 4   | レッスンで指導した内容  | <内容>   | <内容>   | ... |
行 5   | 次回までの宿題       | <宿題>   | <宿題>   | ... |   ← この skill が書く
行 6   | 次回レッスンの内容    | <予定>   | <予定>   | ... |
行 7-  | 受講生記入欄         | ...      | ...      |     |
```

- ターゲット列 = **「行 5（次回までの宿題）が空」の最初の列**。指導内容の有無は判定に使わない（実運用では「レッスンが始まる前に事前準備として宿題を書く」パターンがあり、その時点で指導内容セルは空のまま）。
- 既存セルを上書きしないよう、「最初に空になる列」のみを使う。
- 行 6「次回レッスンの内容」がインストラクター記入済みなら、それを最優先のヒントとして使う。

## Preflight

1. ユーザーから **Spreadsheet URL** を取得する (引数 or プロンプト)。URL 例: `https://docs.google.com/spreadsheets/d/<ID>/edit?gid=<GID>`
   - URL を **claude-forge repo にも CLAUDE.md にも保存しない**。会話内/セッション内でのみ保持。受講生の個人情報を含むため。
2. URL から `spreadsheetId` (パスの `/d/<ID>/`) と `gid` (`gid=<数値>`) を抽出。
3. `which gws` を確認。未インストールなら `npm install -g @googleworkspace/cli` を案内して STOP。
4. 書き込み前に `gws auth status` で `auth_method != "none"` を確認。未認証なら `gws auth setup --login` を案内して STOP (gcloud 必要)。読み取りだけなら認証不要なので、まず読み取り進めてもOK。

## ワークフロー

### 1. 読み取り (認証不要)

CSV export URL を curl して履歴を取得:

```sh
curl -sL "https://docs.google.com/spreadsheets/d/${SPREADSHEET_ID}/export?format=csv&gid=${GID}" -o /tmp/lesson-sheet.csv
```

Python の csv モジュールで正しくパース (セル内改行が多いので awk/grep では誤動作):

```python
import csv
with open('/tmp/lesson-sheet.csv', encoding='utf-8') as f:
    rows = list(csv.reader(f))
# rows[3] = レッスンで指導した内容
# rows[4] = 次回までの宿題
# rows[5] = 次回レッスンの内容
```

### 2. ターゲット列の特定

```python
# 列 1 (= 第1回) から見て、rows[4][n] (宿題) が空の最初の n
target_col = next(
    (n for n in range(1, len(rows[4])) if not rows[4][n].strip()),
    None
)
```

- `target_col` が `None` (= 全 60 回分すべて宿題が入力済) なら、「全レッスン分の宿題が既に入力されています」と伝えて停止。
- 見つかった場合、その直前列 (`target_col - 1`) が「最後に宿題を入力した回」になる。これが履歴分析の起点。

### 3. 履歴分析

直近 3-5 回分の `[指導内容 / 宿題 / 次回レッスン]` を読み、以下を把握:
- カリキュラム上の現在位置 (例: AWS 入門の中盤、VPC〜EC2 を済ませた直後)
- ハンズオンと座学(記事読み)のリズム (毎回ハンズオン? 隔回?)
- 過去宿題の **書式** (例: `🔳ハンズオン課題` または `ハンズオン課題：<タイトル>` → `【詳細な要件】` → `【具体的な手順と学習ポイント】` → `参考リンク`)
- ターゲット列の **直前列の宿題** (= rows[4][target_col-1]) = 直近の宿題、被らないように
- ターゲット列の **直前列の次回レッスン予定** (= rows[5][target_col-1]) = **次のレッスンで扱われる予定の内容**、宿題はその準備として整合させる
- 「事前準備モード」のときは指導内容も予定もまだ未入力なので、より前の回 (target_col-1 がさらに空のとき) から推測する

### 4. ハンズオン課題のドラフト生成

過去フォーマットを **厳格に踏襲** して生成。要素:

```
🔳ハンズオン課題：<タイトル>

【詳細な要件】
<2-4 文で要件を簡潔に>

【具体的な手順と学習ポイント】
1. <ステップ>
2. <ステップ>
3. <ステップ>
...

🔳参考リンク:
<実在する公式 docs / Qiita / Zenn の URL>
```

生成時のルール:
- **次回レッスン予定 (行 6) と整合させる**。例: 行 6 に「ALB のレビュー会」とあるなら、宿題は ALB 構築ハンズオン。
- 直近の指導内容を踏まえた **自然な次ステップ** にする。AWS の典型カリキュラム順 (IAM→VPC→EC2→ALB/ASG→RDS→S3/CloudFront→IAM ロール深掘り→Lambda/API GW→ECS→CI/CD) を意識。
- 参考リンクは **実在する URL のみ**。記憶が不確かな場合は省略し、AWS 公式 docs (`https://docs.aws.amazon.com/ja_jp/...`) を推奨。捏造したリンクを書かない。
- 受講生プロフィールを反映 (このシートの場合: ITパスポート / 基本情報技術者 取得済 → 基礎用語は説明不要、すぐ実践レベルで書いてよい)。

### 5. ユーザー確認 (必須)

書き込み前に **必ず以下を見せて承認を取る**:
- ターゲット列 (例: `第 7 回 = 列 H`)
- 書き込み先の A1 notation (例: `'シート1'!H5`) ※sheet 名は実際の名前を `gws sheets spreadsheets get` で確認
- 生成した宿題のドラフト全文
- 「これで書き込んで OK? 編集する? キャンセル?」と聞く

承認を待たずに自動書き込みは **絶対にしない**。

### 6. 書き込み (認証必須)

シート名を解決 (gid → sheet title):
```sh
gws sheets spreadsheets get --params '{"spreadsheetId":"<ID>","fields":"sheets(properties(sheetId,title))"}'
```

書き込み:
```sh
gws sheets spreadsheets values update \
  --params '{"spreadsheetId":"<ID>","range":"<シート名>!<列文字>5","valueInputOption":"USER_ENTERED"}' \
  --json '{"values":[["<宿題本文 (改行は \\n エスケープ)>"]]}'
```

- `valueInputOption: USER_ENTERED` でリンクが自動でハイパーリンク化される。
- 列文字変換は手計算: 第 N 回 → 列 N+1 文字 (1=B, 2=C, ..., 25=Z, 26=AA, ...)。`python3 -c "n=int(input()); s=''; n+=1
while n>0:
  n,r = divmod(n-1, 26)
  s = chr(65+r)+s
print(s)"` で計算可。

### 7. 確認 + 報告

書き込み後、再度 CSV export して書き込んだセルが反映されているか確認 (Google Sheets API の eventual consistency 対策で 2-3 秒待ってから)。

報告:
- 書き込んだ列 (例: 「第 7 回 = 列 H」)
- 書き込んだ URL (`https://docs.google.com/spreadsheets/d/<ID>/edit?gid=<GID>&range=H5`)
- 「内容を編集したい場合はシートを開いて直接編集してください」と案内

## してはいけないこと

- **ユーザー承認なしの書き込みは絶対にしない**。
- 既存セル (rows[4][n] が非空) を上書きしない。ターゲット列の判定で防ぐが、最終確認時にも再チェック。
- 参考リンクを捏造しない。確信が持てなければ省略。
- Spreadsheet URL や受講生個人情報を claude-forge repo / 永続 memory に保存しない。
- レッスンが現在 60 回目で終わっている (rows[3] が全 60 列埋まってる) 場合、61 回目を勝手に作らない。ユーザーに状況を伝えて停止。

## 関連

- 認証 (`gws` の OAuth) セットアップは上の **Preflight 4** を参照。`gws auth status` で確認し、未認証なら `gws auth setup --login` でブラウザ認証する（初回のみ）。
- 書き込みには **sheets の read/write scope** を含めて認証しておく必要がある（読み取りのみなら CSV export で認証不要）。
