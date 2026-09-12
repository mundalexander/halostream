#!/bin/bash
# HaloStream Phase B+C: Erster Start GLM-5.3-Flash
# Pipeline: Sanity → RAM-Check → Remap (Skip wenn Backup existiert) → Doctor → Plan → Baseline-Run (Vulkan→CPU-Fallback) → Bench
#
# v2 (2026-09-12 ~21:50): --model NACH dem Subcommand. Der Subparser-argparse von
# coli überschreibt sonst den Wert des Hauptparsers mit seinem Default (None) →
# "no model directory given" (0.0s, RC=1 — siehe Abendreport 21:21).
# Zusätzlich: Remap-Skip wenn .pre_remap-Backup existiert (Remap lief bereits).
# Log: spike/vulkan_glm53_run.log
set -u

MODEL_DIR=/home/sascha/models/colibri_store/glm53_flash
LOG=/home/sascha/halostream/spike/vulkan_glm53_run.log
COLI=/home/sascha/.venvs/colibri/bin/coli
REMAP=/home/sascha/halostream/spike/remap_glm53.py
BACKUP=/home/sascha/models/colibri_store/glm53_flash/model.safetensors.index.json.pre_remap
PROMPT="Erkläre in genau drei Sätzen, was NVMe-Streaming für große Sprachmodelle bedeutet."

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "===== HaloStream Phase B+C v2: erster Start ====="

# --- 1. Sanity ---
sz=$(du -sk "$MODEL_DIR" 2>/dev/null | cut -f1)
shards=$(ls "$MODEL_DIR"/model-*-of-00062.safetensors 2>/dev/null | wc -l)
log "Sanity: $shards/62 Shards, $(awk -v s="$sz" 'BEGIN{printf "%.0f", s/1048576}') GB"
if [ "$shards" -ne 62 ]; then
  log "ABBRUCH: Download unvollständig ($shards/62 Shards)"
  exit 1
fi

# --- 2. RAM-Check ---
ram_avail=$(free -g | awk '/^Speicher|^Mem:/{print $7}')
log "RAM verfügbar: ${ram_avail} GiB"

# --- 3. Remap (idempotent: Skip wenn Backup existiert) ---
if [ -f "$BACKUP" ]; then
  log "=== Phase B1: Remap bereits erledigt (.pre_remap vorhanden) — überspringe ==="
else
  log "=== Phase B1: Remap ==="
  python3 "$REMAP" 2>&1 | tee -a "$LOG"
  [ "${PIPESTATUS[0]}" -ne 0 ] && { log "ABBRUCH: Remap fehlgeschlagen"; exit 1; }
fi

# --- 4. Doctor (Validierung) — --model NACH dem Subcommand ---
log "=== Phase B2: coli doctor ==="
"$COLI" doctor --model "$MODEL_DIR" --json --deep 2>&1 | tee -a "$LOG"

# --- 5. Load-Plan ---
log "=== Phase B3: coli plan ==="
"$COLI" plan --model "$MODEL_DIR" --json 2>&1 | tee -a "$LOG"

# --- 6. Baseline-Run: Vulkan zuerst, sonst CPU ---
log "=== Phase C1: Baseline-Run (Vulkan, gfx1151) ==="
t0=$(date +%s.%N)
"$COLI" run --model "$MODEL_DIR" --gpu vulkan "$PROMPT" 2>&1 | tee -a "$LOG"
rc=${PIPESTATUS[0]}
t1=$(date +%s.%N)
log "Vulkan-Run RC=$rc · Dauer: $(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.1fs", b-a}')"
if [ "$rc" -ne 0 ]; then
  log "=== Phase C2: Fallback CPU-Run ==="
  t0=$(date +%s.%N)
  "$COLI" run --model "$MODEL_DIR" "$PROMPT" 2>&1 | tee -a "$LOG"
  rc=${PIPESTATUS[0]}
  t1=$(date +%s.%N)
  log "CPU-Run RC=$rc · Dauer: $(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.1fs", b-a}')"
fi

# --- 7. Bench (nur wenn ein Run klappte) ---
if [ "$rc" -eq 0 ]; then
  log "=== Phase C3: coli bench ==="
  "$COLI" bench --model "$MODEL_DIR" 2>&1 | tail -30 | tee -a "$LOG"
fi

log "===== Phase B+C v2 Ende ====="
exit 0