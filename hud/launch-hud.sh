#!/bin/bash
# Auto-detects DISPLAY and XAUTHORITY by scanning the environment of your
# own running processes. This is the most reliable method regardless of how
# X was launched (e.g. GDM's -displayfd pattern doesn't put the display
# number in the process command line at all, so parsing Xorg's args directly
# doesn't work here) - desktop session processes like gnome-shell always
# have DISPLAY correctly exported in their own environment.

set -e

DETECTED_DISPLAY=""
DETECTED_AUTH=""

for pid in $(pgrep -u "$USER"); do
    ENV_FILE="/proc/$pid/environ"
    if [ -r "$ENV_FILE" ]; then
        VALUE=$(tr '\0' '\n' < "$ENV_FILE" 2>/dev/null | grep '^DISPLAY=' | cut -d= -f2-)
        if [ -n "$VALUE" ]; then
            DETECTED_DISPLAY="$VALUE"
            # Grab XAUTHORITY from the same process while we're at it, if it has one
            AUTH_VALUE=$(tr '\0' '\n' < "$ENV_FILE" 2>/dev/null | grep '^XAUTHORITY=' | cut -d= -f2-)
            if [ -n "$AUTH_VALUE" ]; then
                DETECTED_AUTH="$AUTH_VALUE"
            fi
            break
        fi
    fi
done

if [ -n "$DETECTED_DISPLAY" ]; then
    export DISPLAY="$DETECTED_DISPLAY"
else
    export DISPLAY=":0"  # last-resort fallback
fi

if [ -n "$DETECTED_AUTH" ] && [ -f "$DETECTED_AUTH" ]; then
    export XAUTHORITY="$DETECTED_AUTH"
else
    # Fallback chain if no process had XAUTHORITY explicitly set
    UID_NUM=$(id -u)
    for candidate in "/run/user/$UID_NUM/gdm/Xauthority" "$HOME/.Xauthority"; do
        if [ -f "$candidate" ]; then
            export XAUTHORITY="$candidate"
            break
        fi
    done
fi

echo "[launch-hud] Using DISPLAY=$DISPLAY XAUTHORITY=$XAUTHORITY"

exec /home/prad/miniconda3/envs/aria/bin/python /home/prad/Desktop/Extra/aria/hud/hud.py