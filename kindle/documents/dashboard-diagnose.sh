#!/bin/sh
# Name: Dashboard - Diagnose input
# Author: Kindle Dashboard
# DontUseFBInk
# Records which input device fires on a screen tap and on a power-button press,
# and which powerd events arrive, into /mnt/us/dashboard/diag.txt.

OUT=/mnt/us/dashboard/diag.txt
FBINK=/mnt/us/libkh/bin/fbink
say() { "$FBINK" -q -c -f -m -M "$1"; }

{
    echo "== $(date)"; uname -a
    echo "== /proc/bus/input/devices"; cat /proc/bus/input/devices
    echo "== /dev/input"; ls -l /dev/input
    echo "== tools"; for t in lipc-wait-event lipc-get-prop timeout od hexdump evtest; do echo "$t: $(command -v $t)"; done
} > "$OUT" 2>&1

watch_all() {  # $1 = phase name; logs every device that delivers events within 10 s
    pids=
    for d in /dev/input/event*; do
        ( dd if="$d" bs=16 count=1 of=/dev/null 2>/dev/null && echo "$1: $d fired" >> "$OUT" ) &
        pids="$pids $!"
    done
    sleep 10
    for p in $pids; do kill "$p" 2>/dev/null; done
    killall dd 2>/dev/null
}

say "Diagnose 1/2: TAP THE SCREEN a few times now (10 s)"
sleep 2
watch_all tap

say "Diagnose 2/2: press the POWER button once now, then press it again to wake"
lipc-wait-event -m -s 25 com.lab126.powerd goingToScreenSaver,outOfScreenSaver,suspending,resuming,readyToSuspend,wakeupFromSuspend,t1TimerReset >> "$OUT" 2>&1 &
sleep 1
watch_all power
sleep 15
echo "== done $(date)" >> "$OUT"
say "Diagnose finished. Plug the Kindle into the PC."
