FROM python:3.11-slim

# Config debian
RUN apt update && apt install -y \
    libgmp10 \
    libtinfo6 \
    curl \
    unzip \
    gnupg \
    openssh-client \
    enscript \
    ghostscript \
    locales \
    ripgrep \
    python3-cffi \
    python3-brotli \
    libpango-1.0-0 \
    libharfbuzz0b \
    libpangoft2-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/'        /etc/locale.gen \
    && sed -i -e 's/# pt_BR.UTF-8 UTF-8/pt_BR.UTF-8 UTF-8/' /etc/locale.gen \
    && locale-gen

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project

COPY ./streamlit_sql ./app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen

EXPOSE 8501
ENV PYTHONPATH="/app"
ENV LANG=en_US.UTF-8
ENV BKP_DIR=/bkp

RUN useradd -m appuser
ENV HOME=/home/appuser
ENV PATH=$HOME/.local/bin:$PATH
USER appuser

ENTRYPOINT ["uv","run", "--","streamlit", "run", "./app/webapp.py"]
