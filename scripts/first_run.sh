#!/bin/bash
# HaloStream Phase B+C: Erster Start GLM-5.3-Flash
# Pipeline: Model-Auswahl → Sanity → RAM-Check → Doctor → Plan → Baseline-Run (Vulkan→CPU-Fallback) → Bench
#
# v2 (2026-09-12 ~21:50): --model NACH dem Subcommand. Der Subparser-argparse von
# coli überschreibt sonst den Wert des Hauptparsers mit seinem Default (None) →
# "no model directory given" (0.0s, RC=1 — siehe Abendreport 21:21).
# Zusätzlich: Remap-Skip wenn .pre_remap-Backup existiert (Remap lief bereits).
# Log: spike/vulkan_glm53_run.log
set -u

RAW_MODEL_DIR=/home/sascha/models/colibri_store/glm53_flash
CONVERTED_MODEL_DIR=/home/sascha/models/colibri_store/glm53_i4
MODEL_DIR="$CONVERTED_MODEL_DIR"
LOG=/home/sascha/halostream/spike/vulkan_glm53_run.log
COLI=/home/sascha/.venvs/colibri/bin/coli
CONVERTER=/home/sascha/colibri/c/tools/convert_glm53.py
PROMPT="Erkläre in genau drei Sätzen, was NVMe-Streaming für große Sprachmodelle bedeutet."
NGEN=${NGEN:-128}
CTX=${CTX:-4096}
VK_EXPERTS=${GLM53_VK_EXPERTS:-0}
VK_BATCH=${GLM53_VK_BATCH:-0}
PREFETCH=${GLM53_PREFETCH:-0}

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "===== HaloStream Phase B+C v2: erster Start ====="

# --- 0. Model selection and shape sanity ---
if [ ! -d "$MODEL_DIR" ]; then
  if [ ! -d "$RAW_MODEL_DIR" ]; then
    log "ABBRUCH: weder konvertiertes noch rohes Modell gefunden."
    log "Erwartet: $CONVERTED_MODEL_DIR oder $RAW_MODEL_DIR"
    exit 1
  fi
  log "ABBRUCH: konvertierter Container fehlt: $CONVERTED_MODEL_DIR"
  log "Roh-Checkpoint gefunden: $RAW_MODEL_DIR"
  log "Nächster Schritt: python3 $CONVERTER --outdir $CONVERTED_MODEL_DIR --min-free-gb 30"
  exit 1
fi
log "Modell: konvertierter Colibri-Container $MODEL_DIR"

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
log "Vulkan-Expert-Tier: GLM53_VK_EXPERTS=${VK_EXPERTS}"
log "Vulkan-Expert-Batching: GLM53_VK_BATCH=${VK_BATCH}"
log "Next-Layer-Prefetch: GLM53_PREFETCH=${PREFETCH}"

# --- 3. Doctor (Validierung) — --model NACH dem Subcommand ---
log "=== Phase B2: coli doctor ==="
"$COLI" doctor --model "$MODEL_DIR" --json --deep 2>&1 | tee -a "$LOG"

# --- 4. Load-Plan ---
log "=== Phase B3: coli plan ==="
"$COLI" plan --model "$MODEL_DIR" --json 2>&1 | tee -a "$LOG"

# --- 5. Baseline-Run: Vulkan optional, Engine fällt auf CPU zurück ---
log "=== Phase C1: Baseline-Run (Vulkan, gfx1151) ==="
t0=$(date +%s.%N)
COLI_VULKAN=1 COLI_VK_DENSE=1 COLI_VK_ATTN=1 GLM53_VK_EXPERTS="$VK_EXPERTS" GLM53_VK_BATCH="$VK_BATCH" GLM53_PREFETCH="$PREFETCH" \
  "$COLI" run --model "$MODEL_DIR" --ctx "$CTX" --ngen "$NGEN" "$PROMPT" 2>&1 | tee -a "$LOG"
rc=${PIPESTATUS[0]}
t1=$(date +%s.%N)
log "Vulkan-Run RC=$rc · Dauer: $(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.1fs", b-a}')"
if [ "$rc" -ne 0 ]; then
  log "=== Phase C2: Fallback CPU-Run ==="
  t0=$(date +%s.%N)
  "$COLI" run --model "$MODEL_DIR" --ctx "$CTX" --ngen "$NGEN" "$PROMPT" 2>&1 | tee -a "$LOG"
  rc=${PIPESTATUS[0]}
  t1=$(date +%s.%N)
  log "CPU-Run RC=$rc · Dauer: $(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.1fs", b-a}')"
fi

# --- 6. Bench (nur wenn ein Run klappte) ---
if [ "$rc" -eq 0 ]; then
  log "=== Phase C3: coli bench ==="
  "$COLI" bench --model "$MODEL_DIR" 2>&1 | tail -30 | tee -a "$LOG"
fi

log "===== Phase B+C v2 Ende ====="
exit 0