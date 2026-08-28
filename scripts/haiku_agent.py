#!/opt/anaconda3/bin/python3
"""
haiku_agent.py — Claude Code CLI（Pro/Maxサブスクリプション経由）で econ_digest 記事を自動生成する

【2026-08-28 変更】
以前は anthropic.Anthropic() で Anthropic API を直接叩いていたが、
API クレジット残高切れで自動実行が止まる障害が繰り返し発生したため、
Claude Code CLI（`claude --print --model haiku`）を subprocess 呼び出しする方式に変更した。
これは ai_news / weather_digest と同じ方式で、Pro/Max サブスクリプションの
利用枠を消費するだけなので、API クレジット残高には一切依存しない。
呼び出し時は ANTHROPIC_API_KEY を環境から明示的に取り除き、サブスク認証を強制する。

役割分担:
  - Claude Code CLI（WebSearch/WebFetch/Write/Read のみ許可）: 情報収集 → 記事執筆 → 保存
  - この Python スクリプト: README.md / index.md 更新・git commit・push（決定論的に実行）

使い方（run_econ_haiku.sh から呼ばれる）:
  python3 haiku_agent.py \
    --mode weekly|monthly \
    --week-file 0704 \
    --week-label "6/28〜7/4" \
    --year 2026 \
    --month 07 \
    [--prefetch "事前収集済みテキスト"] \
    [--model haiku]
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))
DEFAULT_MODEL = "haiku"
CLAUDE_BIN = str(Path.home() / ".local" / "bin" / "claude")

JEKYLL_FRONT_MATTER = "---\nlayout: default\n---\n"

# ------------------------------------------------------------------ #
# ロギング
# ------------------------------------------------------------------ #

def log(msg: str) -> None:
    ts = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

# ------------------------------------------------------------------ #
# README / index.md 更新・git（決定論的に実行。Claude Code CLI には触らせない）
# ------------------------------------------------------------------ #

def append_to_readme(week_label: str, week_path: str) -> str:
    """README.md の Haiku セクション（週次 or 月次）にリンクを追加する"""
    readme = PROJECT_DIR / "README.md"
    lines = readme.read_text(encoding="utf-8").split("\n")

    is_monthly = "haiku_monthly" in week_path
    section_header = "### 月次まとめ（Claude Haiku）" if is_monthly else "### 週次まとめ（Claude Haiku）"

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
        log(f"append_to_readme: セクション '{section_header}' が見つかりませんでした（README はそのまま）")
        return "README 変更なし"

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


def update_index(week_label: str, week_path: str) -> str:
    """articles/haiku_{weekly,monthly}/index.md のリストを更新する"""
    is_monthly = "haiku_monthly" in week_path
    w_stem = Path(week_path).stem  # "2026-0704" or "2026-07"

    if is_monthly:
        w_href = f"articles/haiku_monthly/{w_stem}"
        w_date = w_stem
        sub_index = PROJECT_DIR / "articles/haiku_monthly/index.md"
    else:
        w_year, w_mmdd = w_stem.split("-", 1)
        w_href = f"articles/haiku_weekly/{w_year}-{w_mmdd}"
        w_date = f"{w_year}-{w_mmdd[:2]}-{w_mmdd[2:]}"
        sub_index = PROJECT_DIR / "articles/haiku_weekly/index.md"

    item_li = (
        f'  <li><a href="{{{{ site.baseurl }}}}/{w_href}">'
        f'{week_label}</a><span class="date">{w_date}</span></li>'
    )

    results = []
    if _insert_li_at_top_of_ul(sub_index, item_li):
        results.append(str(sub_index.relative_to(PROJECT_DIR)))

    log(f"update_index (haiku {'monthly' if is_monthly else 'weekly'}): {week_label} → {results}")
    return f"index.md 更新完了: {', '.join(results) if results else '変更なし'}"


def git_commit_push(files: list, message: str) -> bool:
    log(f"git_commit_push: {files}")
    try:
        for f in files:
            subprocess.run(["git", "add", f], cwd=PROJECT_DIR, check=True)
        subprocess.run(["git", "commit", "-m", message], cwd=PROJECT_DIR, check=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=PROJECT_DIR, check=True)
        log("git add / commit / push 完了")
        return True
    except subprocess.CalledProcessError as e:
        log(f"git エラー: {e}")
        return False


def git_dirty_files() -> set:
    """git status --porcelain の対象ファイル集合を返す（想定外の変更検知用）"""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=PROJECT_DIR, capture_output=True, text=True, check=True,
    )
    return {line[3:].strip() for line in result.stdout.splitlines()}

# ------------------------------------------------------------------ #
# プロンプト構築（Claude Code CLI ネイティブツール名で記述）
# ------------------------------------------------------------------ #

PROMPT_WEEKLY_TMPL = """\
あなたは経済・マーケット情報まとめライターです。以下の手順で週次ダイジェスト記事を1本作成してください。

