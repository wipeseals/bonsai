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

# Create a Python environment for the bonsai project
$ uv python install

# Synchronize packages
$ uv sync --all-extras --dev

# Run all simulations
$ uv run pytest
```

## Generate Verilog

```bash
# Generate Verilog for any design
$ uv run bonsai/<design name>.py

# Example
$ uv run bonsai/stage.py

# TODO: add main design file

```

### Use Docker Compose

```bash
$ docker-compose run bonsai
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.

## Contact

For any inquiries or questions, you can reach out to the project maintainer at [wipeseals@gmail.com](mailto:wipeseals@gmail.com).
