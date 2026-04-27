#!/usr/bin/env python3
"""Publish a generated article to Shopify via Admin GraphQL articleCreate.

Required env vars:
    SHOPIFY_STORE_DOMAIN   e.g. totocola.myshopify.com
    SHOPIFY_ACCESS_TOKEN   shpat_...
    SHOPIFY_BLOG_ID        gid://shopify/Blog/xxxxxxxxx
    AUTO_PUBLISH           "true" to publish immediately, otherwise saved as draft

Usage:
    python scripts/publish_to_shopify.py output/<slug>.md

Reads:
    output/<slug>.md          — Markdown body
    output/<slug>.meta.json   — title / handle / summary / tags / author / seo

Writes:
    output/<slug>.publish.json — full Shopify response for debugging

Exits non-zero on any HTTP / GraphQL / userErrors failure.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import urllib.error
import urllib.request

API_VERSION = "2026-01"

ARTICLE_CREATE = """
mutation ArticleCreate($article: ArticleCreateInput!) {
  articleCreate(article: $article) {
    article {
      id
      title
      handle
      isPublished
      publishedAt
      onlineStoreUrl
    }
    userErrors {
      field
      message
    }
  }
}
""".strip()


def env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        print(f"ERROR: env var {name} is not set", file=sys.stderr)
        sys.exit(2)
    return v


def post_graphql(domain: str, token: str, query: str, variables: dict) -> dict:
    url = f"https://{domain}/admin/api/{API_VERSION}/graphql.json"
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": token,
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")
        print(f"ERROR: HTTP {e.code} from Shopify\n{msg}", file=sys.stderr)
        sys.exit(3)
    except urllib.error.URLError as e:
        print(f"ERROR: network error: {e}", file=sys.stderr)
        sys.exit(3)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: publish_to_shopify.py <article.md>", file=sys.stderr)
        return 64

    md_path = Path(argv[1])
    meta_path = md_path.with_suffix(".meta.json")
    if not md_path.exists():
        print(f"ERROR: {md_path} not found", file=sys.stderr)
        return 1
    if not meta_path.exists():
        print(f"ERROR: {meta_path} not found", file=sys.stderr)
        return 1

    body_md = md_path.read_text(encoding="utf-8")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    domain = env("SHOPIFY_STORE_DOMAIN")
    token = env("SHOPIFY_ACCESS_TOKEN")
    blog_id = env("SHOPIFY_BLOG_ID")
    auto_publish = os.environ.get("AUTO_PUBLISH", "false").strip().lower() == "true"

    article_input: dict = {
        "blogId": blog_id,
        "title": meta["title"],
        "handle": meta.get("handle"),
        "body": body_md,
        "summary": meta.get("summary", ""),
        "author": {"name": meta.get("author", "ととコーラ編集部")},
        "tags": meta.get("tags", []),
        "isPublished": auto_publish,
    }
    seo: dict = {}
    if meta.get("seo_title"):
        seo["title"] = meta["seo_title"]
    if meta.get("seo_description"):
        seo["description"] = meta["seo_description"]
    if seo:
        article_input["seo"] = seo

    article_input = {k: v for k, v in article_input.items() if v not in (None, "")}

    print(
        f"Posting to Shopify: title={meta['title']!r} "
        f"handle={meta.get('handle')!r} auto_publish={auto_publish}"
    )
    result = post_graphql(domain, token, ARTICLE_CREATE, {"article": article_input})

    out_path = md_path.with_suffix(".publish.json")
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    if result.get("errors"):
        print("ERROR: GraphQL errors:", file=sys.stderr)
        print(json.dumps(result["errors"], ensure_ascii=False, indent=2), file=sys.stderr)
        return 4

    payload = result.get("data", {}).get("articleCreate", {})
    user_errors = payload.get("userErrors") or []
    if user_errors:
        print("ERROR: articleCreate userErrors:", file=sys.stderr)
        for e in user_errors:
            print(f"  - field={e.get('field')} message={e.get('message')}", file=sys.stderr)
        return 5

    article = payload.get("article") or {}
    print(f"OK: created article id={article.get('id')} published={article.get('isPublished')}")
    if article.get("onlineStoreUrl"):
        print(f"  url: {article['onlineStoreUrl']}")

    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as fh:
            fh.write(f"article_id={article.get('id', '')}\n")
            fh.write(f"article_url={article.get('onlineStoreUrl', '')}\n")
            fh.write(f"is_published={'true' if article.get('isPublished') else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
