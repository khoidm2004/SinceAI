#!/bin/bash
# Reads Artifacts/state.json and prints "difficulty | agent | attempt N | failures N/2".
# Prints an empty line (never an error) if jq is missing or state.json doesn't exist yet.

input=$(cat)

if ! command -v jq >/dev/null 2>&1; then
  echo ""
  exit 0
fi

project_dir=$(echo "$input" | jq -r '.workspace.project_dir // .cwd // "."' 2>/dev/null)
state_file="$project_dir/Artifacts/state.json"

if [ ! -f "$state_file" ]; then
  echo ""
  exit 0
fi

jq -r '
  "\(.difficulty // "-") | \(.current_agent // "-") | attempt \(.attempt // 0) | failures \(.consecutive_failures // 0)/2"
' "$state_file" 2>/dev/null || echo ""
