#!/bin/bash
# =============================================================================
# Git Push Automation Script for Research Pipeline
# Pushes generated CSV files, logs, and source files to git repository
# Uses HTTPS + Personal Access Token for authentication (no SSH required)
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Git Push - Results Upload${NC}"
echo -e "${GREEN}============================================${NC}"

# Configuration from environment variables (with defaults)
GIT_TOKEN="${GIT_TOKEN:-}"
GIT_USERNAME="${GIT_USERNAME:-asadmahmoodd}"
GIT_REPO="${GIT_REPO:-Cognitive-Pipeline-Result}"
GIT_BRANCH="${GIT_BRANCH:-main}"
GIT_USER_NAME="${GIT_USER_NAME:-Research Pipeline Bot}"
GIT_USER_EMAIL="${GIT_USER_EMAIL:-pipeline@automated.local}"
RESULTS_DIR="${RESULTS_DIR:-/app}"
LOGS_DIR="${LOGS_DIR:-/app/logs}"

# Check if token is available
if [ -z "$GIT_TOKEN" ]; then
    echo -e "${RED}ERROR: GIT_TOKEN is not set!${NC}"
    echo "Please provide GIT_TOKEN in the .env file."
    exit 1
fi

# Build the HTTPS URL with token authentication
GIT_REPO_URL="https://${GIT_TOKEN}@github.com/${GIT_USERNAME}/${GIT_REPO}.git"

# Configure git
echo -e "${YELLOW}Configuring git...${NC}"
git config --global user.name "$GIT_USER_NAME"
git config --global user.email "$GIT_USER_EMAIL"
git config --global init.defaultBranch main

# Create a temporary directory for git operations
TEMP_REPO="/tmp/git_repo_$$"
mkdir -p "$TEMP_REPO"
cd "$TEMP_REPO"

# Clone the repository (shallow clone for speed)
echo -e "${YELLOW}Cloning repository...${NC}"
if ! git clone --depth 1 --branch "$GIT_BRANCH" "$GIT_REPO_URL" repo 2>/dev/null; then
    echo -e "${YELLOW}Branch $GIT_BRANCH not found, cloning default branch...${NC}"
    git clone --depth 1 "$GIT_REPO_URL" repo
fi
cd repo

# Create directories if they don't exist
RESULTS_SUBDIR="results"
LOGS_SUBDIR="logs"
SOURCE_SUBDIR="generated_tests"
mkdir -p "$RESULTS_SUBDIR" "$LOGS_SUBDIR" "$SOURCE_SUBDIR"

FILES_COPIED=0

# ===== Copy CSV files =====
echo -e "${YELLOW}Copying CSV files...${NC}"
for csv_file in coverage_results.csv coverage_summary.csv; do
    if [ -f "${RESULTS_DIR}/${csv_file}" ]; then
        cp "${RESULTS_DIR}/${csv_file}" "${RESULTS_SUBDIR}/"
        echo -e "  ${GREEN}✓${NC} Copied ${csv_file}"
        FILES_COPIED=$((FILES_COPIED + 1))
    else
        echo -e "  ${YELLOW}⚠${NC} ${csv_file} not found, skipping"
    fi
done

# ===== Copy Log files =====
echo -e "${YELLOW}Copying log files...${NC}"
if [ -d "${LOGS_DIR}" ]; then
    # Copy the latest log file
    if [ -f "${LOGS_DIR}/latest.log" ]; then
        LATEST_LOG=$(readlink -f "${LOGS_DIR}/latest.log" 2>/dev/null || echo "${LOGS_DIR}/latest.log")
        if [ -f "$LATEST_LOG" ]; then
            LOG_BASENAME=$(basename "$LATEST_LOG")
            cp "$LATEST_LOG" "${LOGS_SUBDIR}/${LOG_BASENAME}"
            echo -e "  ${GREEN}✓${NC} Copied ${LOG_BASENAME}"
            FILES_COPIED=$((FILES_COPIED + 1))
        fi
    fi
    
    # Copy all log files from today
    find "${LOGS_DIR}" -name "pipeline_*.log" -mtime 0 -exec cp {} "${LOGS_SUBDIR}/" \; 2>/dev/null || true
fi

# ===== Copy Generated Source Files (Test classes) =====
echo -e "${YELLOW}Copying generated test source files...${NC}"
TEST_SRC_DIR="${RESULTS_DIR}/test_project_metrics/src/test/java"
if [ -d "$TEST_SRC_DIR" ]; then
    find "$TEST_SRC_DIR" -name "*.java" -exec cp {} "${SOURCE_SUBDIR}/" \; 2>/dev/null
    JAVA_COUNT=$(ls -1 "${SOURCE_SUBDIR}"/*.java 2>/dev/null | wc -l)
    if [ "$JAVA_COUNT" -gt 0 ]; then
        echo -e "  ${GREEN}✓${NC} Copied ${JAVA_COUNT} test source file(s)"
        FILES_COPIED=$((FILES_COPIED + JAVA_COUNT))
    fi
fi

# ===== Copy Original Source Files (Classes under test) =====
MAIN_SRC_DIR="${RESULTS_DIR}/test_project_metrics/src/main/java"
if [ -d "$MAIN_SRC_DIR" ]; then
    mkdir -p "${SOURCE_SUBDIR}/main"
    find "$MAIN_SRC_DIR" -name "*.java" -exec cp {} "${SOURCE_SUBDIR}/main/" \; 2>/dev/null
    MAIN_JAVA_COUNT=$(ls -1 "${SOURCE_SUBDIR}/main"/*.java 2>/dev/null | wc -l)
    if [ "$MAIN_JAVA_COUNT" -gt 0 ]; then
        echo -e "  ${GREEN}✓${NC} Copied ${MAIN_JAVA_COUNT} main source file(s)"
        FILES_COPIED=$((FILES_COPIED + MAIN_JAVA_COUNT))
    fi
fi

if [ $FILES_COPIED -eq 0 ]; then
    echo -e "${YELLOW}No files found to push. Exiting.${NC}"
    rm -rf "$TEMP_REPO"
    exit 0
fi

# Stage, commit, and push
echo -e "${YELLOW}Committing changes...${NC}"
git add -A

# Get current timestamp for commit message
TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S UTC")

if git diff --staged --quiet; then
    echo -e "${YELLOW}No changes to commit.${NC}"
else
    git commit -m "Pipeline Results: ${TIMESTAMP}

Automated commit from Research Pipeline Docker container.

Files included:
- CSV coverage results
- Pipeline execution logs
- Generated test source files
- Classes under test

Total files: ${FILES_COPIED}"
    
    echo -e "${YELLOW}Pushing to remote...${NC}"
    git push origin "$GIT_BRANCH"
    
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}  ✓ Successfully pushed ${FILES_COPIED} file(s)!${NC}"
    echo -e "${GREEN}============================================${NC}"
fi

# Cleanup
cd /
rm -rf "$TEMP_REPO"
