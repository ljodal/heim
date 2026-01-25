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

# Install Python 3.13 using uv
uv python install 3.13

# Install project dependencies (including dev tools)
cd "$CLAUDE_PROJECT_DIR"
uv sync --all-groups

# Install and configure PostgreSQL for running tests
if ! command -v psql &> /dev/null; then
    echo "Installing PostgreSQL..."
    apt-get update
    apt-get install -y postgresql postgresql-contrib
fi

# Fix SSL key permissions (required for PostgreSQL to start)
if [ -f /etc/ssl/private/ssl-cert-snakeoil.key ]; then
    chmod 600 /etc/ssl/private/ssl-cert-snakeoil.key
fi

# Configure PostgreSQL to use trust authentication for local connections
# This is needed because the data directory may be owned by a different user
PG_VERSION=$(ls /etc/postgresql/ | head -1)
PG_HBA="/etc/postgresql/${PG_VERSION}/main/pg_hba.conf"
if [ -f "$PG_HBA" ]; then
    # Update local authentication to trust for all users
    sed -i 's/^local\s\+all\s\+postgres\s\+peer$/local   all             postgres                                trust/' "$PG_HBA"
    sed -i 's/^local\s\+all\s\+all\s\+peer$/local   all             all                                     trust/' "$PG_HBA"

    # Ensure config files are owned by the same user as the data directory
    DATA_OWNER=$(stat -c '%U:%G' /var/lib/postgresql/${PG_VERSION}/main 2>/dev/null || echo "postgres:postgres")
    chown -R "$DATA_OWNER" /etc/postgresql/${PG_VERSION}/
fi

# Start PostgreSQL service
echo "Starting PostgreSQL service..."
service postgresql start

# Wait for PostgreSQL to be ready
for i in {1..10}; do
    if pg_isready; then
        break
    fi
    echo "Waiting for PostgreSQL to start..."
    sleep 1
done

# Create database user and database (matching CI configuration)
echo "Setting up PostgreSQL database..."
psql -U postgres -c "CREATE USER heim WITH PASSWORD 'heim' CREATEDB;" 2>/dev/null || true
psql -U postgres -c "CREATE DATABASE heim OWNER heim;" 2>/dev/null || true

# Set PostgreSQL environment variables for tests
if [ -n "$CLAUDE_ENV_FILE" ]; then
    echo "PGHOST=localhost" >> "$CLAUDE_ENV_FILE"
    echo "PGDATABASE=heim" >> "$CLAUDE_ENV_FILE"
    echo "PGUSER=heim" >> "$CLAUDE_ENV_FILE"
    echo "PGPASSWORD=heim" >> "$CLAUDE_ENV_FILE"
fi

# Also export for current session
export PGHOST=localhost
export PGDATABASE=heim
export PGUSER=heim
export PGPASSWORD=heim

echo "PostgreSQL setup complete. Database 'heim' is ready."

exit 0
