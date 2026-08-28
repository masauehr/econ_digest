# econ_digest 運用詳細

README.md の簡略化で省いた詳細情報をここに保管する。

---

## プロジェクト構成

```
econ_digest/
├── README.md                              # 最新記事一覧・クイックリンク
├── SPEC.md                                # 情報収集・記事生成の仕様
├── econ-digest.md                         # このファイル（運用詳細）
├── articles/
│   ├── weekly/YYYY-MMDD.md               # Ollama 週次記事（金曜 09:00 自動生成）
│   ├── haiku_weekly/YYYY-MMDD.md         # Haiku 週次記事（金曜 13:00 自動生成）
│   ├── compare/YYYY-MMDD.md              # モデル比較ページ（13:00 以降 自動生成）
│   ├── monthly/YYYY-MM.md                # Ollama 月次まとめ（第1金曜 自動生成）
│   ├── haiku_monthly/YYYY-MM.md          # Haiku 月次まとめ（第1金曜 自動生成）
│   └── topics/YYYY-MM-DD_slug.md         # トピックス（単発深掘りレポート）
└── scripts/
    ├── local_agent.py                     # Ollama エージェント（09:00 実行）
    ├── haiku_agent.py                     # Claude Haiku エージェント（13:00 実行）
    ├── generate_compare.py                # 比較ページ生成スクリプト
    ├── run_econ_ollama.sh                 # Ollama 実行スクリプト（launchd）
    ├── run_econ_haiku.sh                  # Haiku 実行スクリプト（launchd）
    ├── com.user.econ_digest_ollama.plist  # launchd 設定（09:00）
    └── com.user.econ_digest_haiku.plist   # launchd 設定（13:00）
```

---

## 使用モデル

| 実行タイミング | モデル | 種別 |
|---|---|---|
| 09:00 | `qwen3.6:35b-mlx` | Ollama ローカルLLM（デフォルト） |
| 13:00（事前収集・要約） | `qwen3.6:35b-mlx` | Ollama（agent_orchestrator 経由。下記フェーズ2参照） |
| 13:00（記事執筆） | `haiku` | Claude Code CLI（Pro/Max サブスクリプション） |
| 13:00（比較評価） | `sonnet` | Claude Code CLI（Pro/Max サブスクリプション） |

モデルは環境変数 `ECON_OLLAMA_MODEL` で上書き可能（Ollama 版のみ）。
Haiku は `HAIKU_MODEL`（既定 `haiku`。フルID `claude-haiku-4-5-...` でも可、CLI 側で正規化）。

### 【2026-08-28】Haiku を Claude Code CLI 方式へ変更（API 依存の撤廃）

`haiku_agent.py` は以前 `anthropic.Anthropic()` で Anthropic API を直接叩く tool-loop 実装
だったが、**API クレジット残高切れで自動実行が止まる障害が頻発**したため、
ai_news / weather_digest と同じ **Claude Code CLI（`claude --print --model haiku`、
Pro/Max サブスクリプション）方式**へ全面書き換えた。`ANTHROPIC_API_KEY` は不要。

- CLI には `WebSearch,WebFetch,Write,Read` のみ許可し、**記事執筆だけ**を行わせる。
- README.md / `articles/haiku_weekly(monthly)/index.md` の更新・git commit/push は
  `haiku_agent.py`（Python）が決定論的に実行する（想定外ファイル変更の検知つき）。
- `run_econ_haiku.sh` は `ANTHROPIC_API_KEY` 必須チェックを撤廃し、`~/.local/bin/claude`
  の存在確認に置換した。

---

## フェーズ2: 事前収集＋ローカル要約（agent_orchestrator 連携）

**目的**: 記事執筆モデル（Haiku）のコンテキストに「Web 記事の生本文」を入れず、
ローカル(Ollama)で作った**圧縮サマリ**だけを渡して入力トークンを削減する。

**フロー**（`run_econ_haiku.sh` が Haiku 起動前に自動実行）:

