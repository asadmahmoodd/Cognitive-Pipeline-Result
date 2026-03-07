#!/bin/bash
# =============================================================================
# Entrypoint Script for Research Pipeline
# Runs the metrics pipeline and optionally pushes results to git
# =============================================================================

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Load environment variables from .env file (handles Windows CRLF and quotes)
if [ -f /app/.env ]; then
    # Remove carriage returns, strip quotes, and export
    while IFS='=' read -r key value; do
        # Skip empty lines and comments
        [[ -z "$key" || "$key" =~ ^# ]] && continue
        # Remove carriage return and quotes
        key=$(echo "$key" | tr -d '\r')
        value=$(echo "$value" | tr -d '\r' | sed 's/^["'"'"']//;s/["'"'"']$//')
        export "$key=$value"
    done < /app/.env
fi

# Create log file with timestamp
LOG_DIR="/app/logs"
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="${LOG_DIR}/pipeline_${TIMESTAMP}.log"

# Function to log to both console and file
log() {
    echo -e "$1" | tee -a "$LOG_FILE"
}

# Start logging
log "${GREEN}============================================================${NC}"
log "${GREEN}         Research Pipeline - JUnit Test Coverage${NC}"
log "${GREEN}============================================================${NC}"
log "Pipeline started at: $(date)"
log "Log file: ${LOG_FILE}"
log ""

# Run the metrics pipeline and capture output
log "${YELLOW}Starting metrics pipeline...${NC}"
log "----------------------------------------"

# Run pipeline, capturing both stdout and stderr to log file
python metricsPipeline.py "$@" 2>&1 | tee -a "$LOG_FILE"
PIPELINE_EXIT_CODE=${PIPESTATUS[0]}

log "----------------------------------------"
log "Pipeline finished at: $(date)"
log "Exit code: ${PIPELINE_EXIT_CODE}"

if [ $PIPELINE_EXIT_CODE -ne 0 ]; then
    log "${RED}Pipeline exited with error code: ${PIPELINE_EXIT_CODE}${NC}"
fi

# Create a latest log symlink for easy access
ln -sf "$LOG_FILE" "${LOG_DIR}/latest.log"

# Check if git push is enabled
ENABLE_GIT_PUSH="${ENABLE_GIT_PUSH:-false}"

if [ "$ENABLE_GIT_PUSH" = "true" ] || [ "$ENABLE_GIT_PUSH" = "1" ]; then
    log ""
    log "${YELLOW}Git push is enabled, uploading results...${NC}"
    /app/git_push.sh 2>&1 | tee -a "$LOG_FILE"
else
    log ""
    log "${YELLOW}Git push is disabled. Set ENABLE_GIT_PUSH=true to enable.${NC}"
fi

log ""
log "${GREEN}============================================================${NC}"
log "${GREEN}  Pipeline Complete - Log saved to: ${LOG_FILE}${NC}"
log "${GREEN}============================================================${NC}"

exit $PIPELINE_EXIT_CODE
