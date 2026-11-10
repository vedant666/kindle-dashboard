# Kindle-side settings. Edit over USB; changes apply the next time a dashboard scriptlet is opened.

# Your GitHub Pages address (https://<github-username>.github.io/<repo-name>).
BASE_URL="https://vedant666.github.io/kindle-dashboard"

# India Standard Time in POSIX form (UTC+05:30).
TZ_POSIX="IST-5:30"
CLOCK_24H=0

# Starting orientation: portrait or landscape. Tapping the bottom-left corner switches it
# and the choice is remembered (in dashboard/orientation).
ORIENTATION=portrait

# Frontlight while the dashboard runs: blank = leave as is, 0 = off, up to 25 = brightest.
# Tapping the top-right corner steps through FL_LEVELS and remembers the choice (in
# dashboard/frontlight). Your normal reading brightness comes back when you exit.
FRONTLIGHT=0
FL_LEVELS="0 3 8 15 25"

# Minutes between downloads, and between pages in the "rotate" and "photos" modes.
REFRESH_MIN=15
ROTATE_MIN=5

# 1 = stop the Kindle's own interface while the dashboard runs (recommended: taps then only
# switch pages, and the power button exits). 0 = leave it running underneath.
STOP_GUI=1

# Touchscreen input device. Blank = detect automatically.
TOUCH_DEV=""
