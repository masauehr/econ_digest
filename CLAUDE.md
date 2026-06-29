# CLAUDE.md — econ_digest プロジェクト専用指示

## このプロジェクトについて

経済・マーケット・財政に関する最新情報を週次・月次でまとめ、
GitHubで公開するプロジェクト。

| エンジン | 実行時刻 | スクリプト |
|---|---|---|
| Ollama（qwen3.6:35b-mlx） | 毎週金曜 09:00 | `run_econ_ollama.sh` → `local_agent.py` |
| Claude Haiku（Anthropic API） | 毎週金曜 13:00 | `run_econ_haiku.sh` → `haiku_agent.py` |
| 比較ページ生成 | 13:00 以降（Haiku完了後） | `generate_compare.py` |

---

## 自動実行時の動作フロー

### Step 1: 日付判定

今日が「月の第1金曜日」かどうかを判定する。

```bash
DAY=$(TZ=Asia/Tokyo date +%d)
if [ "$DAY" -le 7 ]; then
  # 月次モード（月次まとめ + 週次まとめ）
else
  # 週次モードのみ
fi
```

### Step 2: 情報収集（WebSearch / WebFetch）

以下のサイト・キーワードで最新情報を収集する（直近7日間を対象）:

**収集キーワード（WebSearch）**:
- `経済ニュース 今週 日本`
- `日経平均 株式市場 今週`
- `為替 円ドル 今週`
- `日本銀行 金融政策 最新`
- `米国経済 FRB 金利 最新`

**優先収集キーワード（SPEC.md の注目トピック — 必ず検索すること）**:
- `GDP 経済成長 日本 最新` / `景気指標 内閣府 今週`
- `日銀 政策金利 インフレ 今週`
- `企業決算 業績 主要企業 今週`
- `物価 CPI 消費者物価 今週`

**⚠️ マーケット動向（必ず個別に検索すること — 特に重要）**:
- 日経平均・TOPIX・ドル円・米国市場（S&P500・NASDAQ）の週次動向
- 検索クエリ例:
  - `日経平均 今週 相場 まとめ`
  - `ドル円 今週 推移 為替`
  - `米国株 S&P500 今週`
  - `金利 国債 今週 日本`

**日本政府・行政（必ず個別に確認すること）**:
- 内閣府統計ページを WebFetch で直接確認（URL: https://www.esri.cao.go.jp/ ）
- `内閣府 月例経済報告 最新` / `財務省 予算 経済政策 最新`
- `経産省 産業政策 最新` / `金融庁 規制 最新`
- `日銀 展望レポート 金融政策 最新`

**国内企業・産業動向（偏りなく幅広く収集すること）**:
- `日本企業 決算 業績 今週`
- `東証プライム 上場企業 動向 今週`
- `製造業 サービス業 景況感 今週`
- `日本 M&A 企業再編 最新`

**参照サイト（WebFetch）**:
- 日本経済新聞（nikkei.com）
- Bloomberg Japan
- ロイター日本語版
- 東洋経済オンライン（toyokeizai.net）
- 内閣府（cao.go.jp）
- 財務省（mof.go.jp）
- 日本銀行（boj.or.jp）

### Step 3: 週次記事の生成

ファイル名: `articles/weekly/YYYY-MMDD.md`（例: `2026-0703.md`、MMDD はその週の金曜日の月日）

SPEC.md の週次フォーマットに従い記事を生成する。
- 最低5トピック以上を収録（国内経済動向を必ず2件以上含める）
- 各情報源のURLを必ず記載
- 日本語で記述（経済用語・指数名は原語も記載）
- **英語記事・英語タイトルのリンクには、必ず日本語訳タイトルを併記する**
  - 例: `[US CPI Data（米消費者物価指数データ）](https://...)`
- 記事タイトルは `# 経済週次ダイジェスト（MM/DD〜MM/DD）` の形式で月日表記を使うこと
  （スクリプトから渡される `WEEK_LABEL` の値を使う）

### Step 4: 月次記事の生成（第1金曜のみ）

ファイル名: `articles/monthly/YYYY-MM.md`（例: `2026-07.md`）

SPEC.md の月次フォーマットに従い記事を生成する。
- 前月の週次まとめ記事を参照してサマリーを作成
- 主要トピックを3件以上深掘り
- マーケット月間パフォーマンス表を必ず含める

### Step 5: README.md の更新

`README.md` の「最新記事」セクションに、生成した記事へのリンクを追記する。

週次まとめのリンク形式:
```markdown
- [MM/DD〜MM/DD](./articles/weekly/YYYY-MMDD.md)
```

月次まとめのリンク形式:
```markdown
- [YYYY年MM月](./articles/monthly/YYYY-MM.md)
```

### Step 6: git commit & push

```bash
git add articles/ README.md
git commit -m "YYYY-MMDD 週次まとめを追加

- トピック数: X件
- 主な内容: 〜

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"

git push origin main
```

---

## 記事生成の注意事項

- 情報ソースのURLは必ず記載する
- 推測・憶測は「〜とみられる」「〜の可能性がある」と明示する
- 個人情報・機密情報は含めない
- 著作権に配慮し、要約・引用にとどめる（原文の大量コピーは避ける）
- 既存の記事ファイルは上書きしない（同名ファイルが存在する場合はスキップ）
- 株価・為替等の数値は「概算」「〜前後」など幅を持たせた表現を使い、投資助言と誤解されないよう注意する

---

## ファイルパス一覧

| 目的 | パス |
|---|---|
| Ollama 週次記事 | `/Users/masahiro/projects/econ_digest/articles/weekly/YYYY-MMDD.md` |
| Haiku 週次記事 | `/Users/masahiro/projects/econ_digest/articles/haiku_weekly/YYYY-MMDD.md` |
| モデル比較ページ | `/Users/masahiro/projects/econ_digest/articles/compare/YYYY-MMDD.md` |
| 月次記事 | `/Users/masahiro/projects/econ_digest/articles/monthly/YYYY-MM.md` |
| README | `/Users/masahiro/projects/econ_digest/README.md` |
| Ollama 実行ログ | `/Users/masahiro/projects/econ_digest/econ_digest.log` |
| Haiku 実行ログ | `/Users/masahiro/projects/econ_digest/econ_digest_haiku.log` |
| Ollama エージェント | `/Users/masahiro/projects/econ_digest/scripts/local_agent.py` |
| Haiku エージェント | `/Users/masahiro/projects/econ_digest/scripts/haiku_agent.py` |
| 比較生成スクリプト | `/Users/masahiro/projects/econ_digest/scripts/generate_compare.py` |
| ANTHROPIC_API_KEY | `~/.anthropic_env`（`ANTHROPIC_API_KEY=sk-ant-...` を記載） |
