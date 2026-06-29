#!/bin/bash
# run_econ_ollama.sh — Ollama ローカルLLM による経済週次まとめ 自動実行スクリプト
# launchd から毎週金曜 09:00 に呼び出される。

set -euo pipefail

# --- 設定 ---
PROJECT_DIR="/Users/masahiro/projects/econ_digest"
LOG_FILE="${PROJECT_DIR}/econ_digest.log"
PYTHON_BIN="/opt/anaconda3/bin/python3"
OLLAMA_MODEL="${ECON_OLLAMA_MODEL:-qwen3.6:35b-mlx}"
TODAY=$(TZ=Asia/Tokyo date +%Y-%m-%d)
DAY_OF_MONTH=$(TZ=Asia/Tokyo date +%d)
YEAR=$(TZ=Asia/Tokyo date +%Y)
MONTH=$(TZ=Asia/Tokyo date +%m)
WEEK_FILE_MMDD=$(TZ=Asia/Tokyo date +%m%d)
WEEK_END=$(TZ=Asia/Tokyo date +%-m/%-d)
WEEK_START=$(TZ=Asia/Tokyo date -v-7d +%-m/%-d)
WEEK_LABEL="${WEEK_START}〜${WEEK_END}"
OLLAMA_WEEKLY_FILE="${PROJECT_DIR}/articles/weekly/${YEAR}-${WEEK_FILE_MMDD}.md"
OLLAMA_MONTHLY_FILE="${PROJECT_DIR}/articles/monthly/${YEAR}-${MONTH}.md"

# --- ログ関数 ---
log() {
  echo "[$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

# --- 開始 ---
log "=== econ_digest Ollama 起動チェック ==="
log "今日: ${TODAY} / 実行日ファイル: ${YEAR}-${WEEK_FILE_MMDD} / 対象期間: ${WEEK_LABEL}"

cd "${PROJECT_DIR}"

# --- 実行済みチェック ---
if [ -f "${OLLAMA_WEEKLY_FILE}" ]; then
  log "実行日分 Ollama 記事（${YEAR}-${WEEK_FILE_MMDD}）は実行済み。スキップします。"
  exit 0
fi

# --- Ollama 疎通確認 ---
if ! curl -sf "http://localhost:11434/api/tags" > /dev/null 2>&1; then
  log "ERROR: Ollama が起動していません。Ollama を起動してから再実行してください。"
  exit 1
fi

log "=== econ_digest Ollama 自動実行開始 ==="

# --- モード判定 ---
if [ "${DAY_OF_MONTH}" -le 7 ]; then
  MODE="monthly"
  log "モード: 月次（月初週）"
else
  MODE="weekly"
  log "モード: 週次"
fi

# --- エージェント実行関数（リトライ付き）---
run_ollama_agent() {
  local _mode="$1"
  local _max_retry=2
  local _retry=0
  local _success=false

  while [ ${_retry} -lt ${_max_retry} ]; do
    _retry=$((_retry + 1))
    log "Ollamaエージェントを起動します... mode=${_mode} model=${OLLAMA_MODEL} (試行 ${_retry}/${_max_retry})"

    if "${PYTHON_BIN}" "${PROJECT_DIR}/scripts/local_agent.py" \
        --mode "${_mode}" \
        --week-file "${WEEK_FILE_MMDD}" \
        --week-label "${WEEK_LABEL}" \
        --year "${YEAR}" \
        --month "${MONTH}" \
        --model "${OLLAMA_MODEL}" \
        2>&1 | tee -a "${LOG_FILE}"; then
      _success=true
      break
    else
      EXIT_CODE=$?
      log "Ollamaエージェントが終了コード ${EXIT_CODE} で失敗しました。"
      if [ ${_retry} -lt ${_max_retry} ]; then
        log "30秒後にリトライします..."
        sleep 30
      fi
    fi
  done

  if [ "${_success}" = false ]; then
    log "ERROR: ${_max_retry}回試行しましたがすべて失敗しました（mode=${_mode}）。手動確認が必要です。"
    return 1
  fi
  return 0
}

# --- 週次記事生成 ---
log "モード: weekly"
run_ollama_agent "weekly" || exit 1
log "=== Ollama 週次記事生成完了 ==="

# --- 月次記事生成（第1週のみ）---
if [ "${MODE}" = "monthly" ]; then
  if [ -f "${OLLAMA_MONTHLY_FILE}" ]; then
    log "Ollama 月次記事（${YEAR}-${MONTH}）は実行済み。スキップします。"
  else
    log "=== Ollama 月次記事生成開始 ==="
    run_ollama_agent "monthly" || log "WARN: 月次記事生成に失敗しました（手動で実行してください）"
    log "=== Ollama 月次記事生成完了 ==="
  fi
fi

log "=== econ_digest Ollama 自動実行完了 ==="
