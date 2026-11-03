#!/bin/sh
# Kindle side of the dashboard. Downloads the page images that GitHub Actions renders,
# shows them full screen, and pastes clock digit tiles every minute so the time is exact.
#
#   dashboard.sh start <home|news|markets|photos|rotate>    (the scriptlets call this)
#   dashboard.sh stop
#
# While it runs: tap the screen for the next page, press the power button to exit.
# If anything ever gets stuck, hold the power button ~40 s to reboot: nothing here
# starts at boot, so a reboot always brings back the normal Kindle.

DIR=${DASH_DIR:-/mnt/us/dashboard}
. "$DIR/settings.sh"
CACHE="$DIR/cache"
RUN=/tmp/dashboard
LOG="$DIR/dashboard.log"
mkdir -p "$CACHE/tiles/big" "$CACHE/tiles/small" "$RUN" "$DIR/photos"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }

# ---------------------------------------------------------------- screen

find_fbink() {
    for f in "$(command -v fbink)" /mnt/us/libkh/bin/fbink /usr/bin/fbink /usr/local/bin/fbink \
             /mnt/us/koreader/fbink /mnt/us/extensions/MRInstaller/bin/KHF/fbink; do
        [ -n "$f" ] && [ -x "$f" ] && { echo "$f"; return; }
    done
}
FBINK=$(find_fbink)

show_full() {      # $1 = png; full flashing refresh, clears ghosting
    if [ -n "$FBINK" ]; then "$FBINK" -q -c -f -g file="$1"
    else eips -c; eips -f -g "$1"; fi
}

show_at() {        # $1 = png, $2 = x, $3 = y; quick partial refresh
    if [ -n "$FBINK" ]; then "$FBINK" -q -g file="$1",x="$2",y="$3"
    else eips -g "$1" -x "$2" -y "$3"; fi
}

message() {
    if [ -n "$FBINK" ]; then "$FBINK" -q -c -f -m -M "$1"
    else eips -c; eips 5 30 "$1"; fi
}

gui() {            # gui start|stop
    if command -v "$1" >/dev/null 2>&1; then "$1" lab126_gui
    else /etc/init.d/framework "$1"; fi
}

# ---------------------------------------------------------------- downloads

fetch() {          # $1 = url, $2 = destination; replaces the file only on success
    if command -v curl >/dev/null 2>&1; then
        curl -fsS -m 60 -o "$2.part" "$1?t=$(date +%s)"
    else
        wget -q -T 60 -O "$2.part" "$1?t=$(date +%s)"
    fi && mv "$2.part" "$2" || { rm -f "$2.part"; return 1; }
}

refresh() {        # returns 0 when new images were downloaded
    if ! fetch "$BASE_URL/updated.txt" "$RUN/updated.txt"; then
        log "download failed; making sure Wi-Fi is on"
        lipc-set-prop com.lab126.cmd wirelessEnable 1 2>/dev/null
        return 1
    fi
    cmp -s "$RUN/updated.txt" "$CACHE/updated.txt" && return 1
    fetch "$BASE_URL/pages.txt" "$CACHE/pages.txt" || return 1
    fetch "$BASE_URL/clock.txt" "$CACHE/clock.txt"
    for p in $(cat "$CACHE/pages.txt"); do
        fetch "$BASE_URL/$p.png" "$CACHE/$p.png" || log "failed to get $p.png"
    done
    for s in big small; do
        for c in 0 1 2 3 4 5 6 7 8 9 colon blank; do
            fetch "$BASE_URL/tiles/$s/$c.png" "$CACHE/tiles/$s/$c.png"
        done
    done
    cp "$RUN/updated.txt" "$CACHE/updated.txt"
    log "downloaded pages rendered at $(cat "$CACHE/updated.txt")"
    return 0
}

# ---------------------------------------------------------------- pages

build_list() {     # sets LIST, one page per line
    web=$(cat "$CACHE/pages.txt" 2>/dev/null)
    locals=$(cd "$DIR/photos" && ls *.png 2>/dev/null | sed 's/^/local:/')
    photos=$(printf '%s\n%s\n' "$(echo "$web" | grep '^photo-[0-9]')" "$locals" | grep .)
    [ -z "$photos" ] && photos=$(echo "$web" | grep -x photo-empty)
    if [ "$MODE" = photos ]; then
        LIST=$photos
    else
        LIST=$(printf '%s\n%s\n' "$(echo "$web" | grep -v '^photo-')" "$photos" | grep .)
    fi
}

