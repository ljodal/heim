#!/bin/bash
# Setup script for Claude Code for web environment
# Only runs in remote environments, not locally

if [ "$CLAUDE_CODE_REMOTE" != "true" ]; then
    exit 0
fi

set -e

# Install uv (fast Python package manager)
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"

    # Persist PATH for subsequent commands
    if [ -n "$CLAUDE_ENV_FILE" ]; then
        echo "PATH=$HOME/.local/bin:$PATH" >> "$CLAUDE_ENV_FILE"
    fi
fi

# Install Python 3.14 using uv
uv python install 3.14

# Install project dependencies (including dev tools)
cd "$CLAUDE_PROJECT_DIR"
uv sync --all-groups

exit 0
