# Known limitations

Machine transcription of a mixed recording is never note-perfect. Every job
reports confidence values it actually computed and warns about what it was
unsure of. This is the honest summary of where it stands.

## Reliable

- **Tempo and beat grid**, when a drum stem is present. Tempo octave errors
  (half-time, double-time) are corrected.
- **Bar lines and section boundaries.** Boundaries are snapped to downbeats.
- **Chord roots**, and the overall progression.
- **Kick, snare and hi-hat** separation in the drum groove.

## Approximate

- **Chord quality.** Roots are dependable; sevenths, suspensions and added
  notes less so. Power chords are exported as MusicXML `kind=none`, so some
  notation software shows "F" where the chart says "F5".
- **Key.** Usually right, but a key and its relative major or minor are close
  in chroma. The job warns when the fit was close.
- **Melody and pitched-part notation.** Good for the shape and range of a line.
  Not a substitute for a transcriber's ear.
- **Polyphonic transcription** (guitar, keys). Peaks are picked from the
  constant-Q spectrum between onsets and overtones are suppressed, but dense
  voicings and reverb wash still produce notes nobody played.

## Not attempted

- **Lyrics.** Nothing here does speech recognition.
- **Cymbal types.** Telling a crash from a ride from an open hi-hat needs decay
  measurement across the following hits. Everything bright is called a hi-hat.
- **Section names.** Boundaries are detected; the labels "verse", "chorus" and
  "bridge" are inferred from loudness and whether vocals are present. Treat
  them as a guide.
- **Key or time-signature changes mid-song.** One key and one meter are
  reported for the whole song. Candidate meters are 4/4, 3/4, 6/8 and 2/4.
- **Tuplets and swing.** The grid is straight; triplet feel is quantized onto
  the nearest straight subdivision.
- **Stems that hold more than one instrument.** Each stem is treated as one
  part.
