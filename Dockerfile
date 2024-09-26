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

WORKDIR /streamlit_sql

COPY ./requirements.txt .

RUN --mount=type=cache,target=/home/eduardo/.cache/pip \
    pip install -r requirements.txt

COPY ./streamlit_sql ./

EXPOSE 8501
ENV PYTHONPATH="/app"
ENV LANG=en_US.UTF-8
ENV BKP_DIR=/bkp

ENTRYPOINT ["streamlit", "run", "webapp.py"]
