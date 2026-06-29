# econ_digest — 経済週次ダイジェスト

毎週金曜日に経済・マーケット情報を自動収集・要約し、GitHub Pages で公開するプロジェクト。

ローカルLLM（Ollama）と Claude Haiku の2モデルが同じ週の記事を生成し、Claude Sonnet が比較評価を行う。

---

## 公開サイト

| | リンク |
|---|---|
| 🔬 モデル比較（トップ） | https://masauehr.github.io/econ_digest/ |
| 🖥️ Ollama 週次まとめ | https://masauehr.github.io/econ_digest/articles/weekly/ |
| ⚡ Haiku 週次まとめ | https://masauehr.github.io/econ_digest/articles/haiku_weekly/ |
| 📅 月次まとめ | https://masauehr.github.io/econ_digest/articles/monthly/ |

---

## 自動実行スケジュール

| 時刻（毎週金曜） | 処理 |
|---|---|
| 09:00 JST | Ollama（qwen3.6:35b-mlx）が週次記事を生成・push |
| 13:00 JST | Claude Haiku が同じ週の記事を生成 → Claude Sonnet が比較評価ページを作成・push |
| 第1金曜のみ | 09:00 に月次まとめも追加生成 |

launchd（macOS）で自動起動。手動実行は下記参照。

---

## 最新記事

### 週次まとめ（Ollama / qwen3.6:35b-mlx）

- [6/22〜6/29](./articles/weekly/2026-0629.md)

### 週次まとめ（Claude Haiku）

- [6/22〜6/29](./articles/haiku_weekly/2026-0629.md)

### モデル比較（Ollama vs Haiku + Sonnet評価）

- [6/22〜6/29](./articles/compare/2026-0629.md)

### 月次まとめ（Ollama）

- [2026年7月](./articles/monthly/2026-07.md)

---

## 手動実行

```bash
# Ollama 版
bash ~/projects/econ_digest/scripts/run_econ_ollama.sh

# Haiku 版（完了後に比較ページも自動生成）
bash ~/projects/econ_digest/scripts/run_econ_haiku.sh

# 比較ページのみ（両記事が揃っている場合）
python3 ~/projects/econ_digest/scripts/generate_compare.py \
  --week-file 0704 --week-label "6/28〜7/4" --year 2026

# ログ確認
tail -f ~/projects/econ_digest/econ_digest.log        # Ollama
tail -f ~/projects/econ_digest/econ_digest_haiku.log  # Haiku
```

---

## 収集トピック

日経平均・ドル円・日銀/FRB金融政策・GDP/CPI・企業決算・海外経済（米中欧）
