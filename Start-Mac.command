#!/bin/sh
cd "$(dirname "$0")" || exit 1
if ! command -v uv >/dev/null 2>&1; then
  PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
  export PATH
fi
uv run --locked python server.py start
result=$?
if [ "$result" -ne 0 ]; then
  printf '\nStartup failed. Keep the error above; see README troubleshooting. Press Enter to close.\n'
  read -r answer
fi
exit "$result"
