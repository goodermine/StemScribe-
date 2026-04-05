#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   scripts/run_local_demo.sh /absolute/or/relative/path/to/stems_folder
#
# Expected files in stems folder (any subset is allowed):
# vocals.wav drums.wav bass.wav keys.wav guitar.wav other.wav

STEMS_DIR="${1:-sample_data}"
API_BASE="${API_BASE:-http://127.0.0.1:8000}"

if [[ ! -d "$STEMS_DIR" ]]; then
  echo "Stems directory not found: $STEMS_DIR" >&2
  exit 1
fi

files=()
for name in vocals.wav drums.wav bass.wav keys.wav guitar.wav other.wav; do
  if [[ -f "$STEMS_DIR/$name" ]]; then
    files+=( -F "files=@$STEMS_DIR/$name" )
  fi
done

if [[ ${#files[@]} -eq 0 ]]; then
  echo "No supported WAV stems found in $STEMS_DIR" >&2
  exit 1
fi

echo "Submitting job to $API_BASE/jobs ..."
job_json=$(curl -sS -X POST "$API_BASE/jobs" "${files[@]}")
job_id=$(python - <<'PY' "$job_json"
import json,sys
print(json.loads(sys.argv[1])["job_id"])
PY
)

echo "Job ID: $job_id"

echo "\n== Job summary =="
curl -sS "$API_BASE/jobs/$job_id" | python -m json.tool

echo "\n== Preview manifest =="
curl -sS "$API_BASE/jobs/$job_id/preview-manifest" | python -m json.tool

echo "\n== Downloads list =="
curl -sS "$API_BASE/jobs/$job_id/downloads" | python -m json.tool

echo "\nOutput files on disk under: jobs/$job_id"
