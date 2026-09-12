#!/bin/bash
# HaloStream: wartet, bis der GLM-5.3-Flash-Download (colibri-glm53-dl) fertig ist,
# laedt danach automatisch den Halogen-Checkpoint (Qwen3.8-Flash-Next, ~130 GB).
set -u
GLM_DIR=/home/sascha/models/colibri_store/glm53_flash
HALOGEN_DIR=/home/sascha/models/halogen_store
while systemctl --user is-active --quiet colibri-glm53-dl; do sleep 60; done
sz=$(du -sk "$GLM_DIR" | cut -f1)
if [ "$sz" -lt 300000000 ]; then
  echo "[$(date)] GLM-Download unvollständig (${sz} KB) — Kette abgebrochen"
  exit 1
fi
echo "[$(date)] GLM fertig (${sz} KB) — starte Halogen-Checkpoint-Download"
exec /home/sascha/.local/bin/hf download peonist-ai/halogen-qwen3.8-flash-next --local-dir "$HALOGEN_DIR"
