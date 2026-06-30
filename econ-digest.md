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
| 13:00 | `claude-haiku-4-5-20251001` | Anthropic API（Claude Haiku） |
| 13:00（比較評価） | `claude-sonnet-4-6` | Anthropic API（Claude Sonnet） |

モデルは環境変数 `ECON_OLLAMA_MODEL` で上書き可能（Ollama 版のみ）。

---

## 手動実行・操作コマンド

```bash
# Ollama 版（09:00 相当）
bash ~/projects/econ_digest/scripts/run_econ_ollama.sh

# Haiku 版（13:00 相当）+ 比較ページ自動生成
bash ~/projects/econ_digest/scripts/run_econ_haiku.sh

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
