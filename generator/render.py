"""Draws the dashboard pages as 8-bit grayscale PNGs sized for the Kindle screen."""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

import fetch

FONTS = Path(__file__).resolve().parent.parent / "fonts"
BLACK, DARK, MID, LIGHT, WHITE = 0, 68, 119, 204, 255
MARGIN = 64

_font_cache = {}


def font(size, style="regular"):
    key = (size, style)
    if key not in _font_cache:
        name = {"regular": "NotoSans-Regular", "bold": "NotoSans-Bold",
                "italic": "NotoSerif-Italic"}[style]
        _font_cache[key] = ImageFont.truetype(str(FONTS / f"{name}.ttf"), size)
    return _font_cache[key]


def canvas(cfg):
    d = cfg["display"]
    img = Image.new("L", (d["width"], d["height"]), WHITE)
    return img, ImageDraw.Draw(img)


def to_eink(img):
    """Snap to the panel's 16 gray levels so the Kindle shows exactly what we drew."""
    return img.point(lambda v: round(v / 17) * 17)


def dither(img):
    pal = Image.new("P", (1, 1))
    pal.putpalette([v for i in range(16) for v in (i * 17,) * 3] + [0] * 3 * 240)
    return img.convert("RGB").quantize(palette=pal, dither=Image.Dither.FLOYDSTEINBERG).convert("L")


# ---------------------------------------------------------------- text helpers

def wrap(draw, text, fnt, width, max_lines=None):
    words, lines, line = text.split(), [], ""
    for w in words:
        trial = f"{line} {w}".strip()
        if draw.textlength(trial, font=fnt) <= width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and draw.textlength(last + "…", font=fnt) > width:
            last = last[:-1].rstrip()
        lines[-1] = last + "…"
    return lines


def text_block(draw, xy, text, fnt, width, fill=BLACK, max_lines=None, spacing=1.25):
    """Draw wrapped text; return the y just below it."""
    x, y = xy
    step = round(fnt.size * spacing)
    for line in wrap(draw, text, fnt, width, max_lines):
        draw.text((x, y), line, font=fnt, fill=fill)
        y += step
    return y


def hline(draw, y, cfg, width=3, fill=BLACK):
    draw.rectangle([MARGIN, y, cfg["display"]["width"] - MARGIN, y + width - 1], fill=fill)


def header(draw, cfg, title, now):
    draw.text((MARGIN, 48), title, font=font(84, "bold"), fill=BLACK)
    right = f"{now:%a} {now.day} {now:%b} · {now:%H:%M}"
    f = font(40)
    w = draw.textlength(right, font=f)
    draw.text((cfg["display"]["width"] - MARGIN - w, 86), right, font=f, fill=DARK)
    hline(draw, 170, cfg, 4)
    return 210


def footer(draw, cfg, text):
    f = font(30)
    h = cfg["display"]["height"]
    w = draw.textlength(text, font=f)
    draw.text(((cfg["display"]["width"] - w) / 2, h - 60), text, font=f, fill=MID)


