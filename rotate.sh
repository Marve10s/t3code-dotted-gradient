#!/bin/sh
set -eu

ROOT="$(cd "$(dirname "$0")" && pwd)"
THEME_ID="dither-live"
INTERVAL_SECONDS="${DITHER_LIVE_INTERVAL:-1200}"
T3="${T3_CLI:-${T3CODE_HOME:-$HOME/.t3}/bin/t3}"

if [ ! -x "$T3" ]; then
  echo "No t3 CLI at $T3. Open T3 Code once so it writes the CLI, or set T3_CLI." >&2
  exit 1
fi

current=$("$T3" theme show | sed -n 's/^Environment theme: "\(.*\)"\.$/\1/p')
if [ "$current" != "$THEME_ID" ] && [ "${1:-}" != "--start" ]; then
  exit 0
fi

set -- "$ROOT"/themes/*.json
index=$(( $(date +%s) / INTERVAL_SECONDS % $# ))
shift "$index"
"$T3" theme set --id "$THEME_ID" "$1"
