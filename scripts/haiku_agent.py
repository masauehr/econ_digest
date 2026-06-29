#!/opt/anaconda3/bin/python3
"""
haiku_agent.py — Claude Haiku (Anthropic API) で econ_digest 記事を自動生成する

使い方（run_econ_haiku.sh から呼ばれる）:
  python3 haiku_agent.py \
    --mode weekly|monthly \
    --week-file 0704 \
    --week-label "6/28〜7/4" \
    --year 2026 \
    --month 07 \
    [--model claude-haiku-4-5-20251001]
"""

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import anthropic
import requests
from ddgs import DDGS
import trafilatura

PROJECT_DIR = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))
DEFAULT_MODEL = "claude-haiku-4-5-20251001"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en;q=0.9",
}

# ------------------------------------------------------------------ #
# ツール定義（Anthropic SDK format）
# ------------------------------------------------------------------ #

TOOLS = [
    {
        "name": "search_web",
        "description": (
            "DuckDuckGo でウェブ検索し、タイトル・URL・スニペットを返す。"
            "最新の経済ニュースを調べるときに使う。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "検索クエリ（日本語・英語可）",
                },
                "max_results": {
                    "type": "integer",
                    "description": "取得件数（省略時 8）",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch_url",
        "description": (
            "指定 URL のページを取得し、メインテキストを返す。"
            "JS 描画が必要なサイトは取得できないことがある。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "取得する URL"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "write_article",
        "description": (
            "新しい記事ファイルを書き込む。"
            "既存ファイルが存在する場合はエラーを返す（上書き禁止）。"
            "パスは PROJECT_DIR からの相対パスで指定する。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "書き込み先（例: articles/haiku_weekly/2026-0704.md）",
                },
                "content": {
                    "type": "string",
                    "description": "書き込む Markdown 内容",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "read_file",
        "description": "ファイルを読み込んで内容を返す。パスは PROJECT_DIR からの相対パス。",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "読み込むファイルのパス"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "append_to_readme",
        "description": (
            "README.md の Haiku 週次まとめセクションに週次リンクを追加する。"
            "README の直接編集には使わないこと。このツール専用。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "week_label": {
                    "type": "string",
                    "description": "週次ラベル（例: 6/28〜7/4）",
                },
                "week_path": {
                    "type": "string",
                    "description": "週次記事の相対パス（例: ./articles/haiku_weekly/2026-0704.md）",
                },
            },
            "required": ["week_label", "week_path"],
        },
    },
    {
        "name": "update_index",
        "description": (
            "GitHub Pages サイトの index.md の Haiku 記事リストを更新する。"
            "append_to_readme の直後に必ず呼ぶこと。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "week_label": {
                    "type": "string",
                    "description": "週次ラベル（例: 6/28〜7/4）",
                },
                "week_path": {
                    "type": "string",
                    "description": "週次記事の相対パス（例: ./articles/haiku_weekly/2026-0704.md）",
                },
            },
            "required": ["week_label", "week_path"],
        },
    },
    {
        "name": "git_commit_push",
        "description": "変更ファイルを git add / commit / push する。記事と README の更新が完了してから呼ぶ。",
        "input_schema": {
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "コミット対象ファイルのリスト（PROJECT_DIR からの相対パス）",
                },
                "message": {
                    "type": "string",
                    "description": "コミットメッセージ",
                },
            },
            "required": ["files", "message"],
        },
    },
]

# ------------------------------------------------------------------ #
# ツール実装
# ------------------------------------------------------------------ #

def tool_search_web(query: str, max_results: int = 8) -> str:
    log(f"search_web: {query!r} (max={max_results})")
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return "検索結果なし"
        lines = []
        for r in results:
            lines.append(
                f"- [{r.get('title','')}]({r.get('href','')})\n"
                f"  {r.get('body','')[:200]}"
            )
        return "\n\n".join(lines)
    except Exception as e:
        return f"search_web エラー: {e}"


def tool_fetch_url(url: str) -> str:
    log(f"fetch_url: {url}")
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded, include_links=True, favor_precision=True)
            if text:
                return text[:6000]
    except Exception:
        pass
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        text = re.sub(r"<[^>]+>", " ", r.text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:6000]
    except Exception as e:
        return f"fetch_url エラー: {e}"


