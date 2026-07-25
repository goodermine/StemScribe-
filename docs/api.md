# API

Base URL (local): `http://127.0.0.1:8000`

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness check. |
| POST | `/jobs` | Start a job. Multipart: `files` (repeated), `title`. |
| GET | `/jobs/{job_id}` | Status, then the full analysis once complete. |
| GET | `/jobs/{job_id}/chart` | The player sheet as structured data. |
| GET | `/jobs/{job_id}/sheet` | The player sheet as a printable HTML page. |
| GET | `/jobs/{job_id}/downloads` | Every generated file, as relative paths. |
| GET | `/jobs/{job_id}/preview-manifest` | Which score to show, and what else exists. |
| GET | `/jobs/{job_id}/files/{path}` | Fetch one generated file. |

## Starting a job

Analysis takes minutes for a full song, so `POST /jobs` returns immediately and
the work continues in the background.

```bash
curl -X POST http://127.0.0.1:8000/jobs \
  -F "title=Carved From Stone" \
  -F "files=@stems/0 Lead Vocals.wav" \
  -F "files=@stems/1 Drums.wav" \
  -F "files=@stems/2 Bass.wav"
# {"job_id":"…","status":"queued"}
```

Poll until `status` is `completed` or `failed`:

```bash
curl http://127.0.0.1:8000/jobs/$JOB_ID
```

`status` is one of `queued`, `processing`, `completed`, `failed`. A failed job
carries an `error` field.

Accepted audio: `.wav`, `.flac`, `.aiff`, `.aif`, `.ogg`, `.mp3`, `.m4a`.

## Getting the results

```bash
# the printable sheet
curl -O http://127.0.0.1:8000/jobs/$JOB_ID/files/player_sheet.html

# notation and MIDI
curl -O http://127.0.0.1:8000/jobs/$JOB_ID/files/score/lead_sheet.musicxml
curl -O http://127.0.0.1:8000/jobs/$JOB_ID/files/score/full_score.musicxml
curl -O http://127.0.0.1:8000/jobs/$JOB_ID/files/score/song.mid

# one part
curl -O http://127.0.0.1:8000/jobs/$JOB_ID/files/stems/bass/part.musicxml
```

`GET /jobs/{id}/downloads` lists everything a job produced, so there is no need
to guess paths.

## Job layout on disk

```text
jobs/<job_id>/
  status.json          queued | processing | completed | failed
  analysis.json        the summary: key, tempo, sections, parts, warnings
  tempo.json           bpm, beat times, bar starts, downbeat, meter
  key.json             tonic, mode, key signature, chroma
  chords.json          chord spans with bar and beat positions
  sections.json        section boundaries, names and groupings
  chart.json           the player sheet as data
  player_sheet.html    the printable sheet
  player_sheet.md      the same, as Markdown
  score/
    lead_sheet.musicxml
    full_score.musicxml
    song.mid
  lead_melody/
    lead_melody.musicxml  lead_melody.mid  lead_melody_notes.json
  stems/<part>/
    notes.json | rhythm.json
    part.musicxml  part.mid  metadata.json
  merged/preview_manifest.json
```

The uploaded audio is copied to `input/` while the job runs and deleted when it
finishes — stems are large, and the finished job only needs the symbolic output.

## Data contracts

`analysis.json`: `job_id`, `title`, `input_stems`, `detected_stem_types`,
`duration_sec`, `key`, `tempo`, `sections`, `chord_count`, `parts`, `warnings`,
`confidence_summary`, `created_at`.

Note events carry both wall-clock and musical positions: `start_sec`,
`end_sec`, `duration_sec`, `start_beat`, `end_beat`, `duration_beats`,
`bar_index`, `beat_in_bar`, plus `midi`, `note_name`, `source_stem` and
`confidence`.

Drum hits carry `instrument` (`kick`, `snare`, `hihat`, `tom`, `cymbal`),
`midi` (General MIDI percussion key), `start_beat`, `bar_index`, `beat_in_bar`,
`velocity` and `confidence`.

Chord spans carry `symbol`, `root`, `quality`, `roman`, the beat and bar
positions, and `confidence`.
