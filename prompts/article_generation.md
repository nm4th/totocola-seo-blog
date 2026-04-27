# 記事生成プロンプト

このリポジトリで Claude Code が GitHub Actions 経由で 1 本の SEO 記事を
書き上げるときに従う手順。`CLAUDE.md` のブランドルールも併せて読み込むこと。

## 入力（環境変数として渡される）

- `KEYWORD` — 主要対策キーワード（例: 「クラフトコーラ 自宅」）
- `SEARCH_INTENT` — how-to / comparison / informational / lifestyle / problem-solving / seasonal / gift
- `PRIORITY` — high / medium / low
- `NOTES` — 執筆時の留意点（自由記述、空のこともある）

## 手順

1. **競合調査（WebSearch）**
   - `KEYWORD` で検索し、上位 3〜5 件の見出し構成を確認
   - 共通サブトピックを把握（読者が期待する内容）
   - どこにも書かれていないが読者が知りたそうな視点を 1〜2 個メモ
2. **構成案の作成**
   - H1 タイトル（28〜34 字）
   - リード（150〜250 字、情景描写から入る）
   - H2 を 4〜6 個。下に必要なら H3 を 0〜2 個ずつ
   - まとめ（H2）
3. **執筆**
   - `CLAUDE.md` のトーン・禁止事項に厳格に従う
   - 本文 2,500〜4,000 字
   - 商品ページへの内部リンクを本文中盤と末尾に 1 本ずつ
   - 商品ページ URL: `https://totocola.com/products/ととコーラ200ml`
   - 検索意図ごとの寄せ方:
     - how-to → 手順 + 体験文脈
     - comparison → 直接比較せず「自宅の夜時間を楽しむ視点」に変換
     - informational → 出典・主観を明示し断定を避ける
     - lifestyle → 情景描写多めで OK
     - seasonal / gift → シーン提案中心
4. **メタ情報の作成**
   - `handle` は半角英数 + ハイフン、20 字以内目安
   - `summary` (110〜140 字) は本文を読まなくても価値が伝わる文面
   - `tags` は 3〜5 個。例: ["クラフトコーラ", "夜時間", "ノンアルコール"]
   - `seo_title` 32 字以内、`seo_description` 160 字以内
5. **出力**

   `output/` ディレクトリに以下 2 ファイルを書き出す:

   - `output/<handle>.md` — Markdown 本文（H1 から開始）
   - `output/<handle>.meta.json` — メタ情報（`CLAUDE.md` の §6 のスキーマに従う）

   `output/` が存在しなければ作成する。

6. **薬機法・景表法セルフチェック**
   - 書き終えたら本文を読み返し、`scripts/check_compliance.py` の NG_PATTERNS
     に該当しそうな表現がないか確認し、置き換える。
   - 効能を断定したくなったら「〜と言われています」「〜と感じる人もいます」
     「〜という研究も進んでいます」などに書き換える。

## 完了条件

- `output/<handle>.md` と `output/<handle>.meta.json` の両方が存在する
- `<handle>` が `meta.json` の `handle` と一致する
- 本文に `https://totocola.com/products/ととコーラ200ml` への内部リンクが
  最低 1 本含まれている
