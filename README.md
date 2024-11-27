# Bonsai

[![Pytest](https://github.com/wipeseals/bonsai/actions/workflows/pytest.yml/badge.svg)](https://github.com/wipeseals/bonsai/actions/workflows/pytest.yml)

Bonsai is a RISC-V CPU designed using [Amaranth HDL](https://github.com/amaranth-lang/amaranth).

## Features

TODO:

## Getting Started

This project is managed with [uv](https://docs.astral.sh/uv/).

```bash
# install uv
$ pip install --upgrade pip
$ pip install uv

# Create a Python environment for the bonsai project
$ uv python install

# Synchronize packages
$ uv sync --all-extras --dev

# Run tests
$ uv run pytest
```

## Generate Verilog

```bash
# Generate Verilog for any design
$ uv run bonsai/<design name>.py

# Example
$ uv run bonsai/stage.py
```

## Additional Information

### Use yosys

By using amaranth-yosys (a pre-built yosys running on wasm with wasmtime) which is used as a backend by Amaranth, you can utilize it with just the uv environment setup.

```sh
$ python -m  amaranth_yosys

 /----------------------------------------------------------------------------\
 |  yosys -- Yosys Open SYnthesis Suite                                       |
 |  Copyright (C) 2012 - 2024  Claire Xenia Wolf <claire@yosyshq.com>         |
 |  Distributed under an ISC-like license, type "license" to see terms        |
 \----------------------------------------------------------------------------/
 Amaranth Yosys 0.40 (PyPI ver 0.40.0.0.post100, git sha1 a1bb0255d)
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.

## Contact

For any inquiries or questions, you can reach out to the project maintainer at [wipeseals@gmail.com](mailto:wipeseals@gmail.com).
