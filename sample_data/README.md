# Sample data

`carved-from-stone/` holds the seven stems of one song, used as the worked
example throughout the docs and as a realistic end-to-end input.

To run it:

```bash
cd backend
python -m app.cli ../sample_data/carved-from-stone --title "Carved From Stone"
```

To add your own, drop a folder of labelled stems in here. Name each file after
the instrument it holds — `Drums`, `Bass`, `Guitar`, `Keyboard`,
`Lead Vocals`, `Strings`, `Percussion` — since that is how each stem is routed
to the right kind of analysis.

Note that the automated tests do not read this folder. They generate a
synthetic song with a known key, tempo and chord progression instead, so that
assertions can be about musical correctness rather than about whichever song
happens to be checked in.
