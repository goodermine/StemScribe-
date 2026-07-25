#!/usr/bin/env bash
set -euo pipefail

# Submit a folder of stems to a running StemScribe server and wait for the
# sheet. To run the same analysis without a server, use the CLI instead:
#
#   cd backend && python -m app.cli <stems_folder> --title "Song Name"
#
# Usage:
#   scripts/run_local_demo.sh [stems_folder] [song title]

STEMS_DIR="${1:-sample_data/carved-from-stone}"
TITLE="${2:-$(basename "$STEMS_DIR" | tr '-' ' ')}"
API_BASE="${API_BASE:-http://127.0.0.1:8000}"

if [[ ! -d "$STEMS_DIR" ]]; then
  echo "Stems directory not found: $STEMS_DIR" >&2
  exit 1
fi

# Take whatever audio is in the folder rather than looking for fixed names —
# stems come out of Suno as "0 Lead Vocals.wav", "1 Drums.wav" and so on.
files=()
while IFS= read -r -d '' path; do
  files+=( -F "files=@${path}" )
done < <(find "$STEMS_DIR" -maxdepth 1 -type f \
  \( -iname '*.wav' -o -iname '*.flac' -o -iname '*.aiff' -o -iname '*.aif' \
     -o -iname '*.ogg' -o -iname '*.mp3' -o -iname '*.m4a' \) -print0 | sort -z)

if [[ ${#files[@]} -eq 0 ]]; then
  echo "No audio files found in $STEMS_DIR" >&2
  exit 1
fi

echo "Submitting ${#files[@]} stems as \"$TITLE\" to $API_BASE/jobs ..."
job_id=$(curl -sS -X POST "$API_BASE/jobs" -F "title=$TITLE" "${files[@]}" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["job_id"])')

echo "Job ID: $job_id"

# Analysis runs in the background; a full song takes a couple of minutes.
echo -n "Analysing"
for _ in $(seq 1 300); do
  status=$(curl -sS "$API_BASE/jobs/$job_id" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status","unknown"))')
  case "$status" in
    completed) echo " done."; break ;;
    failed)    echo " failed."; curl -sS "$API_BASE/jobs/$job_id" | python3 -m json.tool; exit 1 ;;
    *)         echo -n "."; sleep 2 ;;
  esac
done

if [[ "$status" != "completed" ]]; then
  echo " timed out waiting for the job." >&2
  exit 1
fi

echo
echo "== Summary =="
curl -sS "$API_BASE/jobs/$job_id" | python3 -m json.tool

echo
echo "== Files =="
curl -sS "$API_BASE/jobs/$job_id/downloads" | python3 -m json.tool

echo
echo "Player sheet: $API_BASE/jobs/$job_id/sheet"
echo "On disk:      backend/jobs/$job_id"
