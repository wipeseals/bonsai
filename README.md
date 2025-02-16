# Bonsai

[![Pytest](https://github.com/wipeseals/bonsai/actions/workflows/pytest.yml/badge.svg)](https://github.com/wipeseals/bonsai/actions/workflows/pytest.yml)

bonsai is a RISC-V CPU designed using [Amaranth HDL](https://github.com/amaranth-lang/amaranth).

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

### Run

```bash
# Available tasks
$ uv run task -l
run    python bonsai/main.py
test   pytest -v --ff -rfs
cov    pytest --cov bonsai --cov-report term --cov-report xml
check  ruff check --fix
format ruff format
mypy   mypy bonsai

# Run the bonsai project
task run -h
usage: main.py [-h] [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}] {build} ...

positional arguments:
  {build}               Select the action to perform
    build               build the project

options:
  -h, --help            show this help message and exit
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Set the logging level


# Run simulation
task test     
============================================================ test session starts ============================================================
platform win32 -- Python 3.10.14[pypy-7.3.17-final], pytest-8.3.4, pluggy-1.5.0 -- E:\repos\bonsai\.venv\Scripts\python.exe
cachedir: .pytest_cache
metadata: {'Python': '3.10.14', 'Platform': 'Windows-10-10.0.26100-SP0', 'Packages': {'pytest': '8.3.4', 'pluggy': '1.5.0'}, 'Plugins': {'cov': '6.0.0', 'html': '4.1.1', 'metadata': '3.1.1', 'mock': '3.14.0'}, 'JAVA_HOME': 'C:\\Program Files\\Microsoft\\jdk-17.0.14.7-hotspot\\'}     
rootdir: E:\repos\bonsai
configfile: pyproject.toml
plugins: cov-6.0.0, html-4.1.1, metadata-3.1.1, mock-3.14.0
...
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.

## Contact

For any inquiries or questions, you can reach out to the project maintainer at [wipeseals@gmail.com](mailto:wipeseals@gmail.com).
