#!/bin/bash
# HaloStream: wartet bis der GLM-5.3-Flash-Download (colibri-glm53-dl) KOMPLETT ist,
# laedt danach automatisch den Halogen-Checkpoint (Qwen3.8-Flash-Next, ~130 GB).
#
# Restart-tolerant (2026-09-12, nach Leitungsausfaellen umgebaut):
# - Kurze inactive-Fenster (systemd restart) uebersteht die Schleife.
# - Nach 3 aufeinanderfolgenden inactive-Minuten (Unit wirkt tot) startet
#   die Kette den GLM-Download selbst neu (hf resümiert via .incomplete).
set -u
GLM_DIR=/home/sascha/models/colibri_store/glm53_flash
HALOGEN_DIR=/home/sascha/models/halogen_store
LOG=/home/sascha/models/halogen_store/chain.log
inactive_streak=0

log() { echo "[$(date '+%H:%M:%S')] $*" >> "$LOG"; }

log "Kette aktiv: warte auf GLM-Vollstaendigkeit (>=300 GB)"

while true; do
  sz=$(du -sk "$GLM_DIR" 2>/dev/null | cut -f1)
  if [ "${sz:-0}" -ge 300000000 ]; then
    log "GLM komplett (${sz} KB) — starte Halogen-Checkpoint-Download"
    break
  fi
  if systemctl --user is-active --quiet colibri-glm53-dl; then
    inactive_streak=0
  else
    inactive_streak=$((inactive_streak + 1))
    log "GLM-Unit inactive (Streak $inactive_streak), Stand ${sz} KB"
    if [ "$inactive_streak" -ge 3 ]; then
      log "GLM-Unit wirkt tot — Restart-Versuch"
      systemctl --user restart colibri-glm53-dl 2>>"$LOG" || true
      inactive_streak=0
    fi
  fi
  sleep 60
done

mkdir -p "$HALOGEN_DIR"
exec /home/sascha/.local/bin/hf download peonist-ai/halogen-qwen3.8-flash-next --local-dir "$HALOGEN_DIR"