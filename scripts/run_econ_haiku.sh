#!/bin/bash
# run_econ_haiku.sh — Claude Haiku による経済週次まとめ 自動実行スクリプト
# launchd から毎週金曜 13:00 に呼び出される。
# Ollama版（09:00）と同じ週の記事を Haiku で別ファイルに生成し、
# 両者の比較ページを自動作成する。

set -euo pipefail

# --- 設定 ---
PROJECT_DIR="/Users/masahiro/projects/econ_digest"
LOG_FILE="${PROJECT_DIR}/econ_digest_haiku.log"
PYTHON_BIN="/opt/anaconda3/bin/python3"
HAIKU_MODEL="${HAIKU_MODEL:-claude-haiku-4-5-20251001}"
TODAY=$(TZ=Asia/Tokyo date +%Y-%m-%d)
DAY_OF_MONTH=$(TZ=Asia/Tokyo date +%d)
YEAR=$(TZ=Asia/Tokyo date +%Y)
MONTH=$(TZ=Asia/Tokyo date +%m)
WEEK_FILE_MMDD=$(TZ=Asia/Tokyo date +%m%d)
WEEK_END=$(TZ=Asia/Tokyo date +%-m/%-d)
WEEK_START=$(TZ=Asia/Tokyo date -v-7d +%-m/%-d)
WEEK_LABEL="${WEEK_START}〜${WEEK_END}"
HAIKU_WEEKLY_FILE="${PROJECT_DIR}/articles/haiku_weekly/${YEAR}-${WEEK_FILE_MMDD}.md"
HAIKU_MONTHLY_FILE="${PROJECT_DIR}/articles/haiku_monthly/${YEAR}-${MONTH}.md"

# --- ログ関数 ---
log() {
  echo "[$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

# --- ANTHROPIC_API_KEY の読み込み ---
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  if [ -f "${HOME}/.anthropic_env" ]; then
    # shellcheck disable=SC1090
    source "${HOME}/.anthropic_env"
    log "ANTHROPIC_API_KEY を ~/.anthropic_env から読み込みました"
  fi
fi

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  log "ERROR: ANTHROPIC_API_KEY が設定されていません"
  log "  ~/.anthropic_env に ANTHROPIC_API_KEY=sk-ant-... を記載してください"
  exit 1
fi
export ANTHROPIC_API_KEY

# --- 開始 ---
log "=== econ_digest Haiku 起動チェック ==="
log "今日: ${TODAY} / 実行日ファイル: ${YEAR}-${WEEK_FILE_MMDD} / 対象期間: ${WEEK_LABEL}"

cd "${PROJECT_DIR}"

# --- 実行済みチェック ---
if [ -f "${HAIKU_WEEKLY_FILE}" ]; then
  log "実行日分 Haiku 記事（${YEAR}-${WEEK_FILE_MMDD}）は実行済み。スキップします。"
  COMPARE_FILE="${PROJECT_DIR}/articles/compare/${YEAR}-${WEEK_FILE_MMDD}.md"
  if [ ! -f "${COMPARE_FILE}" ]; then
    log "比較ページが未生成のため生成を試みます..."
    "${PYTHON_BIN}" "${PROJECT_DIR}/scripts/generate_compare.py" \
      --week-file "${WEEK_FILE_MMDD}" \
      --week-label "${WEEK_LABEL}" \
      --year "${YEAR}" \
      2>&1 | tee -a "${LOG_FILE}" || true
  fi
  exit 0
fi

log "=== econ_digest Haiku 自動実行開始 ==="

# --- モード判定 ---
if [ "${DAY_OF_MONTH}" -le 7 ]; then
  MODE="monthly"
  log "モード: 月次（月初週）"
else
  MODE="weekly"
  log "モード: 週次"
fi

# --- 共通: エージェント実行関数（リトライ付き）---
run_haiku_agent() {
  local _mode="$1"
  local _max_retry=2
  local _retry=0
  local _success=false

  while [ ${_retry} -lt ${_max_retry} ]; do
    _retry=$((_retry + 1))
    log "Haikuエージェントを起動します... mode=${_mode} model=${HAIKU_MODEL} (試行 ${_retry}/${_max_retry})"

    if "${PYTHON_BIN}" "${PROJECT_DIR}/scripts/haiku_agent.py" \
        --mode "${_mode}" \
        --week-file "${WEEK_FILE_MMDD}" \
        --week-label "${WEEK_LABEL}" \
        --year "${YEAR}" \
        --month "${MONTH}" \
        --model "${HAIKU_MODEL}" \
        2>&1 | tee -a "${LOG_FILE}"; then
      _success=true
      break
    else
      EXIT_CODE=$?
      log "Haikuエージェントが終了コード ${EXIT_CODE} で失敗しました。"
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

# --- 週次記事生成（常に実行）---
log "モード: weekly"
run_haiku_agent "weekly" || exit 1
log "=== Haiku 週次記事生成完了 ==="

# --- 月次記事生成（第1週のみ）---
if [ "${MODE}" = "monthly" ]; then
  if [ -f "${HAIKU_MONTHLY_FILE}" ]; then
    log "Haiku 月次記事（${YEAR}-${MONTH}）は実行済み。スキップします。"
  else
    log "=== Haiku 月次記事生成開始 ==="
    run_haiku_agent "monthly" || log "WARN: 月次記事生成に失敗しました（手動で実行してください）"
    log "=== Haiku 月次記事生成完了 ==="
  fi
fi

# --- 週次比較ページ生成 ---
OLLAMA_FILE="${PROJECT_DIR}/articles/weekly/${YEAR}-${WEEK_FILE_MMDD}.md"
COMPARE_FILE="${PROJECT_DIR}/articles/compare/${YEAR}-${WEEK_FILE_MMDD}.md"

if [ -f "${OLLAMA_FILE}" ] && [ ! -f "${COMPARE_FILE}" ]; then
  log "=== 週次比較ページ生成開始 ==="
  "${PYTHON_BIN}" "${PROJECT_DIR}/scripts/generate_compare.py" \
    --week-file "${WEEK_FILE_MMDD}" \
    --week-label "${WEEK_LABEL}" \
    --year "${YEAR}" \
    2>&1 | tee -a "${LOG_FILE}" || log "WARN: 比較ページ生成に失敗しました"
  log "=== 週次比較ページ生成完了 ==="
elif [ ! -f "${OLLAMA_FILE}" ]; then
  log "WARN: Ollama版記事（${OLLAMA_FILE}）が存在しません。比較ページはスキップします。"
  log "      Ollama版が生成された後、以下のコマンドで手動生成できます:"
  log "      python3 ${PROJECT_DIR}/scripts/generate_compare.py --week-file ${WEEK_FILE_MMDD} --week-label '${WEEK_LABEL}' --year ${YEAR}"
fi

log "=== econ_digest Haiku 自動実行完了 ==="
