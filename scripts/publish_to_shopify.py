#!/usr/bin/env python3
"""Publish a generated article to Shopify via Admin GraphQL articleCreate.

Auth: Dev Dashboard apps use the OAuth client credentials grant. We exchange
SHOPIFY_CLIENT_ID + SHOPIFY_CLIENT_SECRET for a 24h access token at
https://{shop}.myshopify.com/admin/oauth/access_token, then call the Admin API
with that token. Requires the app and store to live in the same Shopify org.

Required env vars:
    SHOPIFY_STORE_DOMAIN   e.g. totonoido.myshopify.com
    SHOPIFY_CLIENT_ID      Dev Dashboard → Settings → Credentials → Client ID
    SHOPIFY_CLIENT_SECRET  Dev Dashboard → Settings → Credentials → Secret (shpss_...)
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
import re
import sys
from pathlib import Path

import urllib.error
import urllib.request

import markdown

API_VERSION = "2026-01"

LIST_BLOGS = """
{
  blogs(first: 50) {
    edges {
      node {
        id
        title
        handle
      }
    }
  }
}
""".strip()

ARTICLE_CREATE = """
mutation ArticleCreate($article: ArticleCreateInput!) {
  articleCreate(article: $article) {
    article {
      id
      title
      handle
      isPublished
      publishedAt
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


def normalize_blog_id(raw: str) -> str:
    """Accept either a full gid or a bare numeric ID and return a gid."""
    cleaned = raw.strip().strip('"').strip("'")
    if cleaned.startswith("gid://shopify/Blog/"):
        return cleaned
    if cleaned.isdigit():
        return f"gid://shopify/Blog/{cleaned}"
    # Anything else is malformed — let the caller decide whether to error.
    return cleaned


def verify_blog_id(domain: str, token: str, blog_id: str) -> None:
    """Ensure SHOPIFY_BLOG_ID exists; on miss, list all blogs and exit."""
    result = post_graphql(domain, token, LIST_BLOGS, {})
    edges = (result.get("data", {}).get("blogs") or {}).get("edges") or []
    blogs = [e["node"] for e in edges]
    if any(b["id"] == blog_id for b in blogs):
        match = next(b for b in blogs if b["id"] == blog_id)
        print(f"Blog OK: {blog_id}  (title={match['title']!r}, handle={match['handle']!r})")
        return

    print(
        f"ERROR: SHOPIFY_BLOG_ID does not match any blog on this store.\n"
        f"  configured: {blog_id!r}\n"
        f"  available blogs ({len(blogs)}):",
        file=sys.stderr,
    )
    for b in blogs:
        print(
            f"    - id={b['id']}  handle={b['handle']!r}  title={b['title']!r}",
            file=sys.stderr,
        )
    print(
        "\nUpdate the SHOPIFY_BLOG_ID GitHub Secret to one of the gid values above.",
        file=sys.stderr,
    )
    sys.exit(6)


PRODUCT_URL_PREFIX = "https://totocola.com/products/"

ARTICLE_CONTAINER_STYLE = (
    "max-width:680px;margin:0 auto;line-height:1.95;font-size:16px;"
    "color:#1a1a1a;letter-spacing:0.02em;"
)

CTA_WRAPPER_STYLE = (
    "margin:3em auto;padding:2em 1.5em;background:#f6f3ee;"
    "border-radius:8px;text-align:center;"
)

CTA_BUTTON_STYLE = (
    "display:inline-block;padding:14px 36px;background:#1a1a1a;color:#fff;"
    "text-decoration:none;border-radius:4px;font-size:0.95em;"
    "letter-spacing:0.08em;"
)


def _style_final_product_cta(html: str) -> str:
    """Replace the last <p> containing a product link with a styled CTA box."""
    pattern = re.compile(
        r"<p>(?:(?!</p>).)*?"
        r'<a\s+href="(' + re.escape(PRODUCT_URL_PREFIX) + r'[^"]*)"[^>]*>'
        r"([^<]+)"
        r"</a>"
        r"(?:(?!</p>).)*?</p>",
        re.DOTALL,
    )
    matches = list(pattern.finditer(html))
    if not matches:
        return html
    last = matches[-1]
    url, text = last.group(1), last.group(2)
    cta = (
        f'<div style="{CTA_WRAPPER_STYLE}">'
        f'<a href="{url}" style="{CTA_BUTTON_STYLE}">{text} →</a>'
        f"</div>"
    )
    return html[: last.start()] + cta + html[last.end() :]


def md_to_html(md_text: str) -> str:
    """Convert article markdown to HTML; drop a leading H1.

    The article title is set on the Article record itself (via the title
    field on ArticleCreateInput), so the first-line H1 inside the markdown
    body is duplicated content and is removed before conversion. The final
    paragraph that points at the product page is rewritten as a styled CTA
    box; the inline mid-article product mention stays as a regular link.
    The whole body is wrapped in a width-constrained container with a
    line-height tuned for long-form Japanese reading.
    """
    text = md_text.lstrip()
    if text.startswith("# "):
        _, _, rest = text.partition("\n")
        text = rest.lstrip("\n")
    raw_html = markdown.markdown(
        text,
        extensions=["extra", "sane_lists", "smarty"],
        output_format="html5",
    )
    styled = _style_final_product_cta(raw_html)
    return (
        f'<div class="totocola-article" style="{ARTICLE_CONTAINER_STYLE}">\n'
        f"{styled}\n"
        "</div>"
    )


def fetch_access_token(domain: str, client_id: str, client_secret: str) -> str:
    """Exchange client_id + client_secret for a 24h Admin API access token."""
    url = f"https://{domain}/admin/oauth/access_token"
    body = json.dumps(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")
        print(f"ERROR: HTTP {e.code} from token endpoint\n{msg}", file=sys.stderr)
        sys.exit(3)
    except urllib.error.URLError as e:
        print(f"ERROR: network error talking to token endpoint: {e}", file=sys.stderr)
        sys.exit(3)

    token = payload.get("access_token")
    if not token:
        print(f"ERROR: token endpoint returned no access_token: {payload}", file=sys.stderr)
        sys.exit(3)
    return token


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
    client_id = env("SHOPIFY_CLIENT_ID")
    client_secret = env("SHOPIFY_CLIENT_SECRET")
    blog_id = normalize_blog_id(env("SHOPIFY_BLOG_ID"))
    auto_publish = os.environ.get("AUTO_PUBLISH", "false").strip().lower() == "true"

    print(f"Exchanging client credentials for access token at {domain}...")
    token = fetch_access_token(domain, client_id, client_secret)

    verify_blog_id(domain, token, blog_id)

    body_html = md_to_html(body_md)

    article_input: dict = {
        "blogId": blog_id,
        "title": meta["title"],
        "handle": meta.get("handle"),
        "body": body_html,
        "summary": meta.get("summary", ""),
        "author": {"name": meta.get("author", "ととコーラ編集部")},
        "tags": meta.get("tags", []),
        "isPublished": auto_publish,
    }
    # Shopify stores SEO title/description as metafields under the global
    # namespace; ArticleCreateInput has no `seo` field.
    metafields: list[dict] = []
    if meta.get("seo_title"):
        metafields.append(
            {
                "namespace": "global",
                "key": "title_tag",
                "value": meta["seo_title"],
                "type": "single_line_text_field",
            }
        )
    if meta.get("seo_description"):
        metafields.append(
            {
                "namespace": "global",
                "key": "description_tag",
                "value": meta["seo_description"],
                "type": "multi_line_text_field",
            }
        )
    if metafields:
        article_input["metafields"] = metafields

    article_input = {k: v for k, v in article_input.items() if v not in (None, "")}

    base_handle = meta.get("handle") or ""
    max_attempts = 5
    result: dict = {}
    chosen_handle = base_handle
    for attempt in range(max_attempts):
        chosen_handle = base_handle if attempt == 0 else f"{base_handle}-{attempt + 1}"
        article_input["handle"] = chosen_handle
        print(
            f"Posting to Shopify: title={meta['title']!r} "
            f"handle={chosen_handle!r} auto_publish={auto_publish}"
        )
        result = post_graphql(domain, token, ARTICLE_CREATE, {"article": article_input})

        if result.get("errors"):
            break

        payload = result.get("data", {}).get("articleCreate", {})
        user_errors = payload.get("userErrors") or []
        handle_conflict = any(
            "handle" in (e.get("field") or [])
            and "already been taken" in (e.get("message") or "").lower()
            for e in user_errors
        )
        if not handle_conflict:
            break
        print(
            f"  handle {chosen_handle!r} already taken, retrying with next suffix...",
            file=sys.stderr,
        )

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

    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as fh:
            fh.write(f"article_id={article.get('id', '')}\n")
            fh.write(f"article_url=\n")
            fh.write(f"is_published={'true' if article.get('isPublished') else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
