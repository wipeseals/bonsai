FROM python:latest

WORKDIR /app

# install git
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# setup uv
RUN pip install --upgrade pip
RUN pip install uv

# install dependencies
COPY . /app
RUN uv python install
RUN uv venv .venv.docker
RUN uv sync --all-extras --dev

# run tests
CMD ["uv", "run", "pytest", "-v", "-rfs"]