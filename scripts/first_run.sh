#!/bin/bash
# HaloStream Phase B+C: Erster Start GLM-5.3-Flash
# Pipeline: Sanity → RAM-Check → Remap → Doctor → Plan → Baseline-Run (Vulkan→CPU-Fallback)
# Auslöser: Jarvis via Heartbeat, sobald colibri-glm53-dl durch ist.
# Log: spike/vulkan_glm53_run.log
set -u

MODEL_DIR=/home/sascha/models/colibri_store/glm53_flash
LOG=/home/sascha/halostream/spike/vulkan_glm53_run.log
COLI=/home/sascha/.venvs/colibri/bin/coli
REMAP=/home/sascha/halostream/spike/remap_glm53.py
PROMPT="Erkläre in genau drei Sätzen, was NVMe-Streaming für große Sprachmodelle bedeutet."

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "===== HaloStream Phase B+C: erster Start ====="

# --- 1. Sanity: Download vollständig? ---
sz=$(du -sk "$MODEL_DIR" 2>/dev/null | cut -f1)
shards=$(ls "$MODEL_DIR"/model-*-of-00062.safetensors 2>/dev/null | wc -l)
log "Sanity: $shards/62 Shards, $(awk -v s="$sz" 'BEGIN{printf "%.0f", s/1048576}') GB"
if [ "$shards" -ne 62 ]; then
  log "ABBRUCH: Download unvollständig ($shards/62 Shards)"
  exit 1
fi

# --- 2. RAM-Check ---
ram_avail=$(free -g | awk '/^Speicher|^Mem:/{print $7}')
log "RAM verfügbar: ${ram_avail} GiB (LM Studio sollte entladen sein)"
[ "$ram_avail" -lt 40 ] && log "WARNUNG: RAM knapp (<40 GiB) — Run könnte thrifteln"

# --- 3. Remap (Zero-Copy, Backup .pre_remap) ---
log "=== Phase B1: Remap ==="
python3 "$REMAP" 2>&1 | tee -a "$LOG"
[ "${PIPESTATUS[0]}" -ne 0 ] && { log "ABBRUCH: Remap fehlgeschlagen"; exit 1; }

# --- 4. Doctor (Validierung, JSON) ---
log "=== Phase B2: coli doctor ==="
"$COLI" --model "$MODEL_DIR" doctor --json --deep 2>&1 | tee -a "$LOG"

# --- 5. Load-Plan ---
log "=== Phase B3: coli plan ==="
"$COLI" --model "$MODEL_DIR" plan --json 2>&1 | tee -a "$LOG"

# --- 6. Baseline-Run: zuerst Vulkan, sonst CPU ---
log "=== Phase C1: Baseline-Run (Vulkan, gfx1151) ==="
t0=$(date +%s.%N)
"$COLI" --model "$MODEL_DIR" --gpu vulkan run "$PROMPT" 2>&1 | tee -a "$LOG"
rc=${PIPESTATUS[0]}
t1=$(date +%s.%N)
log "Vulkan-Run RC=$rc · Dauer: $(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.1fs", b-a}')"
if [ "$rc" -ne 0 ]; then
  log "=== Phase C2: Fallback CPU-Run ==="
  t0=$(date +%s.%N)
  "$COLI" --model "$MODEL_DIR" run "$PROMPT" 2>&1 | tee -a "$LOG"
  rc=${PIPESTATUS[0]}
  t1=$(date +%s.%N)
  log "CPU-Run RC=$rc · Dauer: $(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.1fs", b-a}')"
fi

# --- 7. Feinmessung (optional, erst wenn Run klappte) ---
if [ "$rc" -eq 0 ]; then
  log "=== Phase C3: coli bench (tok/s-Referenz) ==="
  "$COLI" --model "$MODEL_DIR" bench 2>&1 | tail -30 | tee -a "$LOG"
fi

log "===== Phase B+C Ende — Ergebnisse ins Repo committen ====="
exit 0