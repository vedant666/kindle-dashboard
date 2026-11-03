"""Fetch data and render every dashboard page into out/.

Output layout (served from GitHub Pages, read by kindle/dashboard.sh):
  pages.txt          page names in rotate order, one per line
  <page>.png         one full-screen image per page
  clock.txt          "<page-prefix> <size> <x> <y> <digit_w> <colon_w>" per page with a clock
  tiles/<size>/*.png clock digit tiles: 0-9, colon, blank
  index.html         preview of every page in a browser
"""

import argparse
import sys
import tomllib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import fetch
import render
from quotes import quote_of_the_day

ROOT = Path(__file__).resolve().parent.parent
PHOTO_TYPES = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".bmp", ".gif", ".tif", ".tiff"}

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass


def market_rows(cfg):
    m = cfg["markets"]
    rows = []
    for idx in m["indices"]:
        prefix = "₹" if idx["symbol"] == "INR=X" else ""
        rows.append((idx["label"], fetch.quote(idx["symbol"]), prefix, 2))
    gold, fx = fetch.quote(m["gold_symbol"]), fetch.quote("INR=X")
    if gold and fx:
        per10g = 10 / 31.1035 * fx["price"]
        hist = [g * per10g for g in gold["history"]]
        gold = dict(gold, price=gold["price"] * per10g, change=gold["change"] * per10g, history=hist)
        rows.append(("Gold (intl., ₹ / 10 g)", gold, "₹", 0))
    else:
        rows.append(("Gold (intl., ₹ / 10 g)", None, "", 0))
    for sym in m["watchlist"]:
        rows.append((sym.removesuffix(".NS").removesuffix(".BO"), fetch.quote(sym), "₹", 2))
    return rows


def photo_sources():
    folder = ROOT / "photos"
    return sorted(p for p in folder.glob("*") if p.suffix.lower() in PHOTO_TYPES) if folder.exists() else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "out"))
    args = ap.parse_args()

    cfg = tomllib.loads((ROOT / "config.toml").read_text(encoding="utf-8"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tz = ZoneInfo(cfg["display"]["timezone"])
    now = datetime.now(tz)
    loc = cfg["location"]
    order = cfg["pages"]["order"]

    news = []
    if {"home", "news"} & set(order):
        per = cfg["news"]["headlines_per_section"]
        news = [(f["section"], fetch.feed(f["url"], per)) for f in cfg["news"]["feeds"]]

    pages, clocks = [], {}

    def save(name, img):
        img.save(out / f"{name}.png", optimize=True)
        pages.append(name)

    for page in order:
        if page == "home":
            wx = fetch.weather(loc["latitude"], loc["longitude"], cfg["display"]["timezone"])
            air = fetch.air_quality(loc["latitude"], loc["longitude"], cfg["display"]["timezone"])
            img, c = render.page_home(cfg, now, wx, air, news, quote_of_the_day(now.date()))
            clocks.update(c)
            save("home", img)
        elif page == "news":
            save("news", render.page_news(cfg, now, news))
        elif page == "markets":
            save("markets", render.page_markets(cfg, now, market_rows(cfg)))
        elif page == "photo":
            n = 0
            for src in photo_sources():
                try:
                    img, c = render.page_photo(cfg, now, render.prepare_photo(src, cfg))
                except Exception as e:
                    print(f"warning: photo {src.name} failed: {e}", file=sys.stderr)
                    continue
                n += 1
                clocks.update(c)
                save(f"photo-{n}", img)
            if not n:
                # Placeholder; the Kindle skips it when it has photos of its own (USB).
                img, c = render.page_photo(cfg, now, None)
                clocks.update(c)
                save("photo-empty", img)
        else:
            print(f"warning: unknown page {page!r} in config", file=sys.stderr)

    for size in render.CLOCK_SIZES:
        tdir = out / "tiles" / size
        tdir.mkdir(parents=True, exist_ok=True)
        for ch, name in [(c, c) for c in "0123456789"] + [(":", "colon"), (" ", "blank")]:
            render.clock_tile(size, ch).save(tdir / f"{name}.png", optimize=True)

    (out / "pages.txt").write_text("\n".join(pages) + "\n", encoding="utf-8")
    lines = []
    for prefix, (size, x, y) in clocks.items():
        _, dw, cw, _, _ = render.clock_metrics(size)
        lines.append(f"{prefix} {size} {x} {y} {dw} {cw}")
    (out / "clock.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "updated.txt").write_text(now.isoformat(timespec="seconds") + "\n", encoding="utf-8")

    imgs = "\n".join(f'<figure><img src="{p}.png" alt="{p}"><figcaption>{p}</figcaption></figure>'
                     for p in pages)
    (out / "index.html").write_text(f"""<!doctype html><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kindle dashboard</title>
<style>body{{font-family:sans-serif;background:#ddd;margin:16px}}
figure{{display:inline-block;margin:8px;text-align:center}}
img{{width:309px;border:1px solid #999;background:#fff}}</style>
<p>Rendered {now:%d %b %Y %H:%M} ({cfg['display']['timezone']})</p>
{imgs}
""", encoding="utf-8")
    print(f"rendered {len(pages)} pages to {out}")


if __name__ == "__main__":
    main()
