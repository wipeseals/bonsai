# Rusk

[![Pytest](https://github.com/wipeseals/rusk/actions/workflows/pytest.yml/badge.svg)](https://github.com/wipeseals/rusk/actions/workflows/pytest.yml)

Rusk is a RISC-V CPU designed using Amaranth for educational purposes.

## Features

TODO:

## Getting Started

This project is managed with [uv](https://docs.astral.sh/uv/).

```bash
# Create a Python environment for the rusk project
$ uv python install

# Synchronize packages
$ uv sync --all-extras --dev

# Run tests
$ uv run pytest
```

## Generate Verilog

```bash
# Generate Verilog for any design
$ uv run rusk/<design name>.py generate <design name>.v

# Example
$ uv run rusk/top.py generate top.v
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.

## Contact

For any inquiries or questions, you can reach out to the project maintainer at [wipeseals@gmail.com](mailto:wipeseals@gmail.com).
