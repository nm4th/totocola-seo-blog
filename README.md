# totocola-seo-blog

ととコーラ ブランドの Shopify ブログ向け SEO 記事を、Claude Code GitHub
Actions が自動生成し、Shopify Admin GraphQL API で投稿するパイプライン。

- ブランド: [ととコーラ](https://totocola.com/)
- コンセプト: 夜にととのう、大人のクラフトコーラ
- 投稿先: Shopify ブログ（ハンドル: `column` 推奨）
- API バージョン: `2026-01`

## 仕組み

```
┌─────────────────────────────────────────────────────┐
│ GitHub Actions (workflow_dispatch / schedule)       │
│   ┌───────────────────────────────────────────────┐ │
│   │ 1. pick_keyword.py                            │ │
│   │      data/keywords.csv から status=pending    │ │
│   │      の最古の1件を取得                        │ │
│   │ 2. Claude Code Action で記事生成              │ │
│   │      prompts/article_generation.md を使用     │ │
│   │      output/ に .md と .meta.json を出力      │ │
│   │ 3. check_compliance.py                        │ │
│   │      薬機法・景表法 NG 表現を検査             │ │
│   │ 4. publish_to_shopify.py                      │ │
│   │      articleCreate ミューテーションで投稿     │ │
│   │      auto_publish=false なら下書きで保存      │ │
│   │ 5. update_keyword_status.py                   │ │
│   │      keywords.csv を published / failed に更新│ │
│   │ 6. git commit & push                          │ │
│   └───────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

1 回のワークフロー実行で記事は **1 本だけ**。次の対策キーワードは
`data/keywords.csv` を編集して push するだけで増やせる。

## セットアップ

[docs/setup.md](docs/setup.md) を参照。

## 必要な GitHub Secrets

| Name | 内容 |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API キー |
| `SHOPIFY_STORE_DOMAIN` | 例: `totonoido.myshopify.com` |
| `SHOPIFY_CLIENT_ID` | Dev Dashboard → Settings → 資格情報 → クライアント ID |
| `SHOPIFY_CLIENT_SECRET` | Dev Dashboard → Settings → 資格情報 → シークレット (`shpss_...`) |
| `SHOPIFY_BLOG_ID` | 投稿先ブログの GraphQL gid (`gid://shopify/Blog/xxx`) |

`publish_to_shopify.py` が実行時に
`POST /admin/oauth/access_token` (`grant_type=client_credentials`) で
24 時間有効な Admin API access token を取得し、それで `articleCreate` を叩く。
アプリとストアが同じ Shopify 組織配下にある必要あり。

`AUTO_PUBLISH` は workflow_dispatch の input で指定（Secret 不要）。

> Note: 旧来の Custom App から発行される `shpat_` 型の永続トークンは
> 2026 年 1 月で廃止され、新規アプリは Dev Dashboard 経由のみ。
> したがって本リポジトリは client credentials grant ベースで実装。

## 運用ルール

1. 1 回の実行で記事は 1 本だけ生成
2. 最初の 3〜5 本は `auto_publish=false`（下書き）で品質確認
3. キーワード追加は `data/keywords.csv` に行を足して push
4. 既に `published` のキーワードは再生成しない
5. 失敗したら `status` は `pending` のまま残し、再挑戦できるようにする
