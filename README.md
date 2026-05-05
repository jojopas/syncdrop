# SyncDrop

**Multicam audio sync that doesn't choke on iPhone footage.**

Drop a folder of clips, get a synced AAF you can import straight into Premiere. Free. Open source. Handles 50+ clips and mixed sources (iPhone, GoPro, DSLR, handheld) without complaining.

```bash
syncdrop ~/MyShoot/                                  # auto-pick reference, write synced.aaf
syncdrop ~/MyShoot/ --ref soundbooth.wav --out edit.aaf
```

## Why

PluralEyes costs $200 and falls over on iPhone footage. The Premiere built-in multicam sync is slow on large clip counts. SyncDrop is the tool I built to sync a 100-minute concert with 50+ clips from iPhones, GoPros, and three different cameras. It worked on the first try, so I'm releasing it.

## Install

```bash
pipx install syncdrop
# or
brew install joepascual/tap/syncdrop
```

Requires `ffmpeg` and `ffprobe` (`brew install ffmpeg`).

## How it works

1. Scans the folder for video files
2. Extracts a scratch audio track from each
3. Cross-correlates against a reference clip (longest by default)
4. Builds an AAF with each clip on its own track at the right offset
5. Open it in Premiere → group as multicam if you want

## Status

Alpha. Premiere-only (AAF). FCPXML and a Mac drag-drop GUI coming next.

## License

MIT
