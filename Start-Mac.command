#!/bin/sh
cd "$(dirname "$0")" || exit 1
uv run --locked python server.py start
