#!/bin/bash
cd "$(dirname "$0")"

if command -v caffeinate >/dev/null 2>&1; then
  caffeinate -dims bash scripts/run_forever.sh
else
  bash scripts/run_forever.sh
fi