# 厳守事項
- 書き込んでよいファイルは「articles/haiku_weekly/{year}-{week_file}.md」の1つだけです。
  それ以外のファイル（README.md・index.md・他の記事など）には一切触れないでください。
- README 更新・git commit/push は別プロセスが行うため、あなたは行わないでください。
- 記事ファイルの書き込みが完了したら、それ以上ツールを呼ばずに応答を終えてください。

# 基本情報
- 今日: {today}
- 対象期間: {week_label}
- 出力ファイル: articles/haiku_weekly/{year}-{week_file}.md

# 作業手順
1. WebSearch で以下のキーワードを順番に検索する（各キーワード1回ずつ）
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

2. WebFetch で以下のサイトを直接確認する
   - https://www.boj.or.jp/
   - https://www.esri.cao.go.jp/

3. 収集した情報と下記「事前収集済み情報」を統合して記事本文を作成し、
   Write ツールで articles/haiku_weekly/{year}-{week_file}.md に保存する。
   ファイルの冒頭は必ず次の3行から始めること:
   ---
   layout: default
   ---

# 記事フォーマット（必ず守ること）
- タイトル行: `# 経済週次ダイジェスト（{week_label}）`
- 最低 5 トピック以上収録（国内経済動向を必ず 2 件以上含める）
- マーケット動向の表（株価指数・為替・金利）を必ず含める
- 各情報源の URL を必ず記載
- 日本語で記述（経済指標名・指数名は原語も併記）
- 株価・為替は「〜前後」「〜水準」など幅を持たせた表現を用いる（投資助言に見えないようにする）
- 英語タイトルのリンクには日本語訳を併記
  例: `[US CPI Data（米消費者物価指数）](URL)`

# 事前収集済み情報（事前スクリプトで取得済み。空の場合はすべて WebSearch / WebFetch で収集すること）
{prefetch}
"""

PROMPT_MONTHLY_TMPL = """\
あなたは経済・マーケット情報まとめライターです。以下の手順で月次ダイジェスト記事を1本作成してください。

# 厳守事項
- 書き込んでよいファイルは「articles/haiku_monthly/{year}-{month}.md」の1つだけです。
  それ以外のファイル（README.md・index.md・他の記事など）には一切触れないでください（Read のみ許可）。
- README 更新・git commit/push は別プロセスが行うため、あなたは行わないでください。
- 記事ファイルの書き込みが完了したら、それ以上ツールを呼ばずに応答を終えてください。

# 基本情報
- 今日: {today}
- 対象月: {year}年{month_int}月
- 出力ファイル: articles/haiku_monthly/{year}-{month}.md

# 作業手順
1. WebSearch で以下のキーワードを順番に検索する（各キーワード1回ずつ）
   - 「経済 月次まとめ {year}年{month_int}月 日本」
   - 「日経平均 {year}年{month_int}月 月次 推移」
   - 「為替 ドル円 {year}年{month_int}月 月次」
   - 「日銀 金融政策 {year}年{month_int}月」
   - 「GDP 経済指標 {year}年{month_int}月 日本」
   - 「企業決算 業績 {year}年{month_int}月 日本」
   - 「FRB 米国経済 {year}年{month_int}月」
   - 「内閣府 財務省 経済政策 {year}年{month_int}月」

2. WebFetch で以下のサイトを直接確認する
   - https://www.boj.or.jp/
   - https://www.esri.cao.go.jp/

3. Read ツールで先月の Ollama 月次記事 articles/monthly/{year}-{month}.md を参照する
   （存在しない場合はスキップしてよい）

4. 収集した情報と Ollama 月次記事を統合して記事本文を作成し、
   Write ツールで articles/haiku_monthly/{year}-{month}.md に保存する。
   ファイルの冒頭は必ず次の3行から始めること:
   ---
   layout: default
   ---

