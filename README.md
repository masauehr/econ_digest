# econ_digest — 経済週次ダイジェスト

> 詳しい運用マニュアルは [econ-digest.md](./econ-digest.md) を参照。

## クイックリンク

| | リンク |
|---|---|
| 🌐 公開サイト（GitHub Pages） | https://masauehr.github.io/econ_digest/ |
| 📰 Ollama週次まとめ | https://masauehr.github.io/econ_digest/articles/weekly/ |
| ⚡ Haiku週次まとめ | https://masauehr.github.io/econ_digest/articles/haiku_weekly/ |
| 🔬 モデル比較 | https://masauehr.github.io/econ_digest/articles/compare/ |
| 📅 月次まとめ一覧 | https://masauehr.github.io/econ_digest/articles/monthly/ |
| ⚙️ 収集・生成仕様 | [SPEC.md](./SPEC.md) |

---

## 概要

経済・マーケット・財政に関する最新情報を、
週次・月次で自動収集・要約してGitHubで公開するプロジェクト。

ローカルLLM（Ollama / qwen）と Claude Haiku の2モデルで同じ週を記事化し、
Claude Sonnet が評価した比較ページを自動生成する。

## プロジェクト構成

```
econ_digest/
├── README.md                              # このファイル（最新記事一覧）
├── SPEC.md                                # 情報収集・記事生成の仕様
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

## 最新記事

<!-- 自動更新される記事一覧 -->

### 週次まとめ（Ollama / qwen3.6:35b-mlx）

- [6/22〜6/29](./articles/weekly/2026-0629.md)
<!-- articles/weekly/ のファイルへのリンクがここに追加される -->

### Haiku週次まとめ（Claude Haiku）

- [6/22〜6/29](./articles/haiku_weekly/2026-0629.md)
<!-- articles/haiku_weekly/ のファイルへのリンクがここに追加される -->

### Haiku月次まとめ（Claude Haiku）

<!-- articles/haiku_monthly/ のファイルへのリンクがここに追加される -->

### モデル比較（Ollama vs Haiku）

<!-- articles/compare/ のファイルへのリンクがここに追加される -->

### 月次まとめ（Ollama）

- [2026年7月](./articles/monthly/2026-07.md)
<!-- articles/monthly/ のファイルへのリンクがここに追加される -->

### トピックス（臨時・深掘りレポート）

週次・月次とは別に、特定テーマを深掘りする単発レポート。

<!-- articles/topics/ のファイルへのリンクがここに追加される -->

---

## 自動実行システム

macOS の launchd が `scripts/run_econ_ollama.sh` を呼び出し、
**Ollama のローカルLLM（tool calling）** が情報収集から記事生成・git push までを自動実行する。

### スケジュール

| タイミング | 内容 |
|---|---|
| 毎週金曜 09:00 JST | Ollama（qwen3.6:35b-mlx）が週次記事を自動生成・git push |
| 毎月第1金曜 09:00 JST | 上記に加えて月次まとめも生成 |
| 毎週金曜 13:00 JST | Claude Haiku が同じ週の記事を別ファイルに生成 → 比較ページを自動作成 → Claude Sonnet が両記事を評価 |

### 使用モデル

| 実行 | モデル | 種別 |
|---|---|---|
| 09:00 | `qwen3.6:35b-mlx` | Ollama ローカルLLM（デフォルト） |
| 13:00 | `claude-haiku-4-5-20251001` | Anthropic API（Claude Haiku） |
| 13:00（比較評価） | `claude-sonnet-4-6` | Anthropic API（Claude Sonnet） |

### 手動実行

```bash
# Ollama 版（09:00 相当）を今すぐ実行
bash ~/projects/econ_digest/scripts/run_econ_ollama.sh

# Haiku 版（13:00 相当）を今すぐ実行
bash ~/projects/econ_digest/scripts/run_econ_haiku.sh

# 比較ページのみ手動生成（両記事が揃っている場合）
python3 ~/projects/econ_digest/scripts/generate_compare.py \
  --week-file 0704 --week-label "6/28〜7/4" --year 2026

# launchd 手動起動
launchctl start com.user.econ_digest_ollama  # Ollama 版
launchctl start com.user.econ_digest_haiku   # Haiku 版

# ログ確認
tail -f ~/projects/econ_digest/econ_digest.log        # Ollama ログ
tail -f ~/projects/econ_digest/econ_digest_haiku.log  # Haiku ログ
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
