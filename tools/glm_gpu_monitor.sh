#!/bin/bash
# HaloStream: Monitor fuer den GLM53-Vulkan-Budget-Test.
# Sampelt GPU-Auslastung, GTT-Belegung (das ist auf dem Strix Halo der
# eigentliche "VRAM"-Topf = System-RAM) und RAM-Freigabe in eine CSV.
# Nutzung: ./glm_gpu_monitor.sh [sekunden]   (Default 300)

SECS="${1:-300}"
OUT="/tmp/glm_gpu_monitor_$(date +%H%M%S).csv"
CARD=/sys/class/drm/card1/device

echo "zeit,sec,gpu_busy_prozent,gtt_used_GiB,ram_used_GB,ram_avail_GB,glm53_rss_GB" > "$OUT"
START=$(date +%s)
echo "Monitor -> $OUT (Laufzeit ${SECS}s, Strg-C bricht ab)"

while [ $(( $(date +%s) - START )) -lt "$SECS" ]; do
  NOW=$(date +%s)
  BUSY=$(cat "$CARD/gpu_busy_percent" 2>/dev/null || echo -1)
  GTT=$(awk '{printf "%.1f", $1/1073741824}' "$CARD/mem_info_gtt_used" 2>/dev/null || echo -1)
  read -r USED AVAIL < <(free -g | awk 'NR==2{print $3, $7}')
  RSS=$(pgrep -f 'colibri/c/glm53' -a >/dev/null 2>&1 && \
        ps -o rss= -C glm53 2>/dev/null | awk '{s+=$1} END{printf "%.1f", s/1048576}' || echo 0)
  [ -z "$RSS" ] && RSS=0
  echo "$(date +%H:%M:%S),$(( NOW - START )),$BUSY,$GTT,$USED,$AVAIL,$RSS" >> "$OUT"
  sleep 2
done

echo "== Auswertung $OUT =="
awk -F, 'NR>1 {n++; b+=$3; if ($3>mx) mx=$3; g+=$4; if ($4>gmx) gmx=$4}
         END {if (n) printf "Samples %d | GPU busy: Ø %.1f%% / max %d%% | GTT used: Ø %.1f / max %.1f GiB\n", n, b/n, mx, g/n, gmx}' "$OUT"
