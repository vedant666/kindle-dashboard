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

    tzname = cfg["display"]["timezone"]
    wx = air = None
    if "home" in order:
        wx = fetch.weather(loc["latitude"], loc["longitude"], tzname)
        air = fetch.air_quality(loc["latitude"], loc["longitude"], tzname)
    rows = market_rows(cfg) if "markets" in order else []
    quote = quote_of_the_day(now.date())

    # Every page is rendered twice: "home.png" (portrait) and "home-land.png" (landscape,
    # stored turned on its side). pages.txt lists the base names.
    pages, clocks = [], {}
    for suffix, ocfg in (("", cfg), ("-land", render.landscape(cfg))):
        land = bool(suffix)

        def save(name, img, clock=None):
            if clock:
                size, x, y = clock
                slots = [xy for xy, _ in render.clock_slots(size, x, y)]
                if land:
                    slots = [render.box_to_panel(xy, wh, img.size, cfg)
                             for xy, wh in render.clock_slots(size, x, y)]
                key = ("photo" if name.startswith("photo") else name) + suffix
                clocks[key] = (size + suffix, slots)
            if land:
                img = render.to_panel(img, cfg)
            img.save(out / f"{name}{suffix}.png", optimize=True)
            if not land:
                pages.append(name)

        for page in order:
            if page == "home":
                draw_home = render.page_home_land if land else render.page_home
                img, c = draw_home(ocfg, now, wx, air, news, quote)
                save("home", img, c.get("home"))
            elif page == "news":
                save("news", render.page_news(ocfg, now, news))
            elif page == "markets":
                save("markets", render.page_markets(ocfg, now, rows))
            elif page == "photo":
                n = 0
                for src in photo_sources():
                    try:
                        img, c = render.page_photo(ocfg, now, render.prepare_photo(src, ocfg))
                    except Exception as e:
                        print(f"warning: photo {src.name} failed: {e}", file=sys.stderr)
                        continue
                    n += 1
                    save(f"photo-{n}", img, c.get("photo"))
                if not n:
                    # Placeholder; the Kindle skips it when it has photos of its own (USB).
                    img, c = render.page_photo(ocfg, now, None)
                    save("photo-empty", img, c.get("photo"))
            elif not land:
                print(f"warning: unknown page {page!r} in config", file=sys.stderr)

    for size in render.CLOCK_SIZES:
        for suffix in ("", "-land"):
            tdir = out / "tiles" / f"{size}{suffix}"
            tdir.mkdir(parents=True, exist_ok=True)
            for ch, name in [(c, c) for c in "0123456789"] + [(":", "colon"), (" ", "blank")]:
                tile = render.clock_tile(size, ch)
                if suffix:
                    tile = render.to_panel(tile, cfg)
                tile.save(tdir / f"{name}.png", optimize=True)

    (out / "pages.txt").write_text("\n".join(pages) + "\n", encoding="utf-8")
    # "<page> <tile set> x y ..." with one x y per tile: hour 1, hour 2, colon, minute 1, minute 2
    lines = [f"{key} {tiles} " + " ".join(f"{x} {y}" for x, y in slots)
             for key, (tiles, slots) in clocks.items()]
    (out / "clock.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "landscape.txt").write_text(cfg["display"]["landscape_rotation"] + "\n", encoding="utf-8")
    (out / "updated.txt").write_text(now.isoformat(timespec="seconds") + "\n", encoding="utf-8")

    imgs = "\n".join(f'<figure><img src="{p}{s}.png" alt="{p}{s}" class="{s.strip("-")}">'
                     f'<figcaption>{p}{s}</figcaption></figure>'
                     for s in ("", "-land") for p in pages)
    (out / "index.html").write_text(f"""<!doctype html><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kindle dashboard</title>
<style>body{{font-family:sans-serif;background:#ddd;margin:16px}}
figure{{display:inline-block;margin:8px;text-align:center}}
img{{width:309px;border:1px solid #999;background:#fff}}
img.land{{transform:rotate({-90 if cfg['display']['landscape_rotation'] == 'cw' else 90}deg);margin:52px 0}}</style>
<p>Rendered {now:%d %b %Y %H:%M} ({cfg['display']['timezone']})</p>
{imgs}
""", encoding="utf-8")
    print(f"rendered {len(pages)} pages to {out}")


if __name__ == "__main__":
    main()