JEKYLL_FRONT_MATTER = "---\nlayout: default\n---\n"


def tool_write_article(path: str, content: str) -> str:
    full = PROJECT_DIR / path
    if full.exists():
        return f"エラー: {path} は既に存在します。上書き禁止。"
    full.parent.mkdir(parents=True, exist_ok=True)
    if not content.startswith("---"):
        content = JEKYLL_FRONT_MATTER + content
    full.write_text(content, encoding="utf-8")
    log(f"write_article: {path} ({len(content)} chars)")
    return f"書き込み完了: {path}"


def tool_read_file(path: str) -> str:
    full = PROJECT_DIR / path
    if not full.exists():
        return f"ファイルが存在しません: {path}"
    return full.read_text(encoding="utf-8")


def tool_append_to_readme(week_label: str, week_path: str) -> str:
    readme = PROJECT_DIR / "README.md"
    lines = readme.read_text(encoding="utf-8").split("\n")

    is_monthly = "haiku_monthly" in week_path
    section_header = "### Haiku月次まとめ（Claude Haiku）" if is_monthly else "### Haiku週次まとめ（Claude Haiku）"

    new_line = f"- [{week_label}]({week_path})"
    result = []
    inserted = False
    i = 0

    while i < len(lines):
        result.append(lines[i])
        if not inserted and lines[i].strip() == section_header:
            if i + 1 < len(lines) and lines[i + 1].strip() == "":
                result.append(lines[i + 1])
                i += 1
            result.append(new_line)
            inserted = True
        i += 1

    if not inserted:
        log(f"append_to_readme: セクション '{section_header}' が見つかりませんでした")

    readme.write_text("\n".join(result), encoding="utf-8")
    log(f"append_to_readme (haiku {'monthly' if is_monthly else 'weekly'}): {new_line}")
    return f"README 更新完了: {new_line}"


def _insert_li_at_top_of_ul(md_path: Path, new_li: str) -> bool:
    if not md_path.exists():
        return False
    lines = md_path.read_text(encoding="utf-8").split("\n")
    result = []
    inserted = False
    for line in lines:
        result.append(line)
        if not inserted and line.strip() == '<ul class="article-list">':
            result.append(new_li)
            inserted = True
    if inserted:
        md_path.write_text("\n".join(result), encoding="utf-8")
    return inserted


def tool_update_index(week_label: str, week_path: str) -> str:
    is_monthly = "haiku_monthly" in week_path
    w_stem = Path(week_path).stem

    if is_monthly:
        w_href = f"articles/haiku_monthly/{w_stem}"
        w_date = w_stem
        item_li = (
            f'  <li><a href="{{{{ site.baseurl }}}}/{w_href}">'
            f'{week_label}</a><span class="date">{w_date}</span></li>'
        )
        sub_index = PROJECT_DIR / "articles/haiku_monthly/index.md"
    else:
        w_year, w_mmdd = w_stem.split("-", 1)
        w_href = f"articles/haiku_weekly/{w_year}-{w_mmdd}"
        w_date = f"{w_year}-{w_mmdd[:2]}-{w_mmdd[2:]}"
        item_li = (
            f'  <li><a href="{{{{ site.baseurl }}}}/{w_href}">'
            f'{week_label}</a><span class="date">{w_date}</span></li>'
        )
        sub_index = PROJECT_DIR / "articles/haiku_weekly/index.md"

    results = []
    if _insert_li_at_top_of_ul(sub_index, item_li):
        results.append(str(sub_index.relative_to(PROJECT_DIR)))

    log(f"update_index (haiku {'monthly' if is_monthly else 'weekly'}): {week_label} → {results}")
    return f"index.md 更新完了: {', '.join(results) if results else '変更なし'}"


def tool_git_commit_push(files: list, message: str) -> str:
    log(f"git_commit_push: {files}")
    try:
        for f in files:
            subprocess.run(["git", "add", f], cwd=PROJECT_DIR, check=True)
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=PROJECT_DIR,
            check=True,
        )
        subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=PROJECT_DIR,
            check=True,
        )
        return "git add / commit / push 完了"
    except subprocess.CalledProcessError as e:
        return f"git エラー: {e}"


