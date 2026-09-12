#!/bin/bash
# HaloStream: wartet auf echte GLM-Vollständigkeit (62/62 finale Shards + hf-Exit),
# feuert dann scripts/first_run.sh (Phase B+C: Sanity → Remap → Doctor → Plan →
# Vulkan-Run mit CPU-Fallback → Bench). first_run.sh loggt selbst nach
# spike/vulkan_glm53_run.log.
set -u
GLM_DIR=/home/sascha/models/colibri_store/glm53_flash
LOG=/home/sascha/halostream/spike/vulkan_glm53_run.log

echo "[$(date '+%H:%M:%S')] auto_first_run: warte auf 62/62 finale Shards" >> "$LOG"
while true; do
  shards=$(ls "$GLM_DIR"/model-*-of-00062.safetensors 2>/dev/null | wc -l)
  if [ "$shards" -ge 62 ]; then
    # hf-Schlussverifikation abwarten (max 10 min), dann feuern
    waited=0
    while systemctl --user is-active --quiet colibri-glm53-dl && [ "$waited" -lt 40 ]; do
      sleep 15; waited=$((waited+1))
    done
    break
  fi
  sleep 45
done
echo "[$(date '+%H:%M:%S')] auto_first_run: GLM komplett — starte first_run.sh" >> "$LOG"
exec /bin/bash /home/sascha/halostream/scripts/first_run.sh