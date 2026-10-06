#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/farm.env"
STATE_DIR="$ROOT/state"
PID_FILE="$STATE_DIR/farm-pids.tsv"
mkdir -p "$STATE_DIR"

es_proceso_propio() {
  local index="$1" pid="$2" expected_home args environ
  expected_home="$OLLAMA_BASE_DIR/acc$index"
  [[ -r "/proc/$pid/cmdline" && -r "/proc/$pid/environ" ]] || return 1
  args="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  environ="$(tr '\0' '\n' < "/proc/$pid/environ" 2>/dev/null || true)"
  [[ "$args" == *"ollama serve"* && "$environ" == *$'HOME='"$expected_home"$'\n'* ]]
}

if [[ -f "$PID_FILE" ]]; then
  while IFS=$'\t' read -r index pid; do
    [[ -n "${index:-}" && -n "${pid:-}" ]] || continue
    if es_proceso_propio "$index" "$pid"; then
      echo "[info] acc$index ya está iniciada por este kit (PID $pid)."
      echo "       Para detener solo estas instancias: bash scripts/stop-farm.sh"
      exit 0
    fi
  done < "$PID_FILE"
  rm -f "$PID_FILE"
fi

for i in $(seq 1 "$INSTANCIAS"); do
  port=$((PUERTO_BASE+i-1))
  if timeout 1 bash -c "</dev/tcp/127.0.0.1/$port" 2>/dev/null; then
    echo "[error] El puerto $port ya está ocupado. No se detuvo ni modificó el proceso existente."
    exit 1
  fi
done

detener_iniciadas() {
  while IFS=$'\t' read -r index pid; do
    [[ -n "${index:-}" && -n "${pid:-}" ]] || continue
    if es_proceso_propio "$index" "$pid"; then kill "$pid" 2>/dev/null || true; fi
  done < "$PID_FILE"
  rm -f "$PID_FILE"
}
trap detener_iniciadas ERR INT TERM

for i in $(seq 1 "$INSTANCIAS"); do
  port=$((PUERTO_BASE+i-1))
  inst_dir="$OLLAMA_BASE_DIR/acc$i"
  mkdir -p "$inst_dir/logs"
  HOME="$inst_dir" OLLAMA_HOST="127.0.0.1:$port" OLLAMA_CONTEXT_LENGTH="$CONTEXT_LENGTH" nohup ollama serve > "$inst_dir/logs/ollama.log" 2>&1 &
  pid=$!
  printf '%s\t%s\n' "$i" "$pid" >> "$PID_FILE"
  echo "[ok] acc$i -> :$port pid=$!"
  sleep 0.6
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "[error] acc$i no pudo iniciar. Se detienen únicamente los procesos creados por este kit."
    false
  fi
done

trap - ERR INT TERM
echo "[done] La granja quedó registrada en $PID_FILE."