# 記事フォーマット（必ず守ること）
- タイトル行: `# 経済月次ダイジェスト（{year}年{month_int}月）`
- マーケット月間パフォーマンス表（日経平均・TOPIX・ドル円・金利・原油）必須
- 主要経済指標一覧表必須
- 最低 5 トピック以上収録（国内経済動向を必ず 2 件以上含める）
- Ollama 月次記事と重複するトピックは必ず含め、Haiku 独自の視点・補足情報も追加する
- 各情報源の URL を必ず記載
- 日本語で記述（経済指標名・指数名は原語も併記）
- 月次まとめらしい俯瞰的なトレンド考察を末尾に入れる
- 株価・為替は「〜前後」「〜水準」など幅を持たせた表現を用いる

# 事前収集済み情報（事前スクリプトで取得済み。空の場合はすべて WebSearch / WebFetch で収集すること）
{prefetch}
"""


def build_prompt(args) -> str:
    today = datetime.now(JST).strftime("%Y-%m-%d")
    prefetch = args.prefetch if args.prefetch else "（なし — すべて WebSearch / WebFetch で収集すること）"
    if args.mode == "monthly":
        return PROMPT_MONTHLY_TMPL.format(
            today=today, year=args.year, month=args.month,
            month_int=int(args.month), prefetch=prefetch,
        )
    return PROMPT_WEEKLY_TMPL.format(
        today=today, year=args.year, week_file=args.week_file,
        week_label=args.week_label, prefetch=prefetch,
    )

# ------------------------------------------------------------------ #
# Claude Code CLI 呼び出し（Pro/Maxサブスクリプション。APIクレジット不要）
# ------------------------------------------------------------------ #

# --- オーケストレーション計測（フェーズ1b）: サブスク利用枠の消費を共有台帳へ記録。
#     import・記録に失敗しても本処理は継続する。 ---
try:
    sys.path.insert(0, "/Users/masahiro/projects/agent_orchestrator")
    from orch_meter import record_llm as _orch_record_llm

    def _rec_haiku(model, in_tok, out_tok, wall_s, usd, is_error):
        _orch_record_llm("econ_digest", "haiku_run", "haiku", model,
                         in_tok, out_tok, wall_s,
                         usd=usd or 0.0, billing="subscription",
                         gate="error" if is_error else "n/a")
except Exception:
    def _rec_haiku(*_a, **_k):
        return None


def _cli_model(m: str) -> str:
    """フルモデルID（claude-haiku-4-5-...）を CLI エイリアスへ正規化する。"""
    if m.startswith("claude-haiku"):
        return "haiku"
    if m.startswith("claude-sonnet"):
        return "sonnet"
    if m.startswith("claude-opus"):
        return "opus"
    return m


def run_claude_cli(prompt: str, model: str, budget_usd: str, timeout_sec: int = 1800) -> bool:
    import json as _json
    import time as _time

    model = _cli_model(model)
    env = os.environ.copy()
    # サブスク認証を強制するため、APIキー系の環境変数は明示的に除去する
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("ANTHROPIC_BASE_URL", None)

    cmd = [
        CLAUDE_BIN,
        "--print",
        "--dangerously-skip-permissions",
        "--model", model,
        "--max-budget-usd", budget_usd,
        "--allowedTools", "WebSearch,WebFetch,Write,Read",
        "--input-format", "text",
        "--output-format", "json",   # usage / コストを取得して計測するため
    ]
    log(f"Claude Code CLI 起動: model={model} budget=${budget_usd}")
    _t0 = _time.monotonic()
    try:
        result = subprocess.run(
            cmd, input=prompt, text=True, cwd=PROJECT_DIR, env=env,
            timeout=timeout_sec, capture_output=True,
        )
    except subprocess.TimeoutExpired:
        log(f"ERROR: Claude Code CLI がタイムアウトしました（{timeout_sec}秒）")
        return False
    _wall = _time.monotonic() - _t0

    if result.stderr:
        log(result.stderr.strip())

    data = {}
    try:
        data = _json.loads(result.stdout or "{}")
    except ValueError:
        log((result.stdout or "(CLI 出力なし)")[:2000])

    _u = data.get("usage") or {}
    _in = (int(_u.get("input_tokens", 0)) + int(_u.get("cache_read_input_tokens", 0))
           + int(_u.get("cache_creation_input_tokens", 0)))
    _rec_haiku(model, _in, int(_u.get("output_tokens", 0)), _wall,
               data.get("total_cost_usd"), data.get("is_error"))

    _text = data.get("result") or ""
    if _text:
        log(f"--- Claude Code CLI 出力 ---\n{_text}\n---------------------------")

    if result.returncode != 0 or data.get("is_error") is True:
        log(f"ERROR: Claude Code CLI 失敗（exit={result.returncode} "
            f"is_error={data.get('is_error')}）")
        return False
    return True

# ------------------------------------------------------------------ #
# メインフロー
# ------------------------------------------------------------------ #

def run_agent(args) -> bool:
    if args.mode == "monthly":
        article_rel = f"articles/haiku_monthly/{args.year}-{args.month}.md"
        week_path = f"./articles/haiku_monthly/{args.year}-{args.month}.md"
        week_label = f"{args.year}年{int(args.month)}月"
        sub_index = "articles/haiku_monthly/index.md"
        budget = "3.00"
    else:
        article_rel = f"articles/haiku_weekly/{args.year}-{args.week_file}.md"
        week_path = f"./articles/haiku_weekly/{args.year}-{args.week_file}.md"
        week_label = args.week_label
        sub_index = "articles/haiku_weekly/index.md"
        budget = "2.00"

    article_path = PROJECT_DIR / article_rel

    log(f"Haikuエージェント開始（Claude Code CLI方式）: model={args.model}, mode={args.mode}, week={args.week_file}")

    if article_path.exists():
        log(f"記事は既に存在するため生成をスキップ: {article_rel}")
    else:
        before = git_dirty_files()
        prompt = build_prompt(args)
        ok = run_claude_cli(prompt, args.model, budget)

        if not ok or not article_path.exists():
            log(f"ERROR: 記事生成に失敗しました（ファイル未生成: {article_rel}）")
            return False

        # 想定外のファイル変更がないか確認（README/index等を誤って触っていないか）
        after = git_dirty_files()
        unexpected = {f for f in (after - before) if f != article_rel}
        if unexpected:
            log(f"ERROR: 想定外のファイルが変更されました: {unexpected} → 安全のため後処理を中断します")
            return False

        if not article_path.read_text(encoding="utf-8").startswith("---"):
            content = JEKYLL_FRONT_MATTER + article_path.read_text(encoding="utf-8")
            article_path.write_text(content, encoding="utf-8")

        log(f"記事生成完了: {article_rel}")

    # --- README / index.md 更新・git commit/push（決定論的） ---
    append_to_readme(week_label, week_path)
    update_index(week_label, week_path)

    commit_message = (
        f"{args.year}-{args.week_file if args.mode == 'weekly' else args.month} "
        f"Haiku{'月次' if args.mode == 'monthly' else '週次'}まとめを追加（Claude Haiku生成）\n\n"
        f"Co-Authored-By: Claude Haiku (via Claude Code CLI) <noreply@anthropic.com>"
    )
    files = [article_rel, "README.md", sub_index]
    return git_commit_push(files, commit_message)

# ------------------------------------------------------------------ #
# エントリポイント
# ------------------------------------------------------------------ #

def main():
    parser = argparse.ArgumentParser(description="econ_digest Haiku エージェント（Claude Code CLI / サブスクリプション）")
    parser.add_argument("--mode",       required=True, choices=["weekly", "monthly"])
    parser.add_argument("--week-file",  required=True, help="MMDD形式（例: 0704）")
    parser.add_argument("--week-label", required=True, help="例: 6/28〜7/4")
    parser.add_argument("--year",       required=True, help="例: 2026")
    parser.add_argument("--month",      required=True, help="例: 07")
    parser.add_argument("--model",      default=DEFAULT_MODEL,
                        help="Claude Code CLI モデル（haiku / sonnet / フルID）")
    parser.add_argument("--prefetch",   default="", help="事前収集スクリプトの出力テキスト")
    args = parser.parse_args()

    if not Path(CLAUDE_BIN).exists():
        log(f"ERROR: Claude Code CLI が見つかりません: {CLAUDE_BIN}")
        sys.exit(1)

    success = run_agent(args)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