```
orchestrator.cli run econ_prefetch
  → search  : ddgs で10クエリ検索・URL重複除去（最大24件）
  → fetch   : trafilatura で本文抽出（並列・失敗は破棄）
  → map     : 各記事を qwen3.6 で220字要約（force_local）
  → join    : 「- 」始まりの箇条書きに連結
  → write   : econ_digest/var/prefetch_YYYY-MMDD.txt
haiku_agent.py --prefetch @econ_digest/var/prefetch_YYYY-MMDD.txt
  → Haiku はこのサマリを起点に不足分だけ WebSearch/WebFetch して記事化
```

- パイプライン定義: `~/projects/agent_orchestrator/config/pipelines/econ_prefetch.toml`
- 事前収集が失敗しても Haiku 単独実行にフォールバックする（`--prefetch` なし）。
- `--prefetch` は本文テキストのほか `@/path/to/file` でファイル指定に対応。
- 全 LLM 呼び出しは agent_orchestrator の台帳 `var/ledger.jsonl` に記録される。
  集計は `python -m orchestrator.cli report`（削減額・課金区分別）。

### 計測（フェーズ1 / 1b）

`local_agent.py`（Ollama）と `haiku_agent.py`（CLI）の LLM 呼び出しは、
`orch_meter`（agent_orchestrator の安全 import シム）経由で共有台帳に
トークン数・所要時間・コストを記録する。import・記録に失敗しても本処理は継続する。

---

## 手動実行・操作コマンド

```bash
# Ollama 版（09:00 相当）
bash ~/projects/econ_digest/scripts/run_econ_ollama.sh

# Haiku 版（13:00 相当）: 事前収集(orchestrator) → Haiku記事執筆 → 比較ページ自動生成
bash ~/projects/econ_digest/scripts/run_econ_haiku.sh

# 事前収集パイプラインだけ単体実行（デバッグ用）
PYTHONPATH=~/projects/agent_orchestrator /opt/anaconda3/bin/python3 \
  -m orchestrator.cli run econ_prefetch \
  -p out_file=~/projects/econ_digest/var/prefetch_test.txt -p length=220

# 比較ページのみ手動生成（両記事が揃っている場合）
python3 ~/projects/econ_digest/scripts/generate_compare.py \
  --week-file 0704 --week-label "6/28〜7/4" --year 2026

# launchd 手動起動
launchctl start com.user.econ_digest_ollama
launchctl start com.user.econ_digest_haiku

# launchd 登録（初回・再登録）
launchctl load ~/projects/econ_digest/scripts/com.user.econ_digest_ollama.plist
launchctl load ~/projects/econ_digest/scripts/com.user.econ_digest_haiku.plist

# ログ確認
tail -f ~/projects/econ_digest/econ_digest.log        # Ollama
tail -f ~/projects/econ_digest/econ_digest_haiku.log  # Haiku
```

---

## 収集対象トピック

| カテゴリ | 内容 |
|---|---|
| 📈 マーケット動向 | 日経平均・TOPIX・ドル円・米国市場・金利の週次動向 |
| 🏦 金融政策 | 日銀・FRB・ECBの金融政策・政策金利・量的緩和 |
| 📊 経済指標 | GDP・CPI・雇用統計・貿易統計・機械受注等の主要統計 |
| 🏢 企業動向 | 主要企業の決算・業績修正・M&A・設備投資 |
| 🇯🇵 国内経済・政策 | 財務省・内閣府・経産省の政策・産業動向 |
| 🌐 海外経済 | 米国・中国・欧州の経済指標・政策・地政学リスク |

---

## 公開サイト リンク一覧

| | リンク |
|---|---|
| 🌐 公開サイト（GitHub Pages） | https://masauehr.github.io/econ_digest/ |
| 📰 Ollama 週次まとめ | https://masauehr.github.io/econ_digest/articles/weekly/ |
| ⚡ Haiku 週次まとめ | https://masauehr.github.io/econ_digest/articles/haiku_weekly/ |
| 🔬 モデル比較 | https://masauehr.github.io/econ_digest/articles/compare/ |
| 📅 月次まとめ一覧 | https://masauehr.github.io/econ_digest/articles/monthly/ |
| ⚙️ 収集・生成仕様 | [SPEC.md](./SPEC.md) |