TOOL_HANDLERS = {
    "search_web":       lambda a: tool_search_web(**a),
    "fetch_url":        lambda a: tool_fetch_url(**a),
    "write_article":    lambda a: tool_write_article(**a),
    "read_file":        lambda a: tool_read_file(**a),
    "append_to_readme": lambda a: tool_append_to_readme(**a),
    "update_index":     lambda a: tool_update_index(**a),
    "git_commit_push":  lambda a: tool_git_commit_push(**a),
}

# ------------------------------------------------------------------ #
# ロギング
# ------------------------------------------------------------------ #

def log(msg: str) -> None:
    ts = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

# ------------------------------------------------------------------ #
# システムプロンプト
# ------------------------------------------------------------------ #

SYSTEM_PROMPT_WEEKLY_TMPL = """\
あなたは経済・マーケット情報まとめライターです。
以下の手順に従い、ツールを使いながら週次まとめ記事を自動生成してください。

# 基本情報
- 今日: {today}
- 実行モード: {mode}
- 週次ファイルパス: articles/haiku_weekly/{year}-{week_file}.md
- 週表示ラベル: {week_label}（記事タイトル・READMEリンクに使用）

# 作業手順
1. **情報収集** — search_web で以下のキーワードを順番に検索する（各キーワード1回ずつ）
   - 「経済ニュース 今週 日本」
   - 「日経平均 株式市場 今週 まとめ」
   - 「ドル円 為替 今週 推移」
   - 「日銀 金融政策 最新」
   - 「米国経済 FRB 金利 最新」
   - 「GDP 物価 CPI 日本 最新」
   - 「企業決算 業績 今週 日本」
   - 「内閣府 財務省 経済政策 最新」
   - 「中国経済 米中関係 最新」
   - 「日本 M&A 企業動向 今週」

2. **補足取得** — fetch_url で以下のサイトを直接確認する
   - https://www.boj.or.jp/（日本銀行トップページ）
   - https://www.esri.cao.go.jp/（内閣府経済社会総合研究所）

3. **記事生成** — 収集した情報を統合して週次記事を生成し、write_article で保存する
   - ファイルパスは必ず articles/haiku_weekly/{year}-{week_file}.md を使うこと

4. **README 更新** — append_to_readme ツールで Haiku 週次リンクを追加する

5. **index.md 更新** — update_index ツールで GitHub Pages のトップページ記事リストを更新する

6. **コミット** — git_commit_push で以下のファイルをコミット・プッシュする
   - articles/haiku_weekly/{year}-{week_file}.md
   - README.md
   - articles/haiku_weekly/index.md

# 記事フォーマット（必ず守ること）
- ファイル: articles/haiku_weekly/{year}-{week_file}.md
- タイトル行: `# 経済週次ダイジェスト（{week_label}）`
- 最低 5 トピック以上収録（国内経済動向を必ず 2 件以上含める）
- マーケット動向の表（株価指数・為替・金利）を必ず含める
- 各情報源の URL を必ず記載
- 日本語で記述（経済指標名・指数名は原語も記載）
- 株価・為替は「〜前後」「〜水準」など幅を持たせた表現を用いる（投資助言に見えないようにする）
- 英語タイトルのリンクには日本語訳を併記
  例: `[US CPI Data（米消費者物価指数）](URL)`

# append_to_readme の引数
- week_label: "{week_label}"
- week_path: "./articles/haiku_weekly/{year}-{week_file}.md"

# update_index の引数（append_to_readme と同じ値を使用）
- week_label: "{week_label}"
- week_path: "./articles/haiku_weekly/{year}-{week_file}.md"

# コミットメッセージ形式
```
{year}-{week_file} Haiku週次まとめを追加（Claude Haiku生成）

Co-Authored-By: {model} via Anthropic API <noreply@anthropic.com>
```
"""

