# SyncDrop

**Multicam audio sync that doesn't choke on iPhone footage.**

Drop a folder of clips, get a synced AAF you can import straight into Premiere. Free. Open source. Handles 50+ clips and mixed sources (iPhone, GoPro, DSLR, handheld) without complaining.

```bash
syncdrop ~/MyShoot/                                  # auto-pick reference, write synced.aaf
syncdrop ~/MyShoot/ --ref soundbooth.wav --out edit.aaf
syncdrop ~/MyShoot/ --dry-run                        # confidence check, no AAF
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

## Example

Real run on a 50-clip concert shoot, mixed iPhone + GoPro + DSLR:

```
$ syncdrop ~/Concert/Day1
Found 54 video clips in /Volumes/Media/Concert/Day1
  extract: Soundbooth Cam 02.MP4
  extract: Hand-Held Camera (13).MP4
  ...
Reference: IMG_2611.MOV
Edit rate: 30000/1001 (29.970 fps, auto-detected from reference)

clip                                             offset_s     conf      len_s
------------------------------------------------------------------------------
IMG_2611.MOV                                        0.000      REF     8099.8
Soundbooth Cam 02.MP4                              61.780     42.8     3595.6
Hand-Held Camera (13).MP4                          90.240     82.7     3564.1
Stage-View GoPro (1).MP4                         -160.563     23.8      709.7
Tony YALEO TWISTED SET 1.MOV                       -1.653     73.5     1398.2
... 49 more clips ...

Timeline: 248861 frames @ 30000/1001 = 138.4 min

Wrote /Volumes/Media/Concert/Day1/synced.aaf (1676 KB)
Import in Premiere: File > Import > synced.aaf
```

Open the AAF in Premiere — every clip is on its own track at the correct offset, ready to be grouped as a multicam source sequence.

## How sync works

SyncDrop extracts a mono scratch audio track from each clip, downsamples it, and runs an FFT cross-correlation against a reference clip's scratch audio. Before correlating, it pre-emphasises the signal and computes a smoothed envelope so percussive transients (drum hits, hand claps, snare cracks) dominate. That's why it doesn't care if your iPhone audio is a tinny mess and your soundbooth feed is broadcast quality — they share the same transients, and the correlation peak lines them up to within a frame.

Each clip gets a confidence score (correlation peak height ÷ median noise). Anything above ~10 is rock-solid. Below 5 usually means the clip doesn't actually overlap the reference. SyncDrop drops low-confidence clips with a warning so you don't end up with one rogue camera 7 hours off the timeline.

In v1 every clip lands on its own video track. Group them as a multicam source sequence in Premiere if you want angle-switching.

## Status

Alpha. Premiere-only (AAF). FCPXML and a Mac drag-drop GUI coming next.

## License

MIT
