# =============================================================================
# Multi-stage Dockerfile for Research Pipeline
# JUnit Test Generation & Coverage Analysis
# =============================================================================

FROM python:3.11-slim AS base

# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# =============================================================================
# Stage 1: Install Java and Maven
# =============================================================================
FROM base AS java-builder

# Install dependencies for adding repositories
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    ca-certificates \
    curl \
    git \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Add Eclipse Temurin repository for Java 8
RUN wget -qO - https://packages.adoptium.net/artifactory/api/gpg/key/public | gpg --dearmor -o /usr/share/keyrings/adoptium.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/adoptium.gpg] https://packages.adoptium.net/artifactory/deb $(. /etc/os-release && echo $VERSION_CODENAME) main" > /etc/apt/sources.list.d/adoptium.list

# Install Java 8 (Temurin) and Maven
RUN apt-get update && apt-get install -y --no-install-recommends \
    temurin-8-jdk \
    maven \
    && rm -rf /var/lib/apt/lists/*

# Set Java environment variables
ENV JAVA_HOME=/usr/lib/jvm/temurin-8-jdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

# =============================================================================
# Stage 2: Final image with Python dependencies
# =============================================================================
FROM java-builder AS final

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt* ./

# Create requirements.txt if it doesn't exist, then install
RUN if [ -f requirements.txt ]; then \
        pip install --no-cache-dir -r requirements.txt; \
    else \
        pip install --no-cache-dir \
            pandas \
            langchain \
            langchain-openai \
            langchain-core \
            python-dotenv; \
    fi

# Copy project files
COPY . .

# Create directories for Maven project output and logs
RUN mkdir -p test_project_metrics/src/main/java \
             test_project_metrics/src/test/java \
             logs

# Make scripts executable
RUN chmod +x git_push.sh entrypoint.sh

# Default environment variables (can be overridden by .env file at runtime)
ENV GIT_BRANCH="main" \
    GIT_USER_NAME="Research Pipeline Bot" \
    GIT_USER_EMAIL="pipeline@automated.local" \
    ENABLE_GIT_PUSH="true"

# Default command - run the entrypoint which handles pipeline and git push
ENTRYPOINT ["/app/entrypoint.sh"]