SYSTEM_PROMPT_MONTHLY_TMPL = """\
あなたは経済・マーケット情報まとめライターです。
以下の手順に従い、ツールを使いながら月次まとめ記事を自動生成してください。

# 基本情報
- 今日: {today}
- 実行モード: {mode}
- 月次ファイルパス: articles/haiku_monthly/{year}-{month}.md
- 月表示ラベル: {year}年{month_int}月

# 作業手順
1. **情報収集** — search_web で以下のキーワードを順番に検索する（各キーワード1回ずつ）
   - 「経済 月次まとめ {year}年{month_int}月 日本」
   - 「日経平均 {year}年{month_int}月 月次 推移」
   - 「為替 ドル円 {year}年{month_int}月 月次」
   - 「日銀 金融政策 {year}年{month_int}月」
   - 「GDP 経済指標 {year}年{month_int}月 日本」
   - 「企業決算 業績 {year}年{month_int}月 日本」
   - 「FRB 米国経済 {year}年{month_int}月」
   - 「内閣府 財務省 経済政策 {year}年{month_int}月」

2. **補足取得** — fetch_url で以下のサイトを直接確認する
   - https://www.boj.or.jp/
   - https://www.esri.cao.go.jp/
   - 先月の Ollama 月次記事 articles/monthly/{year}-{month}.md を read_file で参照する

3. **記事生成** — 収集した情報と Ollama 月次記事を統合して月次記事を生成し、write_article で保存する
   - ファイルパスは必ず articles/haiku_monthly/{year}-{month}.md を使うこと

4. **README 更新** — append_to_readme ツールで Haiku 月次リンクを追加する

5. **index.md 更新** — update_index ツールで GitHub Pages のトップページ記事リストを更新する

6. **コミット** — git_commit_push で以下のファイルをコミット・プッシュする
   - articles/haiku_monthly/{year}-{month}.md
   - README.md
   - articles/haiku_monthly/index.md

# 記事フォーマット（必ず守ること）
- ファイル: articles/haiku_monthly/{year}-{month}.md
- タイトル行: `# 経済月次ダイジェスト（{year}年{month_int}月）`
- マーケット月間パフォーマンス表（日経平均・TOPIX・ドル円・金利・原油）必須
- 主要経済指標一覧表必須
- 最低 5 トピック以上収録（国内経済動向を必ず 2 件以上含める）
- Ollama 月次記事と重複するトピックは必ず含め、Haiku 独自の視点・補足情報も追加する
- 各情報源の URL を必ず記載
- 日本語で記述（経済指標名・指数名は原語も記載）
- 月次まとめらしい俯瞰的なトレンド考察を末尾に入れる
- 株価・為替は「〜前後」「〜水準」など幅を持たせた表現を用いる

# append_to_readme の引数
- week_label: "{year}年{month_int}月"
- week_path: "./articles/haiku_monthly/{year}-{month}.md"

# update_index の引数（append_to_readme と同じ値を使用）
- week_label: "{year}年{month_int}月"
- week_path: "./articles/haiku_monthly/{year}-{month}.md"

# コミットメッセージ形式
```
{year}-{month} Haiku月次まとめを追加（Claude Haiku生成）

Co-Authored-By: {model} via Anthropic API <noreply@anthropic.com>
```
"""

SYSTEM_PROMPT_TMPL = SYSTEM_PROMPT_WEEKLY_TMPL


def build_system_prompt(args) -> str:
    today = datetime.now(JST).strftime("%Y-%m-%d")
    if args.mode == "monthly":
        return SYSTEM_PROMPT_MONTHLY_TMPL.format(
            today=today,
            mode=args.mode,
            year=args.year,
            month=args.month,
            month_int=int(args.month),
            model=args.model,
        )
    return SYSTEM_PROMPT_WEEKLY_TMPL.format(
        today=today,
        mode=args.mode,
        year=args.year,
        week_file=args.week_file,
        week_label=args.week_label,
        model=args.model,
    )

# ------------------------------------------------------------------ #
# Anthropic API チャットループ
# ------------------------------------------------------------------ #

