#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/farm.env"

MODEL="${1:-$ACTIVE_MODEL}"
TS=$(date -Iseconds)
OUT="$ROOT/state/health-$TS.csv"
echo "timestamp,port,model,http,status,msg" > "$OUT"

for i in $(seq 1 "$INSTANCIAS"); do
  port=$((PUERTO_BASE+i-1))
  payload=$(printf '{"model":"%s","messages":[{"role":"user","content":"ping"}],"max_tokens":%s}' "$MODEL" "$MAX_TOKENS_TEST")
  body=$(curl -sS -m "$CURL_TIMEOUT" -w "\nHTTP:%{http_code}" -H 'Content-Type: application/json' \
    -d "$payload" \
    "http://127.0.0.1:$port/v1/chat/completions" || true)
  http=$(echo "$body" | sed -n 's/^HTTP://p' | tail -1)
  json=$(echo "$body" | sed '/^HTTP:/d')
  if echo "$json" | grep -q '"choices"'; then
    status="OK"; msg="ok"
  else
    status="FAIL"
    if echo "$json" | grep -q 'requires a subscription'; then msg="403_subscription";
    elif echo "$json" | grep -qi 'rate'; then msg="429_rate";
    elif echo "$json" | grep -qi 'unauthorized\|auth'; then msg="auth";
    else msg=$(echo "$json" | tr ',' ' ' | tr -d '\n' | cut -c1-120); fi
  fi
  echo "$TS,$port,$MODEL,${http:-000},$status,$msg" >> "$OUT"
  echo "[$port] http=${http:-000} $status $msg"
done

echo "saved: $OUT"