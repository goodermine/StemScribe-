"""The player sheet: everything a musician needs on one page.

Notation is precise but slow to read, and machine transcription of a mixed
recording is never note-perfect. A chart is the honest format for this output —
key, tempo, structure, the chord progression bar by bar, and the groove — which
is what a guitarist or a drummer actually asks for when handed a song.
"""

from collections import Counter
from html import escape
from typing import Sequence

BARS_PER_LINE = 4

# Sixteenth-note slots in one bar of 4/4, used for the groove grid.
SLOTS_PER_BEAT = 4


def build_chart(
    title: str,
    tempo_info: dict,
    key_info: dict,
    sections: Sequence[dict],
    chords: Sequence[dict],
    drum_hits: Sequence[dict],
    parts_summary: Sequence[dict],
    duration_sec: float,
    warnings: Sequence[str],
) -> dict:
    beats_per_bar = int(tempo_info.get("beats_per_bar", 4))
    bar_count = int(tempo_info.get("bar_count", 0))
    bar_chords = chords_per_bar(chords, bar_count, beats_per_bar)

    return {
        "title": title,
        "key": key_info.get("key_name", "unknown"),
        "key_confidence": key_info.get("confidence", 0.0),
        "bpm": round(float(tempo_info.get("bpm", 120.0))),
        "time_signature": tempo_info.get("time_signature_guess", "4/4"),
        "tempo_confidence": tempo_info.get("confidence", 0.0),
        "bar_count": bar_count,
        "duration_sec": round(duration_sec, 1),
        "sections": [dict(s) for s in sections],
        "progression": section_progressions(sections, bar_chords),
        "bar_chords": bar_chords,
        "groove": groove_grid(drum_hits, beats_per_bar),
        "parts": [dict(p) for p in parts_summary],
        "warnings": list(warnings),
    }