def run_agent(args) -> bool:
    client = anthropic.Anthropic()
    system_prompt = build_system_prompt(args)

    messages = [
        {"role": "user", "content": "記事生成を開始してください。"},
    ]

    log(f"Haikuエージェント開始: model={args.model}, mode={args.mode}, week={args.week_file}")

    MAX_TURNS = 40
    LOOP_THRESHOLD = 2
    FORCE_WRITE_TURN = 14

    call_counts: dict = {}
    url_cache: dict = {}
    write_article_called = False
    force_write_prompted = False
    turn = 0

    while turn < MAX_TURNS:
        log(f"--- ターン {turn + 1}/{MAX_TURNS} ---")

        if turn >= FORCE_WRITE_TURN and not write_article_called and not force_write_prompted:
            log("WARN: 情報収集ターン超過 → write_article を促進")
            messages.append({
                "role": "user",
                "content": (
                    "情報収集は十分に完了しています。これ以上の検索・URL取得は不要です。"
                    "今すぐ write_article ツールを呼び出して週次記事を生成してください。"
                    "記事生成後、append_to_readme → update_index → git_commit_push の順で後処理を行ってください。"
                ),
            })
            force_write_prompted = True

        try:
            response = client.messages.create(
                model=args.model,
                max_tokens=8192,
                system=system_prompt,
                messages=messages,
                tools=TOOLS,
            )
        except anthropic.APIError as e:
            log(f"ERROR: Anthropic API エラー: {e}")
            raise

        for block in response.content:
            if hasattr(block, "text") and block.text:
                log(f"モデル応答: {block.text[:300]}")

        if response.stop_reason == "end_turn":
            log("end_turn → 完了")
            break

        if response.stop_reason != "tool_use":
            log(f"stop_reason={response.stop_reason} → 完了")
            break

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            name = block.name
            raw_args = block.input if isinstance(block.input, dict) else {}

            args_key = json.dumps(raw_args, sort_keys=True, ensure_ascii=False)
            call_key = (name, args_key)
            call_counts[call_key] = call_counts.get(call_key, 0) + 1

            if call_counts[call_key] > LOOP_THRESHOLD:
                log(f"LOOP検出: {name} {call_counts[call_key]}回目 → スキップ")
                result = (
                    f"[重複スキップ] {name} の同一引数での呼び出しは {call_counts[call_key]} 回目です。"
                    "write_article ツールで記事を生成してください。"
                )
            elif name == "fetch_url" and raw_args.get("url") in url_cache:
                url = raw_args["url"]
                log(f"CACHE HIT: {url}")
                result = (
                    f"[取得済みキャッシュ] この URL はすでに取得しています:\n"
                    f"{url_cache[url][:1000]}\n\n"
                    "write_article ツールで記事を生成してください。"
                )
            else:
                log(f"ツール呼び出し: {name}({args_key[:120]})")
                handler = TOOL_HANDLERS.get(name)
                if handler:
                    try:
                        result = handler(raw_args)
                    except Exception as e:
                        result = f"ツール実行エラー: {e}"
                else:
                    result = f"未知のツール: {name}"

                if name == "fetch_url" and not str(result).startswith("fetch_url エラー"):
                    url_cache[raw_args.get("url", "")] = str(result)

                if name == "write_article" and "書き込み完了" in str(result):
                    write_article_called = True
                    log("write_article 完了 → 後処理フェーズへ")

            log(f"ツール結果: {str(result)[:300]}")
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": str(result),
            })

            if name == "search_web":
                time.sleep(2)

        messages.append({"role": "user", "content": tool_results})
        turn += 1

    if turn >= MAX_TURNS:
        log(f"ERROR: 最大ターン数 ({MAX_TURNS}) に達しました")

    return write_article_called

# ------------------------------------------------------------------ #
# エントリポイント
# ------------------------------------------------------------------ #

def main():
    parser = argparse.ArgumentParser(description="econ_digest Haiku エージェント（Anthropic API）")
    parser.add_argument("--mode",       required=True, choices=["weekly", "monthly"])
    parser.add_argument("--week-file",  required=True, help="MMDD形式（例: 0704）")
    parser.add_argument("--week-label", required=True, help="例: 6/28〜7/4")
    parser.add_argument("--year",       required=True, help="例: 2026")
    parser.add_argument("--month",      required=True, help="例: 07")
    parser.add_argument("--model",      default=DEFAULT_MODEL, help="Anthropic モデル名")
    args = parser.parse_args()

    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log("ERROR: ANTHROPIC_API_KEY が設定されていません")
        log("  ~/.anthropic_env に ANTHROPIC_API_KEY=sk-ant-... を記載してください")
        sys.exit(1)

    success = run_agent(args)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
