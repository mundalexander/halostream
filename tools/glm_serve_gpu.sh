#!/bin/bash
# HaloStream: GLM-5.3-Flash (colibri) — GPU-Vulkan-Server auf Port 18790
# Nutzung: ./glm_serve_gpu.sh start|stop|status

PORT=18790
MODEL=/home/sascha/models/colibri_store/glm53_i4
LOG=/tmp/glm_gpu3.log

# GPU-Budget-Limit (GLM53_VK_GB, dezimale GB; leer = unbegrenzt) und optional
# Experten auf der GPU. Beispiel-Test: VKGB=8 VKEXPERTS=1 ./glm_serve_gpu.sh start
VKGB="${VKGB:-}"
VKEXPERTS="${VKEXPERTS:-0}"
# --ram ist der Gesamtrahmen: coli leitet daraus den CPU-Experten-Cache ab
# (GLM53_EXPERT_GB = ram-8). Bei hohem GPU-Budget hochsetzen, sonst bucht man
# denselben RAM doppelt. EXPGB erzwingt einen eigenen Cache-Wert.
RAMGB="${RAMGB:-20}"
EXPGB="${EXPGB:-}"
[ -n "$EXPGB" ] && export GLM53_EXPERT_GB="$EXPGB"

case "$1" in
  stop)
    PID=$(pgrep -f "coli serve.*$PORT" | head -1)
    EPID=$(pgrep -f "colibri/c/glm53" | head -1)
    [ -n "$PID" ] && kill "$PID" 2>/dev/null
    [ -n "$EPID" ] && kill "$EPID" 2>/dev/null
    sleep 3
    pkill -9 -f "colibri/c/glm53" 2>/dev/null
    echo "Server gestoppt"
    ;;
  status)
    ss -tlnp | grep -q ":$PORT" && echo "LÄUFT auf Port $PORT" || echo "GESTOPPT"
    EPID=$(pgrep -f "colibri/c/glm53" | head -1)
    [ -n "$EPID" ] && ps -p "$EPID" -o pid,%cpu,%mem,rss,etime --no-headers
    ;;
  start|*)
    ss -tlnp | grep -q ":$PORT" && { echo "Läuft bereits auf $PORT"; exit 0; }
    COLI_VULKAN=1 \
    COLI_VK_SHADERS=/home/sascha/colibri_shaders \
    COLI_NO_OMP_TUNE=1 \
    GLM53_VK_GB="${VKGB}" \
    GLM53_VK_EXPERTS="$([ "$VKEXPERTS" = 1 ] && echo 1 || echo 0)" \
    GLM53_VK_BATCH="$([ "$VKEXPERTS" = 1 ] && echo 1 || echo 0)" \
    nohup /home/sascha/.venvs/colibri/bin/coli serve \
      --model "$MODEL" \
      --port $PORT --ram "$RAMGB" --auto-tier \
      > "$LOG" 2>&1 &
    echo "Gestartet: PID $! — Log: $LOG"
    ;;
esac