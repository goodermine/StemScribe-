from app.services.classify import classify_stem, lane_for_stem, profile_for, unique_key


def test_classification_aliases() -> None:
    assert classify_stem('leadvox.wav') == 'vocals'
    assert classify_stem('0 Lead Vocals.wav') == 'vocals'
    assert classify_stem('perc_loop.wav') == 'percussion'
    assert lane_for_stem('drums') == 'rhythm'


def test_drums_and_percussion_stay_separate() -> None:
    """Collapsing these two loses the kit, which the beat tracker depends on."""
    assert classify_stem('1 Drums.wav') == 'drums'
    assert classify_stem('5 Percussion.wav') == 'percussion'


def test_numeric_prefixes_do_not_confuse_matching() -> None:
    assert classify_stem('3 Guitar.wav') == 'guitar'
    assert classify_stem('4 Keyboard.wav') == 'keys'
    assert classify_stem('6 Strings.wav') == 'strings'


def test_word_boundaries_not_substrings() -> None:
    """'slow' must not read as the bass alias 'low'."""
    assert classify_stem('slow build.wav') != 'bass'
    assert classify_stem('2 Bass.wav') == 'bass'


def test_unknown_stem_falls_back_to_other() -> None:
    assert classify_stem('stem_07.wav') == 'other'


def test_unique_key_avoids_overwriting_same_role() -> None:
    taken: set[str] = set()
    first = unique_key('guitar', taken)
    taken.add(first)
    second = unique_key('guitar', taken)
    assert first == 'guitar'
    assert second == 'guitar_2'


def test_bass_profile_is_monophonic_and_low() -> None:
    profile = profile_for('bass')
    assert profile.bass_clef is True
    assert profile.polyphonic is False
    assert profile.fmax_hz <= 400.0


def test_lead_vocal_does_not_inform_harmony() -> None:
    assert profile_for('vocals').informs_harmony is False
    assert profile_for('guitar').informs_harmony is True
