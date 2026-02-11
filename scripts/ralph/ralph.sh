#!/bin/bash
# Ralph Wiggum - Long-running AI agent loop with timeout support
# Usage: ./ralph.sh [--tool amp|claude] [--timeout seconds] [max_iterations]

set -e

# Parse arguments
TOOL="amp"  # Default to amp for backwards compatibility
MAX_ITERATIONS=10
DELAY=800  # 默认延时 15 分钟
TIMEOUT=1000  # 默认超时 10 分钟（每个任务最大执行时间）

while [[ $# -gt 0 ]]; do
  case $1 in
    --tool)
      TOOL="$2"
      shift 2
      ;;
    --tool=*)
      TOOL="${1#*=}"
      shift
      ;;
    --timeout)
      TIMEOUT="$2"
      shift 2
      ;;
    --timeout=*)
      TIMEOUT="${1#*=}"
      shift
      ;;
    --delay)
      DELAY="$2"
      shift 2
      ;;
    --delay=*)
      DELAY="${1#*=}"
      shift
      ;;
    *)
      # Assume it's max_iterations if it's a number
      if [[ "$1" =~ ^[0-9]+$ ]]; then
        MAX_ITERATIONS="$1"
      fi
      shift
      ;;
  esac
done

# Validate tool choice
if [[ "$TOOL" != "amp" && "$TOOL" != "claude" ]]; then
  echo "Error: Invalid tool '$TOOL'. Must be 'amp' or 'claude'."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRD_FILE="$SCRIPT_DIR/prd.json"
PROGRESS_FILE="$SCRIPT_DIR/progress.txt"
ARCHIVE_DIR="$SCRIPT_DIR/archive"
LAST_BRANCH_FILE="$SCRIPT_DIR/.last-branch"

# Function to log messages with timestamp
log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to count pending stories
count_pending_stories() {
  if [ -f "$PRD_FILE" ]; then
    grep -c '"passes": false' "$PRD_FILE" 2>/dev/null || echo "0"
  else
    echo "0"
  fi
}

# Archive previous run if branch changed
if [ -f "$PRD_FILE" ] && [ -f "$LAST_BRANCH_FILE" ]; then
  CURRENT_BRANCH=$(jq -r '.branchName // empty' "$PRD_FILE" 2>/dev/null || echo "")
  LAST_BRANCH=$(cat "$LAST_BRANCH_FILE" 2>/dev/null || echo "")

  if [ -n "$CURRENT_BRANCH" ] && [ -n "$LAST_BRANCH" ] && [ "$CURRENT_BRANCH" != "$LAST_BRANCH" ]; then
    # Archive the previous run
    DATE=$(date +%Y-%m-%d)
    # Strip "ralph/" prefix from branch name for folder
    FOLDER_NAME=$(echo "$LAST_BRANCH" | sed 's|^ralph/||')
    ARCHIVE_FOLDER="$ARCHIVE_DIR/$DATE-$FOLDER_NAME"

    log "Archiving previous run: $LAST_BRANCH"
    mkdir -p "$ARCHIVE_FOLDER"
    [ -f "$PRD_FILE" ] && cp "$PRD_FILE" "$ARCHIVE_FOLDER/"
    [ -f "$PROGRESS_FILE" ] && cp "$PROGRESS_FILE" "$ARCHIVE_FOLDER/"
    log "   Archived to: $ARCHIVE_FOLDER"

    # Reset progress file for new run
    echo "# Ralph Progress Log" > "$PROGRESS_FILE"
    echo "Started: $(date)" >> "$PROGRESS_FILE"
    echo "---" >> "$PROGRESS_FILE"
  fi
fi

# Track current branch
if [ -f "$PRD_FILE" ]; then
  CURRENT_BRANCH=$(jq -r '.branchName // empty' "$PRD_FILE" 2>/dev/null || echo "")
  if [ -n "$CURRENT_BRANCH" ]; then
    echo "$CURRENT_BRANCH" > "$LAST_BRANCH_FILE"
  fi
fi

# Initialize progress file if it doesn't exist
if [ ! -f "$PROGRESS_FILE" ]; then
  echo "# Ralph Progress Log" > "$PROGRESS_FILE"
  echo "Started: $(date)" >> "$PROGRESS_FILE"
  echo "---" >> "$PROGRESS_FILE"
fi

# Display startup information
log "Starting Ralph"
log "  Tool: $TOOL"
log "  Max iterations: $MAX_ITERATIONS"
log "  Timeout per task: ${TIMEOUT}s"
log "  Delay between iterations: ${DELAY}s"
log "  Pending stories: $(count_pending_stories)"

for i in $(seq 1 $MAX_ITERATIONS); do

  if [ "$i" -gt 1 ] && [ "$DELAY" -gt 0 ]; then
    log "Waiting ${DELAY}s before iteration $i..."
    sleep "$DELAY"
  fi

  echo ""
  echo "==============================================================="
  log "Ralph Iteration $i of $MAX_ITERATIONS ($TOOL)"
  log "Pending stories remaining: $(count_pending_stories)"
  echo "==============================================================="

  # Run the selected tool with the ralph prompt and timeout
  if [[ "$TOOL" == "amp" ]]; then
    if command -v timeout &> /dev/null; then
      log "Running amp with ${TIMEOUT}s timeout..."
      OUTPUT=$(timeout "$TIMEOUT" bash -c "cat '$SCRIPT_DIR/prompt.md' | amp --dangerously-allow-all 2>&1" | tee /dev/stderr) || {
        EXIT_CODE=$?
        if [ $EXIT_CODE -eq 124 ]; then
          log "WARNING: amp timed out after ${TIMEOUT}s, continuing to next iteration..."
          OUTPUT=""
        fi
      }
    else
      log "Running amp (no timeout available)..."
      OUTPUT=$(cat "$SCRIPT_DIR/prompt.md" | amp --dangerously-allow-all 2>&1 | tee /dev/stderr) || true
    fi
  else
    # Claude Code: use --dangerously-skip-permissions for autonomous operation
    if command -v timeout &> /dev/null; then
      log "Running claude with ${TIMEOUT}s timeout..."
      OUTPUT=$(timeout "$TIMEOUT" bash -c "claude --dangerously-skip-permissions --print < '$SCRIPT_DIR/CLAUDE.md' 2>&1" | tee /dev/stderr) || {
        EXIT_CODE=$?
        if [ $EXIT_CODE -eq 124 ]; then
          log "WARNING: claude timed out after ${TIMEOUT}s, continuing to next iteration..."
          OUTPUT=""
        fi
      }
    else
      log "Running claude (no timeout available)..."
      OUTPUT=$(claude --dangerously-skip-permissions --print < "$SCRIPT_DIR/CLAUDE.md" 2>&1 | tee /dev/stderr) || true
    fi
  fi

  # Check for completion signal
  if echo "$OUTPUT" | grep -q "<promise>COMPLETE</promise>"; then
    echo ""
    log "Ralph completed all tasks!"
    log "Completed at iteration $i of $MAX_ITERATIONS"
    exit 0
  fi

  log "Iteration $i complete. Continuing..."
  sleep 2
done

echo ""
log "Ralph reached max iterations ($MAX_ITERATIONS) without completing all tasks."
log "Pending stories remaining: $(count_pending_stories)"
log "Check $PROGRESS_FILE for status."
exit 1