def age(when, now):
    if not when:
        return ""
    mins = int((now - when.astimezone(now.tzinfo)).total_seconds() // 60)
    if mins < 60:
        return f"{max(mins, 1)}m ago"
    if mins < 48 * 60:
        return f"{mins // 60}h ago"
    return f"{mins // 1440}d ago"


# ---------------------------------------------------------------- weather icons

def icon(draw, kind, cx, cy, s, fill=BLACK):
    """Simple line-art weather icons, s = overall size in px."""
    lw = max(3, s // 22)

    def sun(x, y, r):
        draw.ellipse([x - r, y - r, x + r, y + r], outline=fill, width=lw)
        for i in range(8):
            a = i * math.pi / 4
            draw.line([x + math.cos(a) * r * 1.4, y + math.sin(a) * r * 1.4,
                       x + math.cos(a) * r * 1.85, y + math.sin(a) * r * 1.85], fill=fill, width=lw)

    def cloud(x, y, w, solid=False):
        h = w * 0.5
        parts = [(x - w * 0.22, y + h * 0.05, w * 0.26), (x + w * 0.12, y - h * 0.12, w * 0.32),
                 (x + w * 0.36, y + h * 0.12, w * 0.2)]
        base = [x - w * 0.48, y + h * 0.05, x + w * 0.56, y + h * 0.5]
        # Fill white first so the cloud covers anything behind it (the sun).
        for px, py, r in parts:
            draw.ellipse([px - r, py - r, px + r, py + r], fill=WHITE, outline=fill, width=lw)
        draw.rounded_rectangle(base, radius=h * 0.22, fill=WHITE, outline=fill, width=lw)
        # Erase the inner outlines so it reads as one shape.
        for px, py, r in parts:
            draw.ellipse([px - r + lw, py - r + lw, px + r - lw, py + r - lw], fill=WHITE)
        draw.rectangle([base[0] + lw, base[1], base[2] - lw, base[3] - lw - h * 0.1], fill=WHITE)
        return y + h * 0.5

    if kind == "sun":
        sun(cx, cy, s * 0.22)
    elif kind == "partly":
        sun(cx - s * 0.14, cy - s * 0.14, s * 0.16)
        cloud(cx + s * 0.06, cy + s * 0.08, s * 0.72)
    elif kind == "cloud":
        cloud(cx, cy - s * 0.05, s * 0.85)
    elif kind in ("rain", "snow", "storm"):
        bottom = cloud(cx, cy - s * 0.18, s * 0.8)
        for i in range(3):
            x = cx - s * 0.22 + i * s * 0.22
            y = bottom + s * 0.08
            if kind == "rain":
                draw.line([x + s * 0.04, y, x - s * 0.04, y + s * 0.18], fill=fill, width=lw)
            elif kind == "snow":
                r = s * 0.035
                draw.ellipse([x - r, y + s * 0.06 - r, x + r, y + s * 0.06 + r], fill=fill)
        if kind == "storm":
            y = bottom + s * 0.04
            draw.polygon([(cx + s * 0.04, y), (cx - s * 0.1, y + s * 0.2), (cx, y + s * 0.2),
                          (cx - s * 0.06, y + s * 0.36), (cx + s * 0.12, y + s * 0.12),
                          (cx + s * 0.02, y + s * 0.12)], fill=fill)
    elif kind == "fog":
        for i in range(4):
            y = cy - s * 0.2 + i * s * 0.14
            off = s * 0.06 * (i % 2)
            draw.line([cx - s * 0.32 + off, y, cx + s * 0.32 + off, y], fill=fill, width=lw)


def triangle(draw, x, y, size, up, fill=BLACK):
    if up:
        draw.polygon([(x, y + size), (x + size, y + size), (x + size / 2, y)], fill=fill)
    else:
        draw.polygon([(x, y), (x + size, y), (x + size / 2, y + size)], fill=fill)


# ---------------------------------------------------------------- clock tiles
# The Kindle redraws the clock itself every minute by pasting these tiles, so the
# time is always right even when the page image is half an hour old.

CLOCK_SIZES = {"big": 270, "small": 72}
CHARS = "0123456789:"


def clock_metrics(size):
    f = font(CLOCK_SIZES[size], "bold")
    digit_w = math.ceil(max(f.getlength(c) for c in "0123456789"))
    colon_w = math.ceil(f.getlength(":") * 1.1)
    asc, desc = f.getmetrics()
    # Noto's ascender leaves room for accents; trim the tile to the digits themselves.
    top = f.getbbox("0123456789:")[1]
    height = asc + desc // 3 - top
    return f, digit_w, colon_w, height, top


def clock_tile(size, char):
    f, dw, cw, h, top = clock_metrics(size)
    w = cw if char == ":" else dw
    tile = Image.new("L", (w, h), WHITE)
    if char != " ":
        d = ImageDraw.Draw(tile)
        d.text((w / 2, -top), char, font=f, fill=BLACK, anchor="ma")
    return to_eink(tile)


def clock_text(now, cfg):
    if cfg["display"]["clock_24h"]:
        return now.strftime("%H:%M")
    return f"{now.hour % 12 or 12:>2}:{now.minute:02d}"


def draw_clock(img, x, y, size, text):
    """Paste tiles exactly the way the Kindle script will, so the preview matches."""
    _, dw, cw, _, _ = clock_metrics(size)
    offsets = [0, dw, 2 * dw, 2 * dw + cw, 3 * dw + cw]
    for ch, off in zip(text, offsets):
        img.paste(clock_tile(size, ch), (x + off, y))


def clock_width(size):
    _, dw, cw, _, _ = clock_metrics(size)
    return 4 * dw + cw


def clock_slots(size, x, y):
    """Top-left corner of each tile in Kindle order: hour 1, hour 2, colon, minute 1, minute 2."""
    _, dw, cw, h, _ = clock_metrics(size)
    return [((x, y), (dw, h)), ((x + dw, y), (dw, h)), ((x + 2 * dw, y), (cw, h)),
            ((x + 2 * dw + cw, y), (dw, h)), ((x + 3 * dw + cw, y), (dw, h))]


# ---------------------------------------------------------------- landscape
# The panel is portrait, so a landscape page is drawn on a wide canvas and stored turned
# on its side. "cw" turns it clockwise: stand the Kindle with its USB port on the right.

def landscape(cfg):
    d = cfg["display"]
    return {**cfg, "display": {**d, "width": d["height"], "height": d["width"]}}


def to_panel(img, cfg):
    """Turn a landscape canvas so the portrait panel shows it upright."""
    return img.rotate(-90 if cfg["display"]["landscape_rotation"] == "cw" else 90, expand=True)


def box_to_panel(xy, wh, frame, cfg):
    """Where a box on the landscape canvas (size `frame`) lands on the panel."""
    (x, y), (w, h), (fw, fh) = xy, wh, frame
    if cfg["display"]["landscape_rotation"] == "cw":
        return fh - y - h, x
    return y, fw - x - w


# ---------------------------------------------------------------- pages

def page_home(cfg, now, wx, air, news, quote):
    img, draw = canvas(cfg)
    W = cfg["display"]["width"]
    clocks = {}

    cx = (W - clock_width("big")) // 2
    draw_clock(img, cx, 60, "big", clock_text(now, cfg))
    clocks["home"] = ("big", cx, 60)
    _, _, _, ch, _ = clock_metrics("big")

    date = now.strftime("%A, %d %B %Y").replace(" 0", " ")
    f = font(56)
    draw.text(((W - draw.textlength(date, font=f)) / 2, 60 + ch + 24), date, font=f, fill=BLACK)
    y = 60 + ch + 105
    hline(draw, y, cfg, 4)
    y += 36

    if wx:
        desc, kind = fetch.describe(wx["code"])
        icon(draw, kind, MARGIN + 130, y + 120, 240)
        tx = MARGIN + 290
        draw.text((tx, y - 10), f"{wx['temp']:.0f}°", font=font(150, "bold"), fill=BLACK)
        draw.text((tx, y + 175), desc, font=font(46, "bold"), fill=BLACK)
        draw.text((tx, y + 235), f"Feels like {wx['feels']:.0f}°", font=font(34), fill=DARK)

        today = wx["days"][0]
        rows = [("High / Low", f"{today['high']:.0f}° / {today['low']:.0f}°"),
                ("Rain chance", f"{today['rain']}%" if today["rain"] is not None else "—"),
                ("Humidity", f"{wx['humidity']}%")]
        if air and air["aqi"] is not None:
            rows.append(("AQI (US)", f"{air['aqi']} · {fetch.aqi_label(air['aqi'])}"))
        rows.append(("Sunrise – set", f"{wx['sunrise']:%H:%M} – {wx['sunset']:%H:%M}"))
        rx = 720
        for i, (label, val) in enumerate(rows):
            ry = y + i * 58
            draw.text((rx, ry), label, font=font(30), fill=MID)
            draw.text((W - MARGIN - draw.textlength(val, font=font(34, "bold")), ry - 4),
                      val, font=font(34, "bold"), fill=BLACK)
        y += 296

        # 3-day forecast
        cards = wx["days"][1:4]
        cw = (W - 2 * MARGIN) // 3
        for i, dday in enumerate(cards):
            x0 = MARGIN + i * cw
            mid = x0 + cw / 2
            name = dday["date"].strftime("%A")
            f = font(36, "bold")
            draw.text((mid - draw.textlength(name, font=f) / 2, y), name, font=f, fill=BLACK)
            icon(draw, fetch.describe(dday["code"])[1], mid, y + 105, 110)
            t = f"{dday['high']:.0f}° / {dday['low']:.0f}°"
            f = font(40, "bold")
            draw.text((mid - draw.textlength(t, font=f) / 2, y + 166), t, font=f, fill=BLACK)
            if dday["rain"] is not None:
                t = f"Rain {dday['rain']}%"
                f = font(30)
                draw.text((mid - draw.textlength(t, font=f) / 2, y + 218), t, font=f, fill=DARK)
            if i:
                draw.line([x0, y + 10, x0, y + 250], fill=LIGHT, width=2)
        y += 276
    else:
        draw.text((MARGIN, y), "Weather unavailable", font=font(44), fill=MID)
        y += 100

    hline(draw, y, cfg, 2, MID)
    y += 26
    draw.text((MARGIN, y), "HEADLINES", font=font(28, "bold"), fill=MID)
    y += 46
    tops = [items[0] for _, items in news if items][:3]
    for item in tops:
        draw.ellipse([MARGIN, y + 17, MARGIN + 11, y + 28], fill=BLACK)
        y = text_block(draw, (MARGIN + 30, y), item["title"], font(35), W - 2 * MARGIN - 30,
                       max_lines=2, spacing=1.2) + 14

    if quote:
        text, who = quote
        f = font(33, "italic")
        lines = wrap(draw, f"“{text}”", f, W - 2 * MARGIN - 40, max_lines=3)
        qh = len(lines) * 42 + 40
        qy = cfg["display"]["height"] - 90 - qh
        if qy > y + 30:
            hline(draw, qy - 26, cfg, 2, MID)
            for i, line in enumerate(lines):
                draw.text((MARGIN + 20, qy + i * 42), line, font=f, fill=BLACK)
            a = f"— {who}"
            fa = font(28)
            draw.text((W - MARGIN - draw.textlength(a, font=fa), qy + len(lines) * 42 + 2), a,
                      font=fa, fill=DARK)

    footer(draw, cfg, f"{cfg['location']['name']} · updated {now:%H:%M}")
    return to_eink(img), clocks


def page_home_land(cfg, now, wx, air, news, quote):
    """Two columns: clock, date and today's weather on the left; forecast, news, quote right."""
    img, draw = canvas(cfg)
    W, H = cfg["display"]["width"], cfg["display"]["height"]
    mid = W // 2
    lx0, lx1 = MARGIN, mid - 40
    rx0, rx1 = mid + 40, W - MARGIN
    draw.line([mid, 60, mid, H - 110], fill=LIGHT, width=2)

    # Left column
    cx = lx0 + (lx1 - lx0 - clock_width("big")) // 2
    draw_clock(img, cx, 50, "big", clock_text(now, cfg))
    clocks = {"home": ("big", cx, 50)}
    _, _, _, ch, _ = clock_metrics("big")
    date = f"{now:%A}, {now.day} {now:%B %Y}"
    f = font(46)
    draw.text((lx0 + (lx1 - lx0 - draw.textlength(date, font=f)) / 2, 50 + ch + 20), date,
              font=f, fill=BLACK)
    y = 50 + ch + 96
    draw.rectangle([lx0, y, lx1, y + 3], fill=BLACK)
    y += 34
    if wx:
        desc, kind = fetch.describe(wx["code"])
        icon(draw, kind, lx0 + 100, y + 100, 200)
        tx = lx0 + 240
        draw.text((tx, y - 14), f"{wx['temp']:.0f}°", font=font(130, "bold"), fill=BLACK)
        draw.text((tx, y + 150), desc, font=font(42, "bold"), fill=BLACK)
        draw.text((tx + draw.textlength(desc, font=font(42, "bold")) + 24, y + 158),
                  f"feels {wx['feels']:.0f}°", font=font(32), fill=DARK)
        y += 236
        today = wx["days"][0]
        rows = [("High / Low", f"{today['high']:.0f}° / {today['low']:.0f}°"),
                ("Rain chance", f"{today['rain']}%" if today["rain"] is not None else "—"),
                ("Humidity", f"{wx['humidity']}%")]
        if air and air["aqi"] is not None:
            rows.append(("AQI (US)", f"{air['aqi']} · {fetch.aqi_label(air['aqi'])}"))
        rows.append(("Sunrise – set", f"{wx['sunrise']:%H:%M} – {wx['sunset']:%H:%M}"))
        fv = font(34, "bold")
        for label, val in rows:
            draw.text((lx0, y), label, font=font(30), fill=MID)
            draw.text((lx1 - draw.textlength(val, font=fv), y - 4), val, font=fv, fill=BLACK)
            y += 56
    else:
        draw.text((lx0, y), "Weather unavailable", font=font(44), fill=MID)

    # Right column: forecast
    y = 56
    if wx:
        cw = (rx1 - rx0) // 3
        for i, dday in enumerate(wx["days"][1:4]):
            x0 = rx0 + i * cw
            c = x0 + cw / 2
            name = dday["date"].strftime("%A")
            f = font(32, "bold")
            draw.text((c - draw.textlength(name, font=f) / 2, y), name, font=f, fill=BLACK)
            icon(draw, fetch.describe(dday["code"])[1], c, y + 95, 100)
            t = f"{dday['high']:.0f}° / {dday['low']:.0f}°"
            f = font(36, "bold")
            draw.text((c - draw.textlength(t, font=f) / 2, y + 150), t, font=f, fill=BLACK)
            if dday["rain"] is not None:
                t = f"Rain {dday['rain']}%"
                f = font(28)
                draw.text((c - draw.textlength(t, font=f) / 2, y + 198), t, font=f, fill=DARK)
            if i:
                draw.line([x0, y + 10, x0, y + 230], fill=LIGHT, width=2)
        y += 262
    draw.rectangle([rx0, y, rx1, y + 1], fill=MID)
    y += 26

    # Right column: headlines
    draw.text((rx0, y), "HEADLINES", font=font(28, "bold"), fill=MID)
    y += 46
    for item in [items[0] for _, items in news if items][:3]:
        draw.ellipse([rx0, y + 16, rx0 + 11, y + 27], fill=BLACK)
        y = text_block(draw, (rx0 + 28, y), item["title"], font(34), rx1 - rx0 - 28,
                       max_lines=3, spacing=1.2) + 14

    # Right column: quote, pinned to the bottom
    if quote:
        text, who = quote
        f = font(31, "italic")
        lines = wrap(draw, f"“{text}”", f, rx1 - rx0 - 10, max_lines=3)
        qy = H - 96 - (len(lines) * 40 + 36)
        if qy > y + 30:
            draw.rectangle([rx0, qy - 24, rx1, qy - 23], fill=MID)
            for i, line in enumerate(lines):
                draw.text((rx0 + 10, qy + i * 40), line, font=f, fill=BLACK)
            a = f"— {who}"
            fa = font(27)
            draw.text((rx1 - draw.textlength(a, font=fa), qy + len(lines) * 40 + 2), a,
                      font=fa, fill=DARK)

    footer(draw, cfg, f"{cfg['location']['name']} · updated {now:%H:%M}")
    return to_eink(img), clocks


def page_news(cfg, now, news):
    img, draw = canvas(cfg)
    W, H = cfg["display"]["width"], cfg["display"]["height"]
    y = header(draw, cfg, "News", now)
    for section, items in news:
        if y > H - 260:
            break
        draw.text((MARGIN, y), section.upper(), font=font(34, "bold"), fill=MID)
        y += 56
        if not items:
            draw.text((MARGIN, y), "Feed unavailable", font=font(34), fill=MID)
            y += 70
        f, fa = font(36, "bold"), font(28)
        step = round(f.size * 1.2)
        for item in items:
            if y > H - 200:
                break
            lines = wrap(draw, item["title"], f, W - 2 * MARGIN, max_lines=2)
            for line in lines:
                draw.text((MARGIN, y), line, font=f, fill=BLACK)
                y += step
            # The age goes at the end of the last line when it fits, else on its own line.
            when = age(item["date"], now)
            if when:
                aw = draw.textlength(when, font=fa)
                if draw.textlength(lines[-1], font=f) + aw + 24 <= W - 2 * MARGIN:
                    draw.text((W - MARGIN - aw, y - step + 8), when, font=fa, fill=MID)
                else:
                    draw.text((MARGIN, y), when, font=fa, fill=MID)
                    y += 36
            y += 18
        y += 8
        if y < H - 160:
            hline(draw, y, cfg, 2, LIGHT)
        y += 30
    footer(draw, cfg, f"updated {now:%H:%M}")
    return to_eink(img)


def sparkline(draw, box, values, fill=BLACK):
    x0, y0, x1, y1 = box
    if len(values) < 2:
        return
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    pts = [(x0 + i * (x1 - x0) / (len(values) - 1), y1 - (v - lo) / span * (y1 - y0))
           for i, v in enumerate(values)]
    draw.line(pts, fill=fill, width=4, joint="curve")
    lx, ly = pts[-1]
    draw.ellipse([lx - 7, ly - 7, lx + 7, ly + 7], fill=fill)


def page_markets(cfg, now, rows):
    """rows: list of (label, quote-dict-or-None, prefix, decimals)."""
    img, draw = canvas(cfg)
    W, H = cfg["display"]["width"], cfg["display"]["height"]
    top = header(draw, cfg, "Markets", now)
    # One column in portrait, a grid of two columns in landscape.
    ncols = 2 if W > H else 1
    per_col = math.ceil(len(rows) / ncols)
    row_h = min(260, (H - top - 100) // per_col)
    col_w = (W - (ncols + 1) * MARGIN) // ncols
    spark_w = min(420, col_w - 460)
    latest = None
    for n, (label, q, prefix, dec) in enumerate(rows):
        x0 = MARGIN + (n // per_col) * (col_w + MARGIN)
        x1 = x0 + col_w
        y = top + (n % per_col) * row_h
        draw.text((x0, y), label, font=font(44, "bold"), fill=BLACK)
        if not q:
            draw.text((x0, y + 70), "unavailable", font=font(40), fill=MID)
        else:
            latest = max(latest, q["time"]) if latest else q["time"]
            price = f"{prefix}{q['price']:,.{dec}f}"
            draw.text((x0, y + 58), price, font=font(80, "bold"), fill=BLACK)
            up = q["change"] >= 0
            ch = f"{abs(q['change']):,.{dec}f}  ({abs(q['pct']):.2f}%)"
            triangle(draw, x0 + 4, y + 176, 30, up, BLACK if up else DARK)
            draw.text((x0 + 48, y + 166), ("+" if up else "–") + ch, font=font(36), fill=DARK)
            sparkline(draw, (x1 - spark_w, y + 40, x1, y + row_h - 70), q["history"])
        draw.rectangle([x0, y + row_h - 30, x1, y + row_h - 29], fill=LIGHT)
    note = "Data: Yahoo Finance (unofficial)"
    if latest:
        latest = latest.astimezone(now.tzinfo)
        note += f" · as of {latest.day} {latest:%b %H:%M}"
    footer(draw, cfg, note)
    return to_eink(img)


def page_photo(cfg, now, photo):
    img, draw = canvas(cfg)
    W, H = cfg["display"]["width"], cfg["display"]["height"]
    clocks = {}
    if photo is None:
        msg = "Add photos to the photos/ folder"
        f = font(48)
        draw.text(((W - draw.textlength(msg, font=f)) / 2, H / 2 - 30), msg, font=f, fill=MID)
    else:
        img.paste(photo, (0, 0))
    if cfg["photo"]["clock_overlay"]:
        _, _, _, ch, _ = clock_metrics("small")
        x, y = W - clock_width("small") - 40, H - ch - 40
        draw.rectangle([x - 20, y - 12, x + clock_width("small") + 20, y + ch + 12], fill=WHITE)
        draw_clock(img, x, y, "small", clock_text(now, cfg))
        clocks["photo"] = ("small", x, y)
    return to_eink(img), clocks


def prepare_photo(path, cfg):
    """Fit a photo to the screen (letterboxed), grayscale, dithered to 16 levels."""
    W, H = cfg["display"]["width"], cfg["display"]["height"]
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        im = ImageOps.grayscale(im)
        im = ImageOps.autocontrast(im, cutoff=1)
        im = ImageOps.pad(im, (W, H), method=Image.Resampling.LANCZOS, color=WHITE)
    return dither(im)