next_page() {
    n=$(echo "$LIST" | grep -n -x -F "$PAGE" | head -n1 | cut -d: -f1)
    total=$(echo "$LIST" | grep -c .)
    if [ -z "$n" ] || [ "$n" -ge "$total" ]; then PAGE=$(echo "$LIST" | head -n1)
    else PAGE=$(echo "$LIST" | sed -n "$((n + 1))p"); fi
}

page_file() {
    case "$1" in
        local:*) echo "$DIR/photos/${1#local:}" ;;
        *) echo "$CACHE/$1.png" ;;
    esac
}

draw_clock() {     # pastes only the digits that changed since the last call
    case "$PAGE" in photo-*|local:*) key=photo ;; *) key=$PAGE ;; esac
    line=$(grep "^$key " "$CACHE/clock.txt" 2>/dev/null | head -n1)
    [ -z "$line" ] && return
    set -- $line   # prefix size x y digit_w colon_w
    size=$2; x=$3; y=$4; dw=$5; cw=$6
    tiles="$CACHE/tiles/$size"
    if [ "$CLOCK_24H" = 1 ]; then t=$(TZ="$TZ_POSIX" date +%H%M)
    else t=$(TZ="$TZ_POSIX" date +%I%M); fi
    set -- $(echo "$t" | sed 's/./& /g')
    [ "$CLOCK_24H" != 1 ] && [ "$1" = 0 ] && set -- blank "$2" "$3" "$4"
    offs="0 $dw $((2 * dw + cw)) $((3 * dw + cw))"
    i=0
    for off in $offs; do
        i=$((i + 1))
        eval "c=\${$i}; old=\${LAST_$i}"
        if [ "$c" != "$old" ]; then
            show_at "$tiles/$c.png" $((x + off)) "$y"
            eval "LAST_$i=\$c"
        fi
    done
    if [ -z "$LAST_COLON" ]; then
        show_at "$tiles/colon.png" $((x + 2 * dw)) "$y"
        LAST_COLON=1
    fi
}

draw_page() {
    f=$(page_file "$PAGE")
    if [ -f "$f" ]; then
        show_full "$f"
        LAST_1=; LAST_2=; LAST_3=; LAST_4=; LAST_COLON=
        draw_clock
    else
        message "Waiting for dashboard images... check BASE_URL in settings.sh"
    fi
}

# ---------------------------------------------------------------- input

input_device() {   # $1 = regex for the device name; prints /dev/input/eventN
    # On the PW5 the lines look like: N: Name="pt_mt"  /  H: Handlers=event1 perfmgr
    awk -v re="$1" '/^N:/ { t = (tolower($0) ~ re) }
         /^H:/ && t && match($0, /event[0-9]+/) { print "/dev/input/" substr($0, RSTART, RLENGTH); exit }' \
        /proc/bus/input/devices
}

watch_touch() {    # one tap is a burst of events; signal the main loop once per burst
    dev=${TOUCH_DEV:-$(input_device 'touch|_mt|cyttsp|zforce|elan')}
    [ -z "$dev" ] && { log "no touchscreen found; set TOUCH_DEV"; return; }
    log "touch input: $dev"
    last=0
    while :; do
        dd if="$dev" of=/dev/null bs=16 count=1 2>/dev/null || { sleep 5; continue; }
        now=$(date +%s)
        [ $((now - last)) -ge 2 ] && kill -USR1 "$MAIN" 2>/dev/null
        last=$now
    done
}

watch_power() {    # read the power key directly; powerd sends no events while the GUI is stopped
    dev=$(input_device 'pwrkey|power|onkey')
    if [ -n "$dev" ]; then
        log "power key: $dev"
        dd if="$dev" of=/dev/null bs=16 count=1 2>/dev/null
    else
        log "no power key device found; falling back to powerd events"
        lipc-wait-event com.lab126.powerd goingToScreenSaver,suspending >/dev/null 2>&1
    fi
    log "power button pressed"
    kill -TERM "$MAIN" 2>/dev/null
}

