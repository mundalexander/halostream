#!/bin/bash
# HaloStream: GLM-5.3-Flash (colibri) — GPU-Vulkan-Server auf Port 18790
# Nutzung: ./glm_serve_gpu.sh start|stop|status

PORT=18790
MODEL=/home/sascha/models/colibri_store/glm53_i4
LOG=/tmp/glm_gpu3.log

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
    nohup /home/sascha/.venvs/colibri/bin/coli serve \
      --model "$MODEL" \
      --port $PORT --ram 68 --auto-tier \
      > "$LOG" 2>&1 &
    echo "Gestartet: PID $! — Log: $LOG"
    ;;
esac