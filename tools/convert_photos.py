"""Convert private photos on this PC into Kindle-ready PNGs, for copying over USB.

    python tools/convert_photos.py <folder-of-photos> [--out kindle/dashboard/photos]

Then copy the PNGs to the Kindle's dashboard/photos/ folder. They stay off GitHub.
"""

import argparse
import sys
import tomllib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "generator"))

import render  # noqa: E402
from main import PHOTO_TYPES  # noqa: E402  (also registers HEIC support)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--out", default=str(ROOT / "kindle" / "dashboard" / "photos"))
    args = ap.parse_args()

    cfg = tomllib.loads((ROOT / "config.toml").read_text(encoding="utf-8"))
    now = datetime.now(ZoneInfo(cfg["display"]["timezone"]))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    done = 0
    for src in sorted(Path(args.folder).iterdir()):
        if src.suffix.lower() not in PHOTO_TYPES:
            continue
        try:
            img, _ = render.page_photo(cfg, now, render.prepare_photo(src, cfg))
        except Exception as e:
            print(f"skipped {src.name}: {e}")
            continue
        img.save(out / f"{src.stem}.png", optimize=True)
        done += 1
    print(f"converted {done} photos into {out}")


if __name__ == "__main__":
    main()
