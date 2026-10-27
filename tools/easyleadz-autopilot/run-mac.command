#!/bin/sh
# ================== SETTINGS - edit these, then save ==================
SHEET_URL=""
TOKEN=""
CSV_FILE="leads.csv"     # empty = read leads from the Google Sheet
MAX=170
PER_MINUTE=3
# =======================================================================
cd "$(dirname "$0")"
set -- --max "$MAX" --per-minute "$PER_MINUTE"
[ -n "$SHEET_URL" ] && set -- "$@" --sheet "$SHEET_URL" --token "$TOKEN"
[ -n "$CSV_FILE" ] && set -- "$CSV_FILE" "$@"
node autopilot.mjs "$@"
