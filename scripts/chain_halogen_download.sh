#!/bin/bash
# HaloStream: wartet bis der GLM-5.3-Flash-Download WAHRSCHEINLICH komplett ist,
# laedt danach automatisch den Halogen-Checkpoint (Qwen3.8-Flash-Next, ~130 GB).
#
# v3 (2026-09-12 20:35): Fertigkeits-Check auf 62/62 FINALE Shards umgestellt.
# Der alte 300-GB-Verzeichnis-Schwellwert war fehlerhaft — du zählt .incomplete-
# Dateien mit, die Kette feuerte deshalb um 19:26 zu früh (303 GB erreicht,
# während Shards noch liefen) und hat GLM die Leitung geteilt.
set -u
GLM_DIR=/home/sascha/models/colibri_store/glm53_flash
HALOGEN_DIR=/home/sascha/models/halogen_store
LOG=/home/sascha/models/halogen_store/chain.log
inactive_streak=0

log() { echo "[$(date '+%H:%M:%S')] $*" >> "$LOG"; }

log "Kette v3 aktiv: warte auf 62/62 finale GLM-Shards"

while true; do
  shards=$(ls "$GLM_DIR"/model-*-of-00062.safetensors 2>/dev/null | wc -l)
  if [ "$shards" -ge 62 ]; then
    log "62/62 Shards da — warte auf sauberen hf-Exit (max 5 min)"
    waited=0
    while systemctl --user is-active --quiet colibri-glm53-dl && [ "$waited" -lt 20 ]; do
      sleep 15; waited=$((waited+1))
    done
    break
  fi
  if systemctl --user is-active --quiet colibri-glm53-dl; then
    inactive_streak=0
  else
    inactive_streak=$((inactive_streak + 1))
    log "GLM-Unit inactive (Streak $inactive_streak), $shards/62 Shards"
    if [ "$inactive_streak" -ge 3 ]; then
      log "GLM-Unit wirkt tot — Restart-Versuch"
      systemctl --user restart colibri-glm53-dl 2>>"$LOG" || true
      inactive_streak=0
    fi
  fi
  sleep 60
done

log "Starte Halogen-Checkpoint-Download (Resume ab ~17 GB)"
mkdir -p "$HALOGEN_DIR"
exec /home/sascha/.local/bin/hf download peonist-ai/halogen-qwen3.8-flash-next --local-dir "$HALOGEN_DIR"