def chords_per_bar(chords: Sequence[dict], bar_count: int, beats_per_bar: int) -> list[list[str]]:
    """The chord symbols sounding in each bar, in order.

    A chord that starts in an earlier bar and is still held carries forward, so
    no bar is left blank when nothing changed.
    """
    bars: list[list[str]] = [[] for _ in range(max(bar_count, 0))]
    for entry in chords:
        start_bar = int(entry["bar_index"])
        end_bar = int(max(entry["end_beat"] - 1e-6, entry["start_beat"]) // beats_per_bar)
        for bar in range(max(start_bar, 0), min(end_bar, len(bars) - 1) + 1):
            if 0 <= bar < len(bars) and entry["symbol"] not in bars[bar]:
                bars[bar].append(entry["symbol"])
    return bars


def section_progressions(sections: Sequence[dict], bar_chords: list[list[str]]) -> list[dict]:
    out = []
    for section in sections:
        start, end = int(section["start_bar"]), int(section["end_bar"])
        bars = [bar_chords[b] if 0 <= b < len(bar_chords) else [] for b in range(start, end + 1)]
        flat = [c for bar in bars for c in bar]
        out.append(
            {
                "name": section["name"],
                "start_bar": start + 1,
                "end_bar": end + 1,
                "bar_count": section.get("bar_count", end - start + 1),
                "bars": bars,
                "unique_chords": list(dict.fromkeys(flat)),
            }
        )
    return out


def groove_grid(drum_hits: Sequence[dict], beats_per_bar: int) -> dict:
    """The bar pattern the drummer plays most often, as a readable grid."""
    if not drum_hits:
        return {"available": False, "rows": [], "slots": 0, "coverage": 0.0, "pattern_bars": 0}

    slots = beats_per_bar * SLOTS_PER_BEAT
    by_bar: dict[int, set[tuple[str, int]]] = {}
    for hit in drum_hits:
        bar = int(hit["bar_index"])
        slot = int(round((float(hit["beat_in_bar"]) - 1.0) * SLOTS_PER_BEAT)) % slots
        by_bar.setdefault(bar, set()).add((hit["instrument"], slot))

    if not by_bar:
        return {"available": False, "rows": [], "slots": slots, "coverage": 0.0, "pattern_bars": 0}

    signatures = Counter(frozenset(v) for v in by_bar.values())
    pattern, count = signatures.most_common(1)[0]

    instruments = ["hihat", "snare", "kick", "tom", "cymbal"]
    present = [i for i in instruments if any(inst == i for inst, _ in pattern)]
    rows = []
    for inst in present or ["kick", "snare"]:
        cells = [False] * slots
        for hit_inst, slot in pattern:
            if hit_inst == inst and 0 <= slot < slots:
                cells[slot] = True
        rows.append({"instrument": inst, "cells": cells})

    return {
        "available": True,
        "rows": rows,
        "slots": slots,
        "beats_per_bar": beats_per_bar,
        "coverage": round(count / max(len(by_bar), 1), 3),
        "pattern_bars": count,
        "total_bars": len(by_bar),
    }


def render_markdown(chart: dict) -> str:
    lines = [
        f"# {chart['title']}",
        "",
        f"**{chart['key']}** · **{chart['bpm']} BPM** · **{chart['time_signature']}** · "
        f"{chart['bar_count']} bars · {_mmss(chart['duration_sec'])}",
        "",
        "## Structure",
        "",
        "| Section | Bars | Chords |",
        "| --- | --- | --- |",
    ]
    for section in chart["progression"]:
        chords = " ".join(section["unique_chords"]) or "—"
        lines.append(
            f"| {section['name']} | {section['start_bar']}–{section['end_bar']} "
            f"({section['bar_count']}) | {chords} |"
        )

    lines += ["", "## Chord chart", ""]
    for section in chart["progression"]:
        lines.append(f"**{section['name']}**  (bars {section['start_bar']}–{section['end_bar']})")
        lines.append("")
        for offset in range(0, len(section["bars"]), BARS_PER_LINE):
            row = section["bars"][offset : offset + BARS_PER_LINE]
            cells = [" ".join(bar) if bar else "%" for bar in row]
            lines.append("| " + " | ".join(f"{c:<10}" for c in cells) + " |")
        lines.append("")

    groove = chart["groove"]
    if groove.get("available"):
        lines += ["## Groove", "", "```"]
        header = "        " + "".join(
            f"{(i // SLOTS_PER_BEAT) + 1}" if i % SLOTS_PER_BEAT == 0 else "."
            for i in range(groove["slots"])
        )
        lines.append(header)
        for row in groove["rows"]:
            cells = "".join("x" if c else "-" for c in row["cells"])
            lines.append(f"{row['instrument']:<8}{cells}")
        lines += ["```", "", f"Main pattern covers {int(groove['coverage'] * 100)}% of bars.", ""]

    if chart["parts"]:
        lines += ["## Parts", "", "| Part | Notes | Range | Confidence |", "| --- | --- | --- | --- |"]
        for part in chart["parts"]:
            lines.append(
                f"| {part['name']} | {part['note_count']} | {part.get('range', '—')} | "
                f"{part.get('confidence', 0):.2f} |"
            )

    if chart["warnings"]:
        lines += ["", "## Notes on this transcription", ""]
        lines += [f"- {w}" for w in chart["warnings"]]

    return "\n".join(lines) + "\n"


def render_html(chart: dict) -> str:
    """Self-contained printable chart. No external assets, prints to A4."""
    sections_html = "".join(
        f"<tr><td class='name'>{escape(s['name'])}</td>"
        f"<td>{s['start_bar']}–{s['end_bar']}</td>"
        f"<td>{s['bar_count']}</td>"
        f"<td class='chords'>{escape(' '.join(s['unique_chords']) or '—')}</td></tr>"
        for s in chart["progression"]
    )

    chart_html = []
    for section in chart["progression"]:
        rows = []
        for offset in range(0, len(section["bars"]), BARS_PER_LINE):
            cells = "".join(
                f"<div class='bar'><span class='barno'>{section['start_bar'] + offset + i}</span>"
                f"<span class='sym'>{escape(' '.join(bar)) if bar else '%'}</span></div>"
                for i, bar in enumerate(section["bars"][offset : offset + BARS_PER_LINE])
            )
            rows.append(f"<div class='barline'>{cells}</div>")
        chart_html.append(
            f"<section class='block'><h3>{escape(section['name'])}"
            f"<small>bars {section['start_bar']}–{section['end_bar']}</small></h3>"
            + "".join(rows)
            + "</section>"
        )

    groove = chart["groove"]
    groove_html = ""
    if groove.get("available"):
        beat_header = "".join(
            f"<td class='tick {'beat' if i % SLOTS_PER_BEAT == 0 else ''}'>"
            f"{(i // SLOTS_PER_BEAT) + 1 if i % SLOTS_PER_BEAT == 0 else ''}</td>"
            for i in range(groove["slots"])
        )
        rows = "".join(
            "<tr><th>"
            + escape(row["instrument"])
            + "</th>"
            + "".join(
                f"<td class='cell {'hit' if c else ''} {'beat' if i % SLOTS_PER_BEAT == 0 else ''}'></td>"
                for i, c in enumerate(row["cells"])
            )
            + "</tr>"
            for row in groove["rows"]
        )
        groove_html = (
            "<section class='block'><h3>Groove<small>"
            f"main pattern, {int(groove['coverage'] * 100)}% of bars</small></h3>"
            f"<table class='groove'><tr><th></th>{beat_header}</tr>{rows}</table></section>"
        )

    parts_html = "".join(
        f"<tr><td class='name'>{escape(p['name'])}</td><td>{p['note_count']}</td>"
        f"<td>{escape(str(p.get('range', '—')))}</td>"
        f"<td>{p.get('confidence', 0):.2f}</td></tr>"
        for p in chart["parts"]
    )

    warnings_html = ""
    if chart["warnings"]:
        items = "".join(f"<li>{escape(w)}</li>" for w in chart["warnings"])
        warnings_html = f"<section class='block caveats'><h3>Read this first</h3><ul>{items}</ul></section>"

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(chart['title'])} — player sheet</title>
<style>{_CSS}</style></head><body>
<header>
  <h1>{escape(chart['title'])}</h1>
  <p class="meta">
    <span class="pill">{escape(chart['key'])}</span>
    <span class="pill">{chart['bpm']} BPM</span>
    <span class="pill">{escape(chart['time_signature'])}</span>
    <span class="pill">{chart['bar_count']} bars</span>
    <span class="pill">{_mmss(chart['duration_sec'])}</span>
  </p>
