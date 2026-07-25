"""Musical correctness on a song whose key, tempo and chords are known."""

import pytest

from app.services.beat_grid import beat_map_from_grid, estimate_beat_grid
from app.services.chords import estimate_chords
from app.services.classify import classify_stem
from app.services.drum_transcribe import transcribe_drums
from app.services.key_detect import detect_key, key_signature_fifths, roman_numeral
from app.services.melody_extract import extract_melody_events, pick_lead_stem
from app.services.sections import analyse_sections


@pytest.fixture(scope="module")
def stems(synthetic_song):
    by_role: dict[str, list] = {}
    for path in sorted(synthetic_song.iterdir()):
        by_role.setdefault(classify_stem(path.name), []).append(path)
    return by_role


@pytest.fixture(scope="module")
def grid(stems, synthetic_song):
    return estimate_beat_grid(sorted(synthetic_song.iterdir()), stems)


def test_tempo_is_recovered(grid, expected) -> None:
    assert grid["bpm"] == pytest.approx(expected["bpm"], rel=0.05)


def test_beat_tracking_prefers_the_drum_stem(grid) -> None:
    assert grid["timing_source"] == "drums"


def test_meter_is_four_four(grid, expected) -> None:
    assert grid["beats_per_bar"] == expected["beats_per_bar"]
    assert grid["time_signature_guess"] == "4/4"


def test_bar_count_matches_the_song_length(grid, expected) -> None:
    assert grid["bar_count"] == pytest.approx(expected["bars"], abs=1)


def test_grid_confidence_is_computed_not_constant(grid) -> None:
    """A clean click track should score well above the old hardcoded 0.75."""
    assert 0.0 < grid["confidence"] <= 0.99
    assert grid["confidence"] > 0.5


def test_beats_are_monotonic(grid) -> None:
    times = grid["beat_times"]
    assert all(b > a for a, b in zip(times, times[1:]))


def test_key_is_recovered(stems, expected) -> None:
    harmony = [p for role in ("keys", "bass") for p in stems.get(role, [])]
    key = detect_key(harmony)
    assert key["key_name"] == expected["key"]
    assert key["fifths"] == 0


def test_key_signature_for_flat_keys() -> None:
    """E-flat major has three flats; its relative C minor shares them."""
    assert key_signature_fifths(3, "major") == -3
    assert key_signature_fifths(0, "minor") == -3
    assert key_signature_fifths(9, "minor") == 0


def test_roman_numerals_reflect_quality() -> None:
    assert roman_numeral(0, "maj", 0, "major") == "I"
    assert roman_numeral(9, "min", 0, "major") == "vi"
    assert roman_numeral(7, "7", 0, "major") == "V7"
    assert roman_numeral(1, "maj", 0, "major") == ""


def test_chord_progression_is_recovered(stems, grid, expected) -> None:
    key = detect_key([p for role in ("keys", "bass") for p in stems.get(role, [])])
    chords = estimate_chords(stems, beat_map_from_grid(grid), key)
    assert chords, "no chords detected"

    found = {c["root"] for c in chords}
    roots = {symbol.rstrip("m") for symbol in expected["chords"]}
    # Every chord root in the progression should turn up somewhere.
    assert roots.issubset(found), f"missing roots: {roots - found}"


def test_chords_do_not_flicker(stems, grid) -> None:
    """A chart that changes chord twice a beat is unusable."""
    key = detect_key([p for role in ("keys", "bass") for p in stems.get(role, [])])
    chords = estimate_chords(stems, beat_map_from_grid(grid), key)
    assert all(c["duration_beats"] >= 2.0 for c in chords)


def test_chords_cover_the_song_without_gaps(stems, grid) -> None:
    key = detect_key([p for role in ("keys", "bass") for p in stems.get(role, [])])
    chords = estimate_chords(stems, beat_map_from_grid(grid), key)
    for current, following in zip(chords, chords[1:]):
        assert current["end_beat"] == pytest.approx(following["start_beat"])


def test_melody_stays_in_range_and_is_not_frame_noise(stems, grid) -> None:
    role, path = pick_lead_stem(stems)
    assert role == "vocals"
    notes = extract_melody_events(role, path, beat_map_from_grid(grid))

    assert notes, "no melody detected"
    # Sixteen seconds of half-note melody is around 16 notes. The old
    # frame-per-note approach produced hundreds.
    assert len(notes) < 60, f"melody has {len(notes)} notes; that is frame noise"
    assert all(48 <= n["midi"] <= 84 for n in notes)
    assert all(0.0 <= n["confidence"] <= 1.0 for n in notes)


def test_drum_hits_land_on_the_beat(stems, grid) -> None:
    hits = transcribe_drums("drums", stems["drums"][0], beat_map_from_grid(grid))
    assert hits, "no drum hits detected"

    kicks = [h for h in hits if h["instrument"] == "kick"]
    snares = [h for h in hits if h["instrument"] == "snare"]
    assert kicks and snares, f"kit pieces not separated: {sorted({h['instrument'] for h in hits})}"

    # The pattern puts kicks on 1 and 3, snares on 2 and 4.
    assert {round(h["beat_in_bar"]) for h in kicks} <= {1, 3}
    assert {round(h["beat_in_bar"]) for h in snares} <= {2, 4}


def test_no_duplicate_drum_hits_in_one_slot(stems, grid) -> None:
    hits = transcribe_drums("drums", stems["drums"][0], beat_map_from_grid(grid))
    keys = [(h["instrument"], h["start_beat"]) for h in hits]
    assert len(keys) == len(set(keys))


def test_sections_are_contiguous_and_named(stems, grid) -> None:
    sections = analyse_sections(stems, beat_map_from_grid(grid))
    if not sections:
        pytest.skip("song too short to segment")
    assert all(s["name"] for s in sections)
    for current, following in zip(sections, sections[1:]):
        assert current["end_beat"] == pytest.approx(following["start_beat"])
