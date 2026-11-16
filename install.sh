#!/bin/sh
set -eu

ROOT="$(cd "$(dirname "$0")" && pwd)"
LABEL="local.dither-live"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/dither-live.log"
MINUTES="${1:-20}"

if [ "$(uname)" != "Darwin" ]; then
  echo "The rotation helper runs on macOS only. Apply a single theme with: t3 theme set --id dither-live themes/01-dither.json" >&2
  exit 1
fi

case "$MINUTES" in
  ''|*[!0-9]*|0) echo "Usage: ./install.sh [minutes]" >&2; exit 1 ;;
esac
SECONDS_BETWEEN=$((MINUTES * 60))

xml() {
  printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'
}

DITHER_LIVE_INTERVAL="$SECONDS_BETWEEN" sh "$ROOT/rotate.sh" --start

mkdir -p "$(dirname "$PLIST")" "$(dirname "$LOG")"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/sh</string>
    <string>$(xml "$ROOT/rotate.sh")</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>DITHER_LIVE_INTERVAL</key>
    <string>$SECONDS_BETWEEN</string>
  </dict>
  <key>StartInterval</key>
  <integer>$SECONDS_BETWEEN</integer>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$(xml "$LOG")</string>
  <key>StandardErrorPath</key>
  <string>$(xml "$LOG")</string>
</dict>
</plist>
EOF

DOMAIN="gui/$(id -u)"
launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST"

echo "Dither Live is on. The background changes every $MINUTES minutes. Log: $LOG"