</header>
{warnings_html}
<section class="block"><h3>Structure</h3>
<table class="grid"><tr><th>Section</th><th>Bars</th><th>Length</th><th>Chords</th></tr>{sections_html}</table>
</section>
<section class="block"><h3>Chord chart</h3></section>
{''.join(chart_html)}
{groove_html}
<section class="block"><h3>Parts</h3>
<table class="grid"><tr><th>Part</th><th>Notes</th><th>Range</th><th>Confidence</th></tr>{parts_html}</table>
</section>
</body></html>"""


_CSS = """
:root { --ink:#14161a; --dim:#666; --line:#d8d8d8; --accent:#1a4d8f; --hit:#1a4d8f; }
* { box-sizing:border-box; }
body { font:15px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
       color:var(--ink); margin:0; padding:28px; max-width:900px; background:#fff; }
h1 { font-size:26px; margin:0 0 6px; letter-spacing:-.01em; }
h3 { font-size:13px; text-transform:uppercase; letter-spacing:.08em; color:var(--dim);
     margin:0 0 10px; display:flex; align-items:baseline; gap:10px; }
h3 small { font-size:11px; text-transform:none; letter-spacing:0; color:var(--dim); font-weight:400; }
.meta { margin:0 0 22px; display:flex; flex-wrap:wrap; gap:6px; }
.pill { border:1px solid var(--line); border-radius:999px; padding:3px 11px; font-size:13px;
        font-variant-numeric:tabular-nums; }
.block { margin:0 0 26px; }
table.grid { border-collapse:collapse; width:100%; font-size:14px; }
table.grid th { text-align:left; font-size:11px; text-transform:uppercase; letter-spacing:.06em;
                color:var(--dim); border-bottom:1px solid var(--line); padding:6px 8px; }
table.grid td { padding:6px 8px; border-bottom:1px solid #f0f0f0; }
table.grid td.name { font-weight:600; }
table.grid td.chords { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }
.barline { display:grid; grid-template-columns:repeat(4,1fr); gap:0; margin-bottom:8px;
           border:1px solid var(--line); border-radius:4px; overflow:hidden; }
.bar { position:relative; padding:16px 10px 12px; border-right:1px solid var(--line); min-height:56px; }
.barline .bar:last-child { border-right:none; }
.barno { position:absolute; top:3px; left:6px; font-size:10px; color:#aaa;
         font-variant-numeric:tabular-nums; }
.sym { font-size:17px; font-weight:600; letter-spacing:-.01em; }
table.groove { border-collapse:collapse; font-size:11px; }
table.groove th { text-align:right; padding-right:10px; color:var(--dim); font-weight:500;
                  font-size:12px; }
table.groove td.cell { width:17px; height:17px; border:1px solid #e8e8e8; }
table.groove td.cell.beat { border-left:1px solid #999; }
table.groove td.cell.hit { background:var(--hit); }
table.groove td.tick { text-align:left; color:var(--dim); font-variant-numeric:tabular-nums;
                       padding-bottom:3px; }
.caveats { background:#fbf7ec; border:1px solid #e8dcc0; border-radius:6px; padding:14px 16px; }
.caveats ul { margin:0; padding-left:18px; }
.caveats li { margin-bottom:4px; font-size:14px; }
@media print { body { padding:0; } .block { break-inside:avoid; } }
@media (prefers-color-scheme: dark) {
  :root { --ink:#e8e8e8; --dim:#999; --line:#3a3a3a; --hit:#6ea8f0; }
  body { background:#16181c; }
  table.grid td { border-bottom-color:#262626; }
  table.groove td.cell { border-color:#333; }
  .caveats { background:#241f14; border-color:#4a3f28; }
}
"""


def _mmss(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 60}:{total % 60:02d}"
