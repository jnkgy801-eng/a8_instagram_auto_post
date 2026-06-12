# 🛍️📸 A8.netアフィリエイト広告 Instagram 自動投稿

A8.netの提携プログラムを、GitHub Actionsで定期的にInstagramへ自動投稿します。

```
your-repo/
├── a8_post.py           # A8.netアフィリエイト広告投稿スクリプト
├── a8_products.json     # 投稿する商品リスト（要編集）
├── ig_utils.py          # Instagram投稿共通ユーティリティ
├── README.md
└── .github/
    └── workflows/
        └── a8_post.yml
```

---

## 🚀 セットアップ手順

### 1. GitHub Secrets に認証情報を登録

GitHubリポジトリの **Settings → Secrets and variables → Actions → New repository secret** で以下を登録：

| Secret名 | 内容 |
|----------|------|
| `META_ACCESS_TOKEN` | Instagramのアクセストークン |
| `INSTAGRAM_ACCOUNT_ID` | InstagramビジネスアカウントID |
| `IMGBB_API_KEY` | imgbb APIキー（**必須**。Pillowで生成した画像のアップロードに使用） |

> ⚠️ `a8_post.py` はPillowで生成した画像（または取得した商品画像）を必ずimgbbに
> アップロードして公開URLを作成するため、`IMGBB_API_KEY` が未設定の場合は投稿に失敗します。

### 2. `a8_products.json` を自分の商品情報に書き換える

サンプル値のままでは投稿できません。A8.netの「リンク作成」ページなどから、
紹介したいプログラムの情報を取得して書き換えてください。

```json
[
  {
    "id": "任意の管理用ID",
    "title": "投稿に表示する商品名・キャッチコピー",
    "copy": "紹介文（数行のフリーテキスト）",
    "image_url": "A8.netの素材ページにある画像URL（任意・空文字でもOK）",
    "affiliate_url": "A8.netの「リンク作成」で発行されたアフィリエイトURL（a8mat=...）",
    "hashtags": "#PR #広告 #任意のハッシュタグ"
  }
]
```

- `image_url` を指定すると、その画像をダウンロードして再アップロードして使用します。
- `image_url` を空文字 `""` にすると、`title` と `copy` を使ったテキストベースの
  広告カード画像（1080×1080・「PR／広告」バッジ付き）をPillowで自動生成します。
- キャプションには **必ず「#PR #広告」が表示されます**（2023年10月施行のステマ規制対応）。
  `hashtags` に既に `#PR` や `広告` を含めている場合は重複表示しません。

### 3. GitHub Actions を有効化

リポジトリの **Actions タブ** を開き、「I understand my workflows, go ahead and enable them」をクリック。

### 4. 動作確認（手動テスト）

Actions タブ → **A8.net アフィリエイト広告 自動投稿** → **Run workflow**

`post_mode` を以下から選択できます：

- `sequential`（デフォルト）: 登録順に1件ずつ投稿し、最後まで行ったら最初に戻る
- `random`: 毎回ランダムに1件投稿

---

## ⏰ 実行スケジュール

`.github/workflows/a8_post.yml` のデフォルトは **毎日 JST 15:00（UTC 06:00）に1回**です。
変更したい場合は `cron` の値を編集してください。

---

## 📂 投稿順の管理（`a8_state.json`）

- `sequential` モードでは、最後に投稿した商品のインデックスを `a8_state.json` に保存し、
  ワークフローが自動でリポジトリにコミットします。次回実行時はその次の商品が選ばれます。
- `random` モードでは毎回ランダムに1件選びます（状態は保存されません）。
- 初回実行時は `a8_state.json` がまだ無くても自動作成されます。

---

## ⚠️ ご利用にあたっての注意

- **各アフィリエイトプログラムの提携規約**で、SNS（Instagram等）への広告掲載が
  許可されているか必ず事前にご確認ください（プログラムによって可否が異なります）。
- 商品画像はA8.net発行の素材を利用し、無関係な画像の転用は避けてください。
- Instagramのキャプション内URLはリンクとして機能しないため、実際の集客には
  プロフィールのリンク（リンクツリー等）と組み合わせることを推奨します。

---

## ❗ トラブルシューティング

| エラー | 原因 | 対処法 |
|--------|------|--------|
| `190` | トークン期限切れ | Meta DevelopersでSecretを更新 |
| `9004` | 画像URL非対応 | `IMGBB_API_KEY` Secretを設定 |
| `24` | 投稿上限超過（25投稿/日） | スケジュールを減らす |
| `❌ IMGBB_API_KEY が設定されていません` | `a8_post.py` 実行時に `IMGBB_API_KEY` Secretが未設定 | Secretを追加 |
| `❌ 商品リストファイルが見つかりません` | `a8_products.json` が無い／パスが違う | リポジトリに配置されているか確認 |
