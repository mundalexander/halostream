#!/bin/bash
COLI=/home/sascha/.venvs/colibri/bin/coli
M=/home/sascha/models/colibri_store/glm53_i4
LOG=/home/sascha/halostream/spike/glm53_i4_run.log
echo "[$(date '+%F %T')] ===== Erster Run aus glm53_i4 (CPU-Pfad) =====" >> "$LOG"
start=$(date +%s)
timeout 1800 $COLI run --model "$M" PING >> "$LOG" 2>&1
rc=$?
echo "[$(date '+%F %T')] Run RC=$rc · Dauer: $(( $(date +%s)-start ))s" >> "$LOG"
