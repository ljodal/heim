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
