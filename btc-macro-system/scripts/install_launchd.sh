#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
LABEL=${LABEL:-local.btc-macro-system.update}
HOUR=${1:-8}
MINUTE=${2:-10}
TARGET="$HOME/Library/LaunchAgents/$LABEL.plist"

mkdir -p "$HOME/Library/LaunchAgents" "$ROOT_DIR/logs"

cat > "$TARGET" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$ROOT_DIR/scripts/update_once.sh</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$ROOT_DIR</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>$HOUR</integer>
    <key>Minute</key>
    <integer>$MINUTE</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>$ROOT_DIR/logs/update.log</string>
  <key>StandardErrorPath</key>
  <string>$ROOT_DIR/logs/update.err</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
</dict>
</plist>
EOF

launchctl unload "$TARGET" 2>/dev/null || true
launchctl load "$TARGET"

echo "Installed $LABEL at $TARGET"
echo "Schedule: daily at $(printf '%02d:%02d' "$HOUR" "$MINUTE") local time"
