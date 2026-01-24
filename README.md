<div align="center">
    <h1>🏡<br>Heim</h1>
    <p>A home monitoring system, focused on temperature and power usage</p>
    <p>
        <a title="CI Status" href="https://github.com/ljodal/heim/actions">
        <img src="https://img.shields.io/github/workflow/status/ljodal/heim/CI/main?style=flat-square"></a>
        <a title="Code Coverage" href="https://app.codecov.io/gh/ljodal/heim/"><img src="https://img.shields.io/codecov/c/github/ljodal/heim?style=flat-square"></a>
        <a title="License" href="https://github.com/ljodal/heim/blob/main/LICENSE"><img src="https://img.shields.io/github/license/ljodal/heim?style=flat-square"></a>
    </p>
</div>

## Project setup

You need Python 3.10+ and PostgreSQL 12+ to run this project.

1. Start by installing the dependencies:

    ```bash
    poetry install
    ```

2. Next you need to set some environment variables, for this I recommend [`direnv`](https://direnv.net):

    ```bash
    # Auto-activate venv
    load_prefix <path to project>/.venv
    export VIRTUAL_ENV=<path to project>/.venv

    # Set up aqara integration
    export AQARA_APP_ID=...
    export AQARA_APP_KEY=...
    export AQARA_KEY_ID=...
    export AQARA_DOMAIN=open-ger.aqara.com

    # Set up netatmo integration
    export NETATMO_CLIENT_ID=...
    export NETATMO_CLIENT_SECRET=...

    # Specify which database to use
    export PGDATABASE=heim
    ```

3. Create the database:

    ```bash
    createdb heim
    ```

4. Apply migrations:

    ```bash
    ./bin/migrate
    ```

5. That should be if, you're now good to go.

## Running

To run the server use any ASGI server. `uvicorn` is installed as part of the project dependencies. It supports reloading as well:

```bash
uvicorn heim.server:app --reload
```

In addition to the HTTP component, heim also has a background task runner that has to be run as a separate process:

```bash
./bin/run-tasks
```

## Integrations

### Netatmo Weather Station

Heim supports Netatmo weather stations (indoor/outdoor sensors, rain gauge, etc.).

#### Setup

1. **Create a Netatmo app** at [dev.netatmo.com](https://dev.netatmo.com/apps/createanapp)
   - You'll need a Netatmo account with at least one weather station
   - Note down the `client_id` and `client_secret`
   - Add `http://localhost:8000/api/netatmo/callback` as a redirect URI

2. **Set environment variables**:

    ```bash
    export NETATMO_CLIENT_ID=your_client_id
    export NETATMO_CLIENT_SECRET=your_client_secret
    ```

3. **Make sure the heim server is running**:

    ```bash
    uvicorn heim.server:app
    ```

4. **Authorize with Netatmo** (opens browser):

    ```bash
    heim netatmo accounts auth
    ```

    After authorization, you'll be redirected to heim which displays the command to run.

5. **Link your Netatmo account** using the command shown:

    ```bash
    heim netatmo accounts create --account-id 1 --auth-code <code>
    ```

5. **List your devices** to find the module IDs:

    ```bash
    heim netatmo devices list -a 1
    ```

6. **Register sensors** for data collection:

    ```bash
    heim netatmo devices create --name "Living Room" --netatmo-id <module_id> --location-id 1 -a 1
    ```

    This will create a sensor and schedule automatic data collection every 10 minutes.

#### Supported modules

| Module Type | Description | Data Collected |
|-------------|-------------|----------------|
| NAMain | Indoor base station | Temperature, Humidity, CO2, Noise, Pressure |
| NAModule1 | Outdoor module | Temperature, Humidity |
| NAModule3 | Rain gauge | Precipitation |
| NAModule4 | Additional indoor | Temperature, Humidity, CO2 |

#### CLI Commands

```bash
# Account management
heim netatmo accounts auth              # Open browser to authorize with Netatmo
heim netatmo accounts create            # Link a Netatmo account

# Device management
heim netatmo devices list -a <id>       # List all stations and modules
heim netatmo devices create             # Register a module as a sensor
heim netatmo devices sensors -a <id>    # List registered sensors
heim netatmo devices backfill -a <id>   # Backfill historical data
```
