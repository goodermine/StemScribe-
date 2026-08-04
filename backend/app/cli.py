"""Run a full analysis from the command line, without starting the server.

    python -m app.cli sample_data/carved-from-stone --title "Carved From Stone"

Pass --separate to point it at a single mixed file (or a folder holding one)
and have it recover the stems first:

    python -m app.cli mix.wav --separate --title "Some Song"
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
from app.services.separate import SeparationLicenseError, SeparationUnavailable, prepare_job_stems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Transcribe a folder of stems into a player sheet.")
    parser.add_argument("input", type=Path, help="Folder of stems, or a single mix file with --separate")
    parser.add_argument("--title", default=None, help="Song title for the sheet")
    parser.add_argument("--job-id", default=None, help="Reuse a fixed job id instead of a timestamp")
    parser.add_argument(
        "--separate",
        action="store_true",
        help="Treat the input as one mix and recover stems from it before analysing",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="audio-separator model key or filename (default: the commercial-safe pick)",
    )
    parser.add_argument(
        "--allow-noncommercial-model",
        action="store_true",
        help="Permit a non-commercial separation model (personal/research use only)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write the job here instead of under the jobs root",
    )
    args = parser.parse_args(argv)

    if args.input.is_dir():
        stems = collect_local_stems(args.input)
        source_label = str(args.input)
        default_title_from = args.input.name
    elif args.input.is_file():
        stems = [args.input]
        source_label = str(args.input)
        default_title_from = args.input.stem
    else:
        print(f"Not a file or folder: {args.input}", file=sys.stderr)
        return 2

    if not stems:
        print(f"No audio files found in {args.input}", file=sys.stderr)
        return 2

    title = args.title or default_title_from.replace("-", " ").replace("_", " ").title()
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

    recovered_note = None
    if args.separate:
        print(f"Separating {source_label} into stems …")
        try:
            copied, recovered_note = prepare_job_stems(
                copied,
                input_dir,
                separate=True,
                model=args.model,
                allow_noncommercial=args.allow_noncommercial_model,
            )
        except (SeparationUnavailable, SeparationLicenseError, ValueError) as exc:
            print(f"Separation could not run: {exc}", file=sys.stderr)
            return 2
        print(f"  recovered {len(copied)} stems")

    print(f"Analysing {len(copied)} stems from {source_label} …")
    started = time.time()
    analysis = run_analysis(job_id, job_dir, copied, title, recovered_note=recovered_note)
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
