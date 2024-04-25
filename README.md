[![Python 3.11](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3123/)

# ms-migrate-cli

Command line tool for migrating Meraki switch configurations.


## Requirements

- Python >= 3.12
- [Poetry](https://python-poetry.org/docs/#installing-with-the-official-installer)


## Installation

```sh
poetry env use $(which python)
```

```sh
poetry install
```


## Commands

### `display`: Display switch configuration by DEVICE_SERIAL.

```sh
ms-device display [OPTIONS] DEVICE_SERIAL
```

Options:
- `-a`, `--api-key`: Meraki Dashboard API key. If not provided, the CLI will attempt to pull the API key from the environment variable `MERAKI_DASHBOARD_API_KEY`.


### `migrate`: Copy device configuration and port configurations from one Meraki switch to another.

```sh
ms-device migrate [OPTIONS] SOURCE_SERIAL TARGET_SERIAL
```

Options:
- `-a`, `--api-key`: Meraki Dashboard API key. If not provided, the CLI will attempt to pull the API key from the environment variable `MERAKI_DASHBOARD_API_KEY`.
- `-o`, `--org-id`: Meraki Dashboard organization ID. Only used if both switches are the same model #.
- `-q`, `--quiet`: Suppress dashboard API logging output.
- `-y`, `--yes`: Skip confirmation prompt.


### `tag`: Add "undeployed" to the tags attribute of a switch device.

```sh
ms-device tag [OPTIONS] DEVICE_SERIAL
```

Options:
- `-a`, `--api-key`: Meraki Dashboard API key. If not provided, the CLI will attempt to pull the API key from the environment variable `MERAKI_DASHBOARD_API_KEY`.


## Usage

### Option 1: Use the `poetry` nested shell

Create a nested shell to activate the virtual environment:
```sh
poetry shell
```

Run the CLI:
```sh
ms-device --help
ms-device display --help
ms-device migrate --help
```


### Option 2: Use `poetry run`

Enter `poetry run` followed by the command:
```sh
poetry run ms-device --help
poetry run ms-device display --help
poetry run ms-device migrate --help
```


### Option 3: Build and install with `pip`

Build the wheel:
```sh
poetry build -f wheel
```

Install it:
```sh
pip install dist/ms_migrate_cli-0.1.0-py3-none-any.whl
```

Run as you would any other shell command:
```sh
ms-device --help
```


## Examples:

#### Display configuration for one switch:

```sh
ms-device display -a [API_KEY] <DEVICE_SERIAL>
```

#### Copy configuration from source switch `Q234-ABCD-5678` to target switch `Q234-ABCD-0001`:

```sh
ms-device migrate -a API_KEY Q234-ABCD-5678 Q234-ABCD-0001
```
or
```sh
ms-device migrate Q234-ABCD-5678 Q234-ABCD-0001
```

#### Clone configuration from a source switch to a target switch of the same model:

```sh
ms-device migrate -a API_KEY -o ORG_ID Q234-ABCD-5678 Q234-ABCD-0001
```

Note: The CLI will attempt to pull the Meraki Dashboard API key from the environment variable `MERAKI_DASHBOARD_API_KEY` if it is not provided as an argument.