watch_usb() {      # USB mode takes /mnt/us away, so hand the Kindle back to its own interface
    lipc-wait-event com.lab126.hal usbPlugIn,usbConfigured >/dev/null 2>&1 || return
    log "USB connected"
    kill -TERM "$MAIN" 2>/dev/null
}

# ---------------------------------------------------------------- main loop

cleanup() {
    for p in $WATCHERS; do kill "$p" 2>/dev/null; done
    # The watchers' blocked readers outlive them; stop those too.
    for p in $( (ps -o pid,args 2>/dev/null || ps) | awk '/dd if=\/dev\/input|lipc-wait-event com.lab126.(hal|powerd)/ && !/awk/ { print $1 }'); do
        kill "$p" 2>/dev/null
    done
    [ -n "$NAP" ] && kill "$NAP" 2>/dev/null
    lipc-set-prop com.lab126.powerd preventScreenSaver 0 2>/dev/null
    [ "$STOP_GUI" = 1 ] && gui start
    rm -f "$RUN/pid"
    log "stopped"
}

nap() {            # sleep that a tap (USR1) can cut short
    [ "$TAPPED" = 1 ] && return
    sleep "$1" & NAP=$!
    wait "$NAP"
    kill "$NAP" 2>/dev/null
    NAP=
}

loop() {
    MODE=$1
    MAIN=$$
    echo "$MAIN" > "$RUN/pid"
    log "starting in $MODE mode (fbink: ${FBINK:-none, using eips})"
    TAPPED=0
    trap 'TAPPED=1' USR1
    trap 'cleanup; exit 0' TERM INT

    lipc-set-prop com.lab126.powerd preventScreenSaver 1
    if [ "$STOP_GUI" = 1 ]; then gui stop; sleep 2; fi
    message "Loading dashboard..."

    watch_touch & WATCHERS=$!
    watch_power & WATCHERS="$WATCHERS $!"
    watch_usb & WATCHERS="$WATCHERS $!"

    refresh
    build_list
    case "$MODE" in
        rotate|photos) PAGE=$(echo "$LIST" | head -n1) ;;
        *) PAGE=$MODE; echo "$LIST" | grep -q -x -F "$PAGE" || PAGE=$(echo "$LIST" | head -n1) ;;
    esac
    draw_page
    last_refresh=$(date +%s); last_rotate=$last_refresh

    while :; do
        s=$(date +%S); nap $((60 - ${s#0}))
        # Storage gone means USB mode started without the event reaching us.
        [ -f "$DIR/settings.sh" ] || { cleanup; exit 0; }
        if [ "$TAPPED" = 1 ]; then
            TAPPED=0
            build_list; next_page; draw_page
            last_rotate=$(date +%s)
            continue
        fi
        now=$(date +%s); full=0
        if [ $((now - last_refresh)) -ge $((REFRESH_MIN * 60)) ]; then
            last_refresh=$now
            refresh && { build_list; full=1; }
        fi
        case "$MODE" in rotate|photos)
            if [ $((now - last_rotate)) -ge $((ROTATE_MIN * 60)) ]; then
                last_rotate=$now; next_page; full=1
            fi ;;
        esac
        [ "$(date +%M)" = 00 ] && full=1      # hourly flash to clear e-ink ghosting
        if [ "$full" = 1 ]; then draw_page; else draw_clock; fi
    done
}

stop_running() {
    pid=$(cat "$RUN/pid" 2>/dev/null)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        kill -TERM "$pid"
        sleep 3
    fi
}

case "$1" in
    start)
        stop_running
        [ -f "$LOG" ] && [ "$(wc -c < "$LOG")" -gt 200000 ] && mv "$LOG" "$LOG.old"
        setsid sh "$0" loop "${2:-home}" >> "$LOG" 2>&1 < /dev/null &
        ;;
    loop) loop "${2:-home}" ;;
    stop) stop_running ;;
    *) echo "usage: $0 start <home|news|markets|photos|rotate> | stop" ;;
esac
