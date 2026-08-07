#!/bin/bash
# Same DISPLAY/XAUTHORITY auto-detection approach as launch-hud.sh -
# see that file for why this method (scanning process environments)
# is used instead of loginctl or parsing Xorg's command line.

set -e

DETECTED_DISPLAY=""
DETECTED_AUTH=""

for pid in $(pgrep -u "$USER"); do
    ENV_FILE="/proc/$pid/environ"
    if [ -r "$ENV_FILE" ]; then
        VALUE=$(tr '\0' '\n' < "$ENV_FILE" 2>/dev/null | grep '^DISPLAY=' | cut -d= -f2-)
        if [ -n "$VALUE" ]; then
            DETECTED_DISPLAY="$VALUE"
            AUTH_VALUE=$(tr '\0' '\n' < "$ENV_FILE" 2>/dev/null | grep '^XAUTHORITY=' | cut -d= -f2-)
            if [ -n "$AUTH_VALUE" ]; then
                DETECTED_AUTH="$AUTH_VALUE"
            fi
            break
        fi
    fi
done

export DISPLAY="${DETECTED_DISPLAY:-:0}"

if [ -n "$DETECTED_AUTH" ] && [ -f "$DETECTED_AUTH" ]; then
    export XAUTHORITY="$DETECTED_AUTH"
else
    UID_NUM=$(id -u)
    for candidate in "/run/user/$UID_NUM/gdm/Xauthority" "$HOME/.Xauthority"; do
        if [ -f "$candidate" ]; then
            export XAUTHORITY="$candidate"
            break
        fi
    done
fi

echo "[launch-device-switcher] Using DISPLAY=$DISPLAY XAUTHORITY=$XAUTHORITY"

exec /home/prad/miniconda3/envs/aria/bin/python /home/prad/Desktop/Extra/aria/hud/device-switcher.py