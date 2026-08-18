#!/usr/bin/env bash
# Operational GPU health sampling for the whole flight; exits when the
# sentinel appears or after a 3 h hard cap. Same CSV shape as the P-ATTR flight.
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/ppromptfly/env.sh
OUT="$RUN_DIR/gpu-health.log"
END=$(( $(date +%s) + 10800 ))
echo "utc,clocks_sm_mhz,clocks_max_mhz,temp_c,power_w,util_pct,mem_used_mib,pstate,throttle_reasons" >> "$OUT"
while [ ! -f "$RUN_DIR/STOP-SAMPLER" ] && [ "$(date +%s)" -lt "$END" ]; do
  echo "$(date -u +%H:%M:%SZ),$(nvidia-smi --query-gpu=clocks.sm,clocks.max.sm,temperature.gpu,power.draw,utilization.gpu,memory.used,pstate,clocks_throttle_reasons.active --format=csv,noheader | tr -d ' ')" >> "$OUT"
  sleep 30
done
echo "sampler stopped $(date -u +%H:%M:%SZ)" >> "$OUT"
