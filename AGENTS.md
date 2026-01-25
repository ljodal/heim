# Heim

Home automation dashboard with sensor data visualization and weather forecasts.

## Tech Stack

- **Backend**: Python 3.13+, FastAPI, asyncpg
- **Frontend**: Jinja2 templates, Bootstrap, Chart.js
- **Database**: PostgreSQL 18
- **Deployment**: Docker with docker-compose

## Development Setup

```bash
# Install dependencies
uv sync

# Run locally (requires postgres)
DATABASE_URL=postgresql://user:pass@localhost/heim uv run heim db migrate
DATABASE_URL=postgresql://user:pass@localhost/heim uv run heim tasks run

# Run with Docker
docker compose build
docker compose up -d
```

## CLI Commands

```bash
# Database
heim db migrate              # Run database migrations

# Background tasks
heim tasks run               # Start the background worker

# Accounts
heim account create          # Create a new account

# Locations
heim location create         # Create a new location

# Aqara integration
heim aqara accounts get-auth-code --aqara-account <email>
heim aqara accounts create --account-id <id> --aqara-account <email> --auth-code <code>
heim aqara devices list -a <account-id>
heim aqara devices resources <model>
heim aqara devices create --name <name> --aqara-id <id> --location-id <id> -a <account-id>
heim aqara devices backfill -a <account-id>                    # List available sensors
heim aqara devices backfill -a <account-id> --sensor-id <id>   # Backfill sensor data

# YR forecasts
heim yr create --account-id <id> --location-id <id> --name <name>
heim yr start --forecast-id <id>
```

## Docker Commands

```bash
# Build and start
docker compose build
docker compose up -d

# View logs
docker compose logs -f web
docker compose logs -f worker

# Run CLI commands in container
docker compose run --rm web heim <command>
docker compose run --rm --env-file .env web heim aqara devices backfill -a 1

# Database access
docker compose exec db psql -U heim
```

## Project Structure

```
heim/
├── accounts/       # Account management
├── auth/           # Authentication (sessions, cookies)
├── db/             # Database connection and migrations
│   └── migrations/ # SQL migration files
├── forecasts/      # Weather forecast data
├── frontend/       # Web UI (views, templates)
│   └── templates/  # Jinja2 templates
├── integrations/
│   ├── aqara/      # Aqara smart home integration
│   └── yr/         # Norwegian weather service integration
├── sensors/        # Sensor data management
└── tasks/          # Background task system
```

## Environment Variables

Required for Aqara integration (in `.env`):
```
AQARA_APP_ID=
AQARA_APP_KEY=
AQARA_KEY_ID=
AQARA_DOMAIN=
```

Required for database:
```
DATABASE_URL=postgresql://user:pass@host:port/dbname
```

## Adding New Aqara Sensor Types

1. Run `heim aqara devices resources <model>` to see available resources
2. Add the model to `MODEL_TO_RESOURCE_MAPPING` in `heim/integrations/aqara/tasks.py`
3. Create a migration in `heim/db/migrations/` to add the type to `aqara_sensor_type` enum:
   ```sql
   alter type aqara_sensor_type add value '<model>';
   ```

## Testing

```bash
uv run pytest
uv run pytest --cov=heim
```

## Linting

```bash
uv run ruff check heim       # Check for lint errors
uv run ruff check --fix heim # Fix auto-fixable errors
uv run ruff format heim      # Format code
uv run mypy                  # Type checking (with strict mode)
uv run ty check heim         # Fast type checking (Astral's ty)
make lint                    # Run ruff checks
make typecheck               # Run both mypy and ty
make                         # Run all checks (lint + typecheck + test)
```

## Agent Instructions

**Before pushing any code, you MUST run `make` and ensure all checks pass:**

```bash
make                         # Runs: lint, typecheck, test
```

This runs:
1. `ruff check` - Lint checking
2. `ruff format --check` - Format verification
3. `mypy` - Strict type checking
4. `ty check` - Fast type checking
5. `pytest` - All tests

If any check fails:
1. Run `make fix` to auto-fix formatting and lint issues
2. Fix any remaining type errors manually
3. Fix any failing tests
4. Re-run `make` to verify all checks pass
5. Only then commit and push
