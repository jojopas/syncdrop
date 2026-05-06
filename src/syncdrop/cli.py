"""SyncDrop CLI entry point."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .pipeline import run_pipeline


def parse_edit_rate(spec: str) -> tuple[int, int]:
    """Parse edit-rate spec like '29.97', '23.976', '24', '60', '30000/1001'."""
    if "/" in spec:
        num, den = spec.split("/", 1)
        return int(num), int(den)
    f = float(spec)
    common = {
        23.976: (24000, 1001),
        24.0: (24, 1),
        25.0: (25, 1),
        29.97: (30000, 1001),
        30.0: (30, 1),
        50.0: (50, 1),
        59.94: (60000, 1001),
        60.0: (60, 1),
    }
    for k, v in common.items():
        if abs(f - k) < 0.01:
            return v
    return int(round(f)), 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="syncdrop",
        description="Multicam audio sync that doesn't choke on iPhone footage. "
                    "Drop a folder of clips, get a synced AAF for Premiere.",
    )
    p.add_argument("folder", type=Path, help="Folder containing video clips")
    p.add_argument("--ref", type=Path, default=None,
                   help="Reference video (defaults to longest clip with audio)")
    p.add_argument("--out", type=Path, default=None,
                   help="Output AAF path (default: <folder>/synced.aaf)")
    p.add_argument("--min-confidence", type=float, default=5.0,
                   help="Drop clips with correlation confidence below this (default 5.0)")
    p.add_argument("--fps", type=str, default=None,
                   help="Edit rate: 23.976, 24, 25, 29.97, 30, 59.94, 60, or num/den. "
                        "Default: auto-detect from reference clip.")
    p.add_argument("--dry-run", action="store_true",
                   help="Scan, extract scratch audio, and print the offset table — "
                        "but skip writing the AAF. Useful for sanity-checking confidence first.")
    p.add_argument("--quiet", action="store_true", help="Suppress progress output")
    p.add_argument("-V", "--version", action="version", version=f"syncdrop {__version__}")

    args = p.parse_args(argv)

    try:
        run_pipeline(
            input_folder=args.folder,
            output_aaf=args.out,
            reference_video=args.ref,
            min_confidence=args.min_confidence,
            edit_rate=parse_edit_rate(args.fps) if args.fps else None,
            verbose=not args.quiet,
            dry_run=args.dry_run,
        )
    except (RuntimeError, NotADirectoryError, ValueError) as e:
        print(f"syncdrop: error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
