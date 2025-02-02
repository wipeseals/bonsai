# Bonsai

[![Pytest](https://github.com/wipeseals/bonsai/actions/workflows/pytest.yml/badge.svg)](https://github.com/wipeseals/bonsai/actions/workflows/pytest.yml)

Bonsai is a RISC-V CPU designed using [Amaranth HDL](https://github.com/amaranth-lang/amaranth).

## Features

TODO:

## Getting Started

This project is managed with [uv](https://docs.astral.sh/uv/).

### Local Python Environment Setup

```bash
# install uv
$ pip install --upgrade pip
$ pip install uv
```

```bash
# Create a Python environment for the bonsai project
$ uv python install
$ uv venv

# Synchronize packages
$ uv sync --all-extras --dev
```

### Run Tests

```bash
$ uv run test
```

### Use Docker Compose

```bash
$ docker-compose run bonsai
```

## Available Tasks

The following tasks are available via `taskipy`:

- `task run`: Run the main script.
- `task test`: Run all tests.
- `task cov`: Run tests with coverage report.
- `task check`: Run `ruff` to check code style.
- `task format`: Run `ruff` to format code.
- `task docs-serve`: Serve the documentation locally.
- `task docs-build`: Build the documentation.
- `task mypy`: Run `mypy` for type checking.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.

## Contact

For any inquiries or questions, you can reach out to the project maintainer at [wipeseals@gmail.com](mailto:wipeseals@gmail.com).
