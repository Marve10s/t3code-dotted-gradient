#!/bin/sh
set -eu

LABEL="local.dither-live"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$PLIST"

echo "Rotation stopped. Dither Live stays on its current background until you pick another theme in T3 Code settings."
