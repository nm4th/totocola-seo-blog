# セットアップ手順

このリポジトリをクローンしてから、初回の記事自動生成が走るまでの手順。

## 0. 前提

- GitHub リポジトリ: https://github.com/nm4th/totocola-seo-blog
- Shopify ストア管理者権限
- Anthropic Console のアカウント

## 1. Shopify Dev Dashboard でアプリを作成（人間タスク）

> 2026-01 から旧来の「ストア管理画面 → 設定 → アプリと販売チャネル → アプリ開発」
> ルートは廃止。`shpat_` 型の永続トークンは UI から取れなくなり、
> Client ID + Client Secret + client credentials grant で
> プログラム的に取得する設計に変わった。

1. Shopify Dev Dashboard を開く
2. 該当の組織（ととコーラ）配下でアプリを作成（既に `totocola-seo-bot` がある場合はそれでよい）
3. **構成 / Configuration** で Admin API access scopes に次を含める:
   - `read_content` / `write_content`
   - `read_online_store_pages` / `write_online_store_pages`
   - 必要に応じてバージョンを発行 → アクティブにする
4. **設定 / Settings → 資格情報** から控える:
   - **クライアント ID**（公開しても問題ない）
   - **シークレット (`shpss_...`)** ← 表示直後にコピー。漏洩したら必ず「ローテーション」で再発行
5. **対象ストアにアプリをインストール**（インストール数が 0 の状態だと
   client credentials grant が通らない）
   - 「アプリをインストール」ボタンから対象ストア（`totonoido`）にインストール

> 制約: アプリとストアが同じ Shopify 組織配下にあること。

## 2. 投稿先ブログを用意（人間タスク）

SEO 記事専用に新しいブログを切ることを推奨。

- Shopify ストア管理画面 → オンラインストア → ブログ → ブログを管理 → ブログを追加
- タイトル例: 「ととのうコラム」
- ハンドル: `column`

ブログ ID（GraphQL gid）を取得するには、まず client credentials grant で
24h トークンを取得してから API を叩く（`scripts/fetch_blog_id.sh` 相当の手順）:

```bash
# トークン取得（24h 有効）
TOKEN=$(curl -s -X POST \
  "https://${SHOPIFY_STORE_DOMAIN}/admin/oauth/access_token" \
  -H "Content-Type: application/json" \
  -d "{\"client_id\":\"${SHOPIFY_CLIENT_ID}\",\"client_secret\":\"${SHOPIFY_CLIENT_SECRET}\",\"grant_type\":\"client_credentials\"}" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# ブログ一覧取得
curl -X POST \
  "https://${SHOPIFY_STORE_DOMAIN}/admin/api/2026-01/graphql.json" \
  -H "X-Shopify-Access-Token: ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ blogs(first: 10) { edges { node { id title handle } } } }"}'
```

レスポンス内の `"id": "gid://shopify/Blog/xxxxxxxxx"` を控える。

## 3. Anthropic API キーを準備（人間タスク）

https://console.anthropic.com で発行（既存のものでも可）。

## 4. GitHub Secrets を登録（人間タスク）

リポジトリ → Settings → Secrets and variables → Actions

| Name | 値 |
|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` |
| `SHOPIFY_STORE_DOMAIN` | `totonoido.myshopify.com` |
| `SHOPIFY_CLIENT_ID` | Dev Dashboard → Settings → 資格情報 → クライアント ID |
| `SHOPIFY_CLIENT_SECRET` | Dev Dashboard → Settings → 資格情報 → シークレット (`shpss_...`) |
| `SHOPIFY_BLOG_ID` | `gid://shopify/Blog/xxxxxxxxx` |

`AUTO_PUBLISH` は workflow_dispatch の入力で渡すので Secret 不要。

## 5. 動作テスト

1. GitHub → Actions → 「Generate SEO Article」
2. 「Run workflow」
3. `auto_publish` は **`false`**（最初の数本は下書きで品質確認）
4. 実行ログを開いて以下を確認:
   - `pick_keyword.py` が id=1 を選んでいる
   - Claude Code Action が WebSearch を走らせている
   - `output/` 配下に `.md` と `.meta.json` が生成された
   - `check_compliance.py` が OK を返している
   - `publish_to_shopify.py` が article id を返している
   - `keywords.csv` の id=1 が `published` に更新され commit されている
5. Shopify 管理画面 → オンラインストア → ブログ → 下書き で記事を確認

## 6. 運用

- キーワード追加: `data/keywords.csv` に行を追加して push
- 失敗した実行: `keywords.csv` の `notes` に `[failed YYYY-MM-DD]` が記録され、
  status は `pending` のまま残る → 次回実行で再挑戦
- スケジュール実行: `.github/workflows/generate-article.yml` の
  `schedule:` ブロックのコメントアウトを外す
- トーンを直したいとき: `CLAUDE.md` のトーンサンプルを実例で書き換えて push
- コンプライアンス検査の調整: `scripts/check_compliance.py` の `NG_PATTERNS`
