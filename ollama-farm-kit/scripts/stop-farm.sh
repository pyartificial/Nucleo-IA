#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/farm.env"
PID_FILE="$ROOT/state/farm-pids.tsv"

es_proceso_propio() {
  local index="$1" pid="$2" expected_home args environ
  expected_home="$OLLAMA_BASE_DIR/acc$index"
  [[ -r "/proc/$pid/cmdline" && -r "/proc/$pid/environ" ]] || return 1
  args="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  environ="$(tr '\0' '\n' < "/proc/$pid/environ" 2>/dev/null || true)"
  [[ "$args" == *"ollama serve"* && "$environ" == *$'HOME='"$expected_home"$'\n'* ]]
}

if [[ ! -f "$PID_FILE" ]]; then
  echo "[info] Este kit no tiene instancias registradas para detener."
  exit 0
fi

while IFS=$'\t' read -r index pid; do
  [[ -n "${index:-}" && -n "${pid:-}" ]] || continue
  if es_proceso_propio "$index" "$pid"; then
    kill "$pid"
    echo "[ok] Señal de detención enviada a acc$index (PID $pid)."
  else
    echo "[skip] PID $pid no coincide con la instancia acc$index de este kit; no se tocó."
  fi
done < "$PID_FILE"
rm -f "$PID_FILE"
