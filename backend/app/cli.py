"""Run a full analysis from the command line, without starting the server.

    python -m app.cli sample_data/carved-from-stone --title "Carved From Stone"
"""

import argparse
import shutil
import sys
import time
from pathlib import Path

from app.config import settings
from app.services.ingest import collect_local_stems
from app.services.pipeline import run_analysis
from app.services.preview_manifest import build_preview_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Transcribe a folder of stems into a player sheet.")
    parser.add_argument("folder", type=Path, help="Folder containing the stem audio files")
    parser.add_argument("--title", default=None, help="Song title for the sheet")
    parser.add_argument("--job-id", default=None, help="Reuse a fixed job id instead of a timestamp")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write the job here instead of under the jobs root",
    )
    args = parser.parse_args(argv)

    if not args.folder.is_dir():
        print(f"Not a folder: {args.folder}", file=sys.stderr)
        return 2

    stems = collect_local_stems(args.folder)
    if not stems:
        print(f"No audio files found in {args.folder}", file=sys.stderr)
        return 2

    title = args.title or args.folder.name.replace("-", " ").title()
    job_id = args.job_id or f"cli-{int(time.time())}"
    job_dir = args.out or (settings.jobs_root / job_id)
    job_dir.mkdir(parents=True, exist_ok=True)

    # The pipeline expects the stems to live inside the job, and deletes that
    # copy when it is done — so never hand it the originals.
    input_dir = job_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for stem in stems:
        target = input_dir / stem.name
        if not target.exists():
            shutil.copy2(stem, target)
        copied.append(target)

    print(f"Analysing {len(copied)} stems from {args.folder} …")
    started = time.time()
    analysis = run_analysis(job_id, job_dir, copied, title)
    build_preview_manifest(job_dir, analysis)
    elapsed = time.time() - started

    tempo = analysis["tempo"]
    print(f"\n{title}")
    print(f"  key       {analysis['key']['key_name']}  (confidence {analysis['key']['confidence']:.2f})")
    print(f"  tempo     {tempo['bpm']:.1f} BPM  {tempo['time_signature']}  "
          f"{tempo['bar_count']} bars  (confidence {tempo['confidence']:.2f})")
    print(f"  sections  {', '.join(s['name'] for s in analysis['sections']) or '—'}")
    print(f"  chords    {analysis['chord_count']} changes")
    for part in analysis["parts"]:
        print(f"  {part['name']:<16} {part['note_count']:>5} events  {part['range']}")
    if analysis["warnings"]:
        print("\n  warnings:")
        for warning in analysis["warnings"]:
            print(f"    - {warning}")
    print(f"\nDone in {elapsed:.1f}s → {job_dir}")
    print(f"  player sheet : {job_dir / 'player_sheet.html'}")
    print(f"  lead sheet   : {job_dir / 'score' / 'lead_sheet.musicxml'}")
    print(f"  full score   : {job_dir / 'score' / 'full_score.musicxml'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
