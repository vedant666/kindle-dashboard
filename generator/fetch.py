"""Data fetchers. Every fetcher returns None (or an empty list) on failure so one
broken source never stops the other pages from rendering."""

import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape

UA = "Mozilla/5.0 (kindle-dashboard; +https://github.com)"


def _get(url, timeout=20, tries=2):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(3)


def _get_json(url, **params):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    return json.loads(_get(url))


def _warn(what, err):
    print(f"warning: {what} failed: {err}", file=sys.stderr)


# ---------------------------------------------------------------- weather

def weather(lat, lon, tz):
    try:
        d = _get_json(
            "https://api.open-meteo.com/v1/forecast",
            latitude=lat, longitude=lon, timezone=tz, forecast_days=4,
            current="temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
            daily="weather_code,temperature_2m_max,temperature_2m_min,"
                  "precipitation_probability_max,sunrise,sunset",
        )
    except Exception as e:
        _warn("weather", e)
        return None
    cur, day = d["current"], d["daily"]
    days = [
        {
            "date": datetime.fromisoformat(day["time"][i]),
            "code": day["weather_code"][i],
            "high": day["temperature_2m_max"][i],
            "low": day["temperature_2m_min"][i],
            "rain": day["precipitation_probability_max"][i],
        }
        for i in range(len(day["time"]))
    ]
    return {
        "temp": cur["temperature_2m"],
        "feels": cur["apparent_temperature"],
        "humidity": cur["relative_humidity_2m"],
        "wind": cur["wind_speed_10m"],
        "code": cur["weather_code"],
        "sunrise": datetime.fromisoformat(day["sunrise"][0]),
        "sunset": datetime.fromisoformat(day["sunset"][0]),
        "days": days,
    }


def air_quality(lat, lon, tz):
    try:
        d = _get_json(
            "https://air-quality-api.open-meteo.com/v1/air-quality",
            latitude=lat, longitude=lon, timezone=tz, current="us_aqi,pm2_5",
        )
        return {"aqi": d["current"]["us_aqi"], "pm25": d["current"]["pm2_5"]}
    except Exception as e:
        _warn("air quality", e)
        return None


WMO = {
    0: ("Clear", "sun"), 1: ("Mainly clear", "sun"), 2: ("Partly cloudy", "partly"),
    3: ("Overcast", "cloud"), 45: ("Fog", "fog"), 48: ("Rime fog", "fog"),
    51: ("Light drizzle", "rain"), 53: ("Drizzle", "rain"), 55: ("Heavy drizzle", "rain"),
    56: ("Freezing drizzle", "rain"), 57: ("Freezing drizzle", "rain"),
    61: ("Light rain", "rain"), 63: ("Rain", "rain"), 65: ("Heavy rain", "rain"),
    66: ("Freezing rain", "rain"), 67: ("Freezing rain", "rain"),
    71: ("Light snow", "snow"), 73: ("Snow", "snow"), 75: ("Heavy snow", "snow"),
    77: ("Snow grains", "snow"), 80: ("Showers", "rain"), 81: ("Showers", "rain"),
    82: ("Heavy showers", "rain"), 85: ("Snow showers", "snow"), 86: ("Snow showers", "snow"),
    95: ("Thunderstorm", "storm"), 96: ("Thunderstorm", "storm"), 99: ("Thunderstorm", "storm"),
}


def describe(code):
    return WMO.get(code, ("—", "cloud"))


def aqi_label(aqi):
    for limit, label in ((50, "Good"), (100, "Moderate"), (150, "Unhealthy for some"),
                         (200, "Unhealthy"), (300, "Very unhealthy")):
        if aqi <= limit:
            return label
    return "Hazardous"


# ---------------------------------------------------------------- news

_ATOM = "{http://www.w3.org/2005/Atom}"


def _clean(text):
    text = unescape(re.sub(r"<[^>]+>", "", text or ""))
    return re.sub(r"\s+", " ", text).strip()


def feed(url, limit):
    try:
        root = ET.fromstring(_get(url))
    except Exception as e:
        _warn(f"feed {url}", e)
        return []
    items = []
    for it in root.iter("item"):  # RSS 2.0
        items.append({"title": _clean(it.findtext("title")),
                      "date": _parse_date(it.findtext("pubDate"))})
    for it in root.iter(f"{_ATOM}entry"):  # Atom
        items.append({"title": _clean(it.findtext(f"{_ATOM}title")),
                      "date": _parse_date(it.findtext(f"{_ATOM}updated"))})
    return [i for i in items if i["title"]][:limit]


def _parse_date(s):
    if not s:
        return None
    try:
        return parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None


# ---------------------------------------------------------------- markets

def quote(symbol):
    """Last price and change vs previous close from Yahoo's chart endpoint."""
    try:
        d = _get_json(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}",
            range="1mo", interval="1d",
        )
        res = d["chart"]["result"][0]
        meta = res["meta"]
        closes = [c for c in res["indicators"]["quote"][0]["close"] if c is not None]
        price = meta["regularMarketPrice"]
        # The latest session's bar often has no close yet, so it is missing from
        # `closes`; only treat closes[-1] as today when it matches the live price.
        if closes and abs(closes[-1] - price) < 1e-6 * max(price, 1):
            prev = closes[-2] if len(closes) >= 2 else price
        else:
            prev = closes[-1] if closes else price
            closes.append(price)
        return {
            "price": price,
            "change": price - prev,
            "pct": (price - prev) / prev * 100 if prev else 0.0,
            "history": closes[-20:],
            "time": datetime.fromtimestamp(meta["regularMarketTime"], timezone.utc),
        }
    except Exception as e:
        _warn(f"quote {symbol}", e)
        return